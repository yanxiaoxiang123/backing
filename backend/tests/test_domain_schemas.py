"""领域契约 schema 测试（任务 02 验收）。

覆盖：六大 schema 正反例、证据契约（缺 source_id/as_of/vendor、未来时间被拒）、
假设语义（无证据必须 hypothesis=True）、JSON 序列化往返。
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain import (
    BacktestMetrics,
    BacktestVerdict,
    DataQualityReport,
    Evidence,
    PlanStep,
    PortfolioProposal,
    ResearchClaim,
    RunBudget,
    RunPlan,
    StrategySpec,
)

NOW = datetime.now(timezone.utc)
PAST = NOW - timedelta(days=3)
FUTURE = NOW + timedelta(days=1)


def ev(**overrides):
    base = {
        "source_id": "news-123",
        "as_of": PAST,
        "vendor": "akshare",
        "data_version": "v1",
        "summary": "某公告披露业绩预增",
    }
    base.update(overrides)
    return base


# ---------- Evidence ----------

def test_evidence_valid():
    e = Evidence(**ev())
    assert e.source_id == "news-123"
    assert e.as_of == PAST


def test_evidence_missing_required_fields():
    for field in ("source_id", "as_of", "vendor", "data_version"):
        data = ev()
        del data[field]
        with pytest.raises(ValidationError):
            Evidence(**data)


def test_evidence_future_as_of_rejected():
    with pytest.raises(ValidationError, match="未来时间"):
        Evidence(**ev(as_of=FUTURE))


def test_evidence_naive_as_of_rejected():
    with pytest.raises(ValidationError, match="时区"):
        Evidence(**ev(as_of=PAST.replace(tzinfo=None)))


def test_evidence_roundtrip():
    e = Evidence(**ev())
    restored = Evidence.model_validate_json(e.model_dump_json())
    assert restored == e


# ---------- ResearchClaim ----------

def test_claim_with_evidence_ok():
    c = ResearchClaim(
        claim="业绩预增利好",
        category="fundamental",
        direction="bullish",
        confidence=0.8,
        evidence=[Evidence(**ev())],
    )
    assert not c.hypothesis


def test_claim_without_evidence_must_be_hypothesis():
    with pytest.raises(ValidationError, match="hypothesis"):
        ResearchClaim(claim="感觉要涨", category="technical", direction="bullish")


def test_claim_hypothesis_neutral_ok():
    c = ResearchClaim(
        claim="缺乏数据，仅为假设", category="news", hypothesis=True
    )
    assert c.hypothesis


def test_claim_hypothesis_cannot_declare_strong_direction():
    with pytest.raises(ValidationError, match="假设"):
        ResearchClaim(
            claim="假设上涨", category="news", direction="bullish", hypothesis=True
        )


def test_claim_confidence_bounds():
    with pytest.raises(ValidationError):
        ResearchClaim(claim="x", category="other", confidence=1.5)


# ---------- RunPlan ----------

def test_run_plan_valid():
    plan = RunPlan(
        run_id="run-1",
        objective="研究 sh.600519",
        steps=[
            PlanStep(order=1, node="data_qa", description="数据质量检查"),
            PlanStep(order=2, node="research", description="证据采集"),
        ],
        budget=RunBudget(max_rounds=5, max_tool_calls=10),
    )
    assert plan.status.value == "planned"
    assert plan.schema_version


def test_run_plan_step_order_must_be_sorted():
    with pytest.raises(ValidationError, match="升序"):
        RunPlan(
            run_id="run-1",
            objective="x",
            steps=[
                PlanStep(order=2, node="a", description="b"),
                PlanStep(order=1, node="a", description="b"),
            ],
        )


def test_run_plan_budget_negative_rejected():
    with pytest.raises(ValidationError):
        RunPlan(run_id="r", objective="x", budget=RunBudget(max_tool_calls=-1))


# ---------- StrategySpec ----------

def test_strategy_spec_valid():
    spec = StrategySpec(name="MA交叉", signal="ma_cross", rebalance="weekly")
    assert spec.cost_model.lot_size == 100
    assert spec.cost_model.t_plus_1 is True
    assert spec.schema_version


def test_strategy_spec_rejects_invalid_rebalance():
    with pytest.raises(ValidationError):
        StrategySpec(name="x", signal="ma_cross", rebalance="hourly")  # type: ignore[arg-type]


def test_strategy_spec_rejects_non_scalar_signal_parameters():
    # pydantic 字段级校验已拒绝非标量值（dict 不属于 float|int|str|bool）
    with pytest.raises(ValidationError):
        StrategySpec(
            name="x",
            signal="ma_cross",
            signal_parameters={"formula": {"exec": "lambda: 1"}},
        )


def test_strategy_spec_fraction_bounds():
    with pytest.raises(ValidationError):
        StrategySpec(
            name="x",
            signal="ma_cross",
            position_sizing={"method": "fixed_fraction", "fraction": 1.5},
        )


# ---------- BacktestVerdict ----------

def _verdict(**overrides):
    data = {
        "run_id": "run-1",
        "strategy": StrategySpec(name="MA交叉", signal="ma_cross").model_dump(),
        "snapshot_id": "snap-1",
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 12, 31),
        "benchmark": "sh.000300",
        "metrics": BacktestMetrics(
            total_return=0.12,
            annual_return=0.10,
            max_drawdown_pct=-0.18,
            sharpe_out_of_sample=0.9,
        ),
        "passed": True,
        "reasons": ["样本外达标"],
        "produced_by": "backtest_engine",
    }
    data.update(overrides)
    return data


def test_backtest_verdict_valid():
    v = BacktestVerdict(**_verdict())
    assert v.passed


def test_backtest_verdict_rejected_needs_reasons():
    data = _verdict(passed=False, reasons=[])
    with pytest.raises(ValidationError, match="原因"):
        BacktestVerdict(**data)


def test_backtest_verdict_positive_drawdown_rejected():
    data = _verdict()
    with pytest.raises(ValidationError):
        data["metrics"] = BacktestMetrics(
            total_return=0.1, annual_return=0.1, max_drawdown_pct=0.05, sharpe_out_of_sample=1.0
        )
        BacktestVerdict(**data)


def test_backtest_verdict_roundtrip():
    v = BacktestVerdict(**_verdict())
    assert BacktestVerdict.model_validate_json(v.model_dump_json()) == v


# ---------- PortfolioProposal ----------

def test_portfolio_proposal_valid():
    p = PortfolioProposal(
        run_id="run-1",
        positions=[{"code": "sh.600519", "action": "buy", "weight": 0.2}],
    )
    assert not p.rejected


def test_portfolio_proposal_weight_over_one_rejected():
    with pytest.raises(ValidationError, match="超过 1.0"):
        PortfolioProposal(
            run_id="run-1",
            positions=[
                {"code": "a", "action": "buy", "weight": 0.6},
                {"code": "b", "action": "buy", "weight": 0.6},
            ],
        )


def test_portfolio_proposal_failed_constraint_must_reject():
    from app.domain import ConstraintResult

    with pytest.raises(ValidationError, match="rejected"):
        PortfolioProposal(
            run_id="run-1",
            positions=[{"code": "a", "action": "buy", "weight": 0.1}],
            constraints=[ConstraintResult(rule="t+1", passed=False, detail="停牌")],
        )


def test_portfolio_proposal_rejected_needs_reasons():
    with pytest.raises(ValidationError, match="rejection_reasons"):
        PortfolioProposal(
            run_id="run-1",
            positions=[],
            rejected=True,
            rejection_reasons=[],
        )


# ---------- DataQualityReport ----------

def _quality(**overrides):
    data = {
        "run_id": "run-1",
        "stock_code": "sh.600519",
        "snapshot_id": "snap-1",
        "as_of": PAST,
        "overall": "pass",
    }
    data.update(overrides)
    return data


def test_quality_report_valid():
    q = DataQualityReport(**_quality())
    assert q.overall == "pass"


def test_quality_report_fail_severity_requires_overall_fail():
    from app.domain import QualityCheck

    with pytest.raises(ValidationError, match="overall=fail"):
        DataQualityReport(
            **_quality(
                checks=[QualityCheck(name="missing", severity="fail", passed=False)]
            )
        )


def test_quality_report_warn_not_pass():
    from app.domain import QualityCheck

    with pytest.raises(ValidationError, match="不能为 pass"):
        DataQualityReport(
            **_quality(
                checks=[QualityCheck(name="split", severity="warn", passed=False)]
            )
        )


def test_quality_report_future_as_of_rejected():
    with pytest.raises(ValidationError, match="未来时间"):
        DataQualityReport(**_quality(as_of=FUTURE))
