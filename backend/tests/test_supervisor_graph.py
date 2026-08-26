"""Supervisor 动态路由图测试（任务 09 验收）。

覆盖：规则路由、动态节点组装、全链路执行（专家输出过 domain schema）、
backtest_critic 确定性结论、SchemaGuardedNode 非法输出重试后失败。
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.strategy  # noqa: F401
from app.agent_runtime.graphs import (
    RuleBasedSupervisor,
    build_supervisor_pipeline,
    extract_stock_code,
    guard,
)
from app.agent_runtime.runtime import RunExecutor, SimpleNode
from app.agent_runtime.stores import create_stores
from app.config import Base
from app.domain.backtest import BacktestVerdict
from app.domain.plans import RunBudget, RunPlan
from app.domain.portfolio import PortfolioProposal
from app.domain.quality import DataQualityReport
from app.domain.research import ResearchClaim
from app.models.models import DailyKline, Stock


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    start = date(2024, 1, 1)
    closes = [10, 10.2, 10.5, 10.9, 11.2, 10.8, 10.4, 10.0, 9.8, 10.3, 10.9, 11.4]
    for idx, close in enumerate(closes):
        s.add(
            DailyKline(
                stock_code="sh.600000",
                date=start + timedelta(days=idx),
                open=close - 0.1,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=100000 + idx * 1000,
                amount=close * 100000,
            )
        )
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def stores(session):
    return create_stores(session)


# ---------- 路由 ----------

def test_rule_based_routing_basic():
    plan = RuleBasedSupervisor().plan("研究 sh.600519 趋势", RunBudget())
    nodes = [s.node for s in plan.steps]
    assert nodes[:3] == ["supervisor", "data_qa", "research"]
    assert "portfolio_risk" in nodes
    assert "strategy_engineer" not in nodes
    assert "backtest_critic" not in nodes


def test_extract_stock_code_without_leading_space():
    assert extract_stock_code("分析sz.000002") == "sz.000002"


def test_rule_based_routing_with_strategy_and_backtest():
    plan = RuleBasedSupervisor().plan("生成 ma_cross 策略并回测验证 sh.600000", RunBudget())
    nodes = [s.node for s in plan.steps]
    assert "strategy_engineer" in nodes
    assert "backtest_critic" in nodes
    assert "portfolio_risk" in nodes


def test_build_pipeline_dynamic_nodes():
    pipeline = build_supervisor_pipeline("策略回测验证 sh.600000", RunBudget())
    names = [node.name for node in pipeline]
    assert names[0] == "supervisor"
    assert {"data_qa", "research", "strategy_engineer", "backtest_critic", "portfolio_risk"} <= set(
        names
    )


# ---------- 全链路执行 ----------

def test_full_pipeline_basic_run(stores, session):
    executor = RunExecutor(stores, db=session)
    run_id = executor.create_run("研究 sh.600000 趋势", budget=RunBudget(max_rounds=10))
    pipeline = build_supervisor_pipeline("研究 sh.600000 趋势", RunBudget())
    run = executor.execute(run_id, pipeline)

    assert run["status"] == "completed"
    steps = stores.steps.list_steps(run_id)
    assert [s["node"] for s in steps][:2] == ["supervisor", "data_qa"]

    by_node = {s["node"]: s for s in steps}
    assert by_node["supervisor"]["output_schema"] == "RunPlan"
    RunPlan.model_validate(by_node["supervisor"]["output_json"])
    DataQualityReport.model_validate(by_node["data_qa"]["output_json"])
    research_out = by_node["research"]["output_json"]
    assert all(isinstance(ResearchClaim.model_validate(c), ResearchClaim) for c in research_out["claims"])
    PortfolioProposal.model_validate(by_node["portfolio_risk"]["output_json"])


def test_full_pipeline_with_backtest_critic(stores, session):
    executor = RunExecutor(stores, db=session)
    run_id = executor.create_run("生成策略并回测验证 sh.600000", budget=RunBudget(max_rounds=10))
    pipeline = build_supervisor_pipeline("生成策略并回测验证 sh.600000", RunBudget())
    run = executor.execute(run_id, pipeline)

    assert run["status"] == "completed"
    steps = {s["node"]: s for s in stores.steps.list_steps(run_id)}
    assert "backtest_critic" in steps
    verdict = BacktestVerdict.model_validate(steps["backtest_critic"]["output_json"])
    assert verdict.passed in (True, False)  # 确定性结构；数值由数据决定
    assert verdict.reasons  # 通过/拒绝均有原因


def test_backtest_critic_verdict_is_deterministic(stores, session):
    from app.agent_runtime.graphs.experts import backtest_critic_node

    executor = RunExecutor(stores, db=session)
    run_id = executor.create_run("回测验证", budget=RunBudget(max_rounds=5))
    run = executor.execute(run_id, [backtest_critic_node("sh.600000")])
    assert run["status"] == "completed"
    step = stores.steps.list_steps(run_id)[0]
    verdict = BacktestVerdict.model_validate(step["output_json"])
    # 2024 年数据在近一年区间外 → 拒绝且给出原因（确定性）
    assert verdict.passed is False
    assert any("回测无法执行" in r for r in verdict.reasons)


def test_backtest_critic_success_path_with_in_range_data(stores, session):
    """真实数据路径：区间内有 K 线时产出确定性 BacktestVerdict（回归：
    max_drawdown 字段名曾写错导致成功路径 AttributeError）。"""
    from datetime import date as _date
    from datetime import timedelta as _td

    from app.agent_runtime.graphs.experts import backtest_critic_node
    from app.models.models import DailyKline

    # 在回测区间（今天-1年 ~ 今天）内补数据
    start = _date.today() - _td(days=200)
    for idx in range(60):
        close = 10.0 + (idx % 5) * 0.1
        session.add(
            DailyKline(
                stock_code="sh.600000",
                date=start + _td(days=idx),
                open=close - 0.1,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=100000 + idx * 1000,
                amount=close * 100000,
            )
        )
    session.commit()

    executor = RunExecutor(stores, db=session)
    run_id = executor.create_run("回测成功路径", budget=RunBudget(max_rounds=5))
    run = executor.execute(run_id, [backtest_critic_node("sh.600000")])
    assert run["status"] == "completed"
    step = stores.steps.list_steps(run_id)[0]
    verdict = BacktestVerdict.model_validate(step["output_json"])
    assert verdict.passed in (True, False)  # 成功路径：确定性结论
    assert verdict.reasons


# ---------- Schema 守卫 ----------

def test_guard_retries_then_fails_on_invalid_output(stores, session):
    attempts = [0]

    def bad_node(ctx):
        attempts[0] += 1
        return {"output": {"not_a_claim": True}}  # 不是合法 ResearchClaim

    executor = RunExecutor(stores, db=session)
    run_id = executor.create_run("守卫测试", budget=RunBudget(max_rounds=5))
    run = executor.execute(run_id, [guard(SimpleNode("bad", bad_node), ResearchClaim)])
    assert run["status"] == "failed"
    assert "校验" in run["error"]
    assert attempts[0] == 2  # 原始 + 重试一次


def test_guard_passes_valid_output(stores, session):
    def good_node(ctx):
        claim = ResearchClaim(claim="合法结论", category="other", hypothesis=True)
        return {"output": claim.model_dump(mode="json")}

    executor = RunExecutor(stores, db=session)
    run_id = executor.create_run("守卫通过", budget=RunBudget(max_rounds=5))
    run = executor.execute(run_id, [guard(SimpleNode("good", good_node), ResearchClaim)])
    assert run["status"] == "completed"
