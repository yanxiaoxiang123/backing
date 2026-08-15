"""BacktestVerdict：确定性回测审计结论（规格决策 1、US-2.2/2.5）。

回测数字必须来自确定性引擎（backtest_executor），LLM 只生成解释文本，
不得修改本契约中的指标（US-2.5 / 规格第四节）。
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.strategy import StrategySpec
from app.domain.version import SCHEMA_VERSION

CheckName = Literal[
    "lookahead",
    "survivorship",
    "out_of_sample",
    "robustness",
    "costs",
    "capacity",
    "market_regimes",
]


class BacktestMetrics(BaseModel):
    """确定性指标。"""

    model_config = ConfigDict(extra="forbid")

    total_return: float
    annual_return: float
    max_drawdown_pct: float = Field(..., le=0, description="最大回撤，必须 ≤ 0")
    sharpe_out_of_sample: float
    turnover_annual: float = Field(default=0.0, ge=0)
    total_cost_bps: float = Field(default=0.0, ge=0)


class BacktestCheck(BaseModel):
    """推广门槛中的一项检查结果。"""

    model_config = ConfigDict(extra="forbid")

    name: CheckName
    passed: bool
    detail: str = ""


class BacktestVerdict(BaseModel):
    """回测审计结论：通过/拒绝及原因（P2 完成标准）。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1)
    strategy: StrategySpec
    snapshot_id: str = Field(..., min_length=1, description="固定数据快照")
    start_date: date
    end_date: date
    benchmark: str = Field(..., min_length=1)
    metrics: BacktestMetrics
    checks: list[BacktestCheck] = Field(default_factory=list)
    passed: bool
    reasons: list[str] = Field(default_factory=list, description="通过/拒绝的原因")
    produced_by: str = Field(..., min_length=1, description="产出节点（run_id/step 引用）")
    schema_version: str = Field(default=SCHEMA_VERSION)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "BacktestVerdict":
        if self.start_date > self.end_date:
            raise ValueError("start_date 不能晚于 end_date")
        if not self.passed and not self.reasons:
            raise ValueError("拒绝时必须给出原因")
        if self.passed and not self.reasons:
            raise ValueError("通过时必须给出支持性原因")
        return self
