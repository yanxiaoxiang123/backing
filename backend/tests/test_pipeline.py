"""Agent 流水线测试：四种模式的阶段门控与最终决策。

使用 fake LLM 返回固定 JSON，monkeypatch tavily 搜索，验证 run_pipeline
与原 orchestrator 语义一致（quick 门控、standard 跳过情报、full/strategy
全阶段执行、取消异常透传）。
"""

from unittest.mock import patch

import pytest

from app.agent.pipeline import MODE_PIPELINES, OrchestratorResult, run_pipeline
from app.agent.protocols import AgentContext


class FakeLLM:
    """按消息条数返回 buy/sell JSON，或抛错。"""

    def __init__(self, content='{"signal": "buy", "confidence": 0.8, "reason": "ok"}'):
        self.content = content
        self.calls = 0

    def chat(self, messages, temperature=0.3, max_tokens=2048):
        self.calls += 1
        if isinstance(self.content, Exception):
            raise self.content
        return {"choices": [{"message": {"content": self.content}}]}


@pytest.fixture(autouse=True)
def _no_tavily():
    with patch(
        "app.agent.pipeline.tavily_search.search_stock_news", return_value=[]
    ):
        yield


def _ctx(mode):
    return AgentContext(stock_code="sh.600000", stock_name="浦发", mode=mode)


class TestPipelineModes:
    def test_quick_completes_with_decision(self):
        llm = FakeLLM()
        result = run_pipeline(_ctx("quick"), llm)
        assert result.success is True
        assert result.final_signal == "buy"
        assert [s["stage_name"] for s in result.stages] == [
            "technical_analysis",
            "decision",
        ]
        assert llm.calls == 2

    def test_quick_stops_after_failed_first_stage(self):
        llm = FakeLLM(content=Exception("llm down"))
        result = run_pipeline(_ctx("quick"), llm)
        assert result.success is False
        assert result.stages[0]["status"] == "failed"
        # decision 阶段保持 PENDING（未被调用）
        assert result.stages[1]["status"] == "pending"
        assert llm.calls == 1

    def test_standard_skips_intel_when_technical_fails(self):
        class FailingThenOK(FakeLLM):
            def chat(self, messages, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("technical failed")
                return {"choices": [{"message": {"content": self.content}}]}

        llm = FailingThenOK()
        result = run_pipeline(_ctx("standard"), llm)
        assert result.stages[0]["status"] == "failed"
        assert result.stages[1]["stage_name"] == "intel"
        assert result.stages[1]["status"] == "pending"  # 被跳过
        assert result.stages[2]["status"] == "completed"  # decision 仍执行
        assert result.success is True
        assert result.final_signal == "buy"

    def test_full_runs_all_stages_even_if_one_fails(self):
        class FailOnRisk(FakeLLM):
            def chat(self, messages, **kwargs):
                self.calls += 1
                if self.calls == 3:  # risk 阶段
                    raise RuntimeError("risk failed")
                return {"choices": [{"message": {"content": self.content}}]}

        llm = FailOnRisk()
        result = run_pipeline(_ctx("full"), llm)
        names = [s["stage_name"] for s in result.stages]
        assert names == ["technical_analysis", "intel", "risk", "decision"]
        assert result.stages[2]["status"] == "failed"
        assert result.stages[3]["status"] == "completed"
        assert result.success is True
        assert llm.calls == 4  # 4 个阶段都执行了

    def test_strategy_mode_has_five_stages(self):
        llm = FakeLLM()
        result = run_pipeline(_ctx("strategy"), llm)
        assert [s["stage_name"] for s in result.stages] == [
            "technical_analysis",
            "intel",
            "risk",
            "strategy",
            "decision",
        ]
        assert result.success is True
        assert llm.calls == 5

    def test_unknown_mode_returns_error_result(self):
        result = run_pipeline(_ctx("bogus"), FakeLLM())
        assert result.success is False
        assert "Unknown mode" in (result.error or "")

    def test_progress_callback_invoked_per_stage(self):
        llm = FakeLLM()
        progress_values = []

        def cb(progress, stages):
            progress_values.append(progress)

        run_pipeline(_ctx("full"), llm, progress_callback=cb)
        assert progress_values == [25.0, 50.0, 75.0, 100.0]

    def test_non_json_decision_falls_back_to_hold(self):
        class EmptyDecision(FakeLLM):
            def chat(self, messages, **kwargs):
                self.calls += 1
                if self.calls == 2:  # decision 阶段返回空内容
                    return {
                        "choices": [{"message": {"content": "no json here"}}]
                    }
                return {"choices": [{"message": {"content": self.content}}]}

        llm = EmptyDecision()
        result = run_pipeline(_ctx("quick"), llm)
        assert result.success is True  # 简单解析也会产出 opinion(hold)
        assert result.final_signal == "hold"


class TestPipelineConstants:
    def test_mode_pipelines_match_orchestrator_modes(self):
        assert set(MODE_PIPELINES.keys()) == {"quick", "standard", "full", "strategy"}

    def test_stage_counts(self):
        assert len(MODE_PIPELINES["quick"]) == 2
        assert len(MODE_PIPELINES["standard"]) == 3
        assert len(MODE_PIPELINES["full"]) == 4
        assert len(MODE_PIPELINES["strategy"]) == 5
