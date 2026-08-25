"""TradingAgents 深度研究子图测试（规格 v2 决策 19-20；US-2.7；切片 06）。

覆盖：子图节点产出归一化 claims（结构化，非自由文本）、gateway 上下文
在传播期间设置并在结束后清除、Supervisor 深度研究路由。
"""

from datetime import date, datetime, timezone
from typing import ClassVar

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent_runtime.graphs import RuleBasedSupervisor, build_supervisor_pipeline
from app.agent_runtime.runtime import NodeContext
from app.agent_runtime.stores import create_stores
from app.agent_runtime.ta_bridge import vendor
from app.config import Base
from app.domain.plans import RunBudget
from app.models.agent_runtime import AgentRun
from app.models.models import DailyKline, Stock

AS_OF = datetime(2026, 8, 14, 7, 0, tzinfo=timezone.utc)


class FakeTradingAgentsGraph:
    """替代真实 TA 图：记录调用，返回固定 final_state。"""

    calls: ClassVar[list] = []
    saw_context: ClassVar[bool] = False

    def __init__(self, selected_analysts, config=None):
        FakeTradingAgentsGraph.calls.append(
            {"analysts": selected_analysts, "config": config}
        )
        assert vendor._state["context"] is not None, "传播期间必须有网关上下文"
        FakeTradingAgentsGraph.saw_context = True

    def propagate(self, company_name, trade_date):
        return (
            {
                "market_report": "市场分析：均线多头排列，量能温和放大。",
                "news_report": "新闻：公司发布业绩预增公告。",
                "fundamentals_report": "基本面：ROE 改善，估值合理。",
                "sentiment_report": "",
                "policy_report": "",
                "hot_money_report": "",
                "lockup_report": "",
                "final_trade_decision": "bullish 看多：建议轻仓试多",
            },
            "bullish",
        )


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add(AgentRun(run_id="run-ta-1", objective="测试"))
    s.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    s.add(
        DailyKline(
            stock_code="sh.600000",
            date=date(2026, 8, 14),
            open=10.0,
            high=10.5,
            low=9.9,
            close=10.3,
            volume=100000,
            amount=1030000,
        )
    )
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def stores(session):
    return create_stores(session)


def _ctx(session, stores):
    return NodeContext(
        run_id="run-ta-1",
        seq=1,
        node="ta_research",
        stores=stores,
        step_db_id=None,
        db=session,
        as_of=AS_OF,
    )


def test_ta_research_node_emits_normalized_claims(session, stores, monkeypatch):
    import tradingagents.graph.trading_graph as ta_graph

    FakeTradingAgentsGraph.calls = []
    FakeTradingAgentsGraph.saw_context = False
    monkeypatch.setattr(ta_graph, "TradingAgentsGraph", FakeTradingAgentsGraph)

    from app.agent_runtime.ta_bridge.subgraph import ta_research_node

    result = ta_research_node("sh.600000", "深度研究 sh.600000").run(
        _ctx(session, stores)
    )
    assert result["output_schema"] == "ResearchClaim[]"
    claims = result["output"]["claims"]
    assert claims, "应产出归一化 claims"
    by_category = {c["category"]: c for c in claims}
    assert "technical" in by_category  # market_report
    assert "news" in by_category  # news_report
    assert "fundamental" in by_category  # fundamentals_report
    decision = next(c for c in claims if "最终决策" in c["claim"])
    assert decision["direction"] == "bullish"
    for claim in claims:
        assert claim["evidence"], "所有 claim 必须有证据"
        assert claim["evidence"][0]["source_id"].startswith("ta:sh.600000:")
    assert FakeTradingAgentsGraph.saw_context is True

    # gateway 上下文已清除
    assert vendor._state["context"] is None


def test_supervisor_routes_deep_research(session, stores):
    plan = RuleBasedSupervisor().plan("对 sh.600000 做深度研究", RunBudget())
    nodes = [s.node for s in plan.steps]
    assert "ta_research" in nodes
    assert "research" in nodes

    pipeline = build_supervisor_pipeline("对 sh.600000 做深度研究", RunBudget())
    names = [node.name for node in pipeline]
    assert "ta_research" in names


def test_plain_objective_does_not_route_deep_research(session, stores):
    plan = RuleBasedSupervisor().plan("判断 sh.600000 短期趋势", RunBudget())
    nodes = [s.node for s in plan.steps]
    assert "ta_research" not in nodes
