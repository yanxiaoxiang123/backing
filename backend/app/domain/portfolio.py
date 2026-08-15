"""PortfolioProposal：组合风险与合规输出（规格决策 1、US-2.3 风险视图）。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.version import SCHEMA_VERSION

Action = Literal["buy", "hold", "reduce", "sell"]


class PositionAllocation(BaseModel):
    """单票建议仓位。"""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1)
    action: Action
    weight: float = Field(..., ge=0, le=1, description="目标权重（占总组合比例）")
    confidence: float = Field(default=0.5, ge=0, le=1)
    reason: str = ""


class ExposureSummary(BaseModel):
    """暴露摘要。"""

    model_config = ConfigDict(extra="forbid")

    sector_exposure: dict[str, float] = Field(default_factory=dict, description="行业 → 权重")
    single_stock_max_pct: float = Field(default=0.0, ge=0, le=1)
    liquidity_note: str = ""


class ConstraintResult(BaseModel):
    """A 股硬约束检查结果（T+1、一手、涨跌停无法成交、停牌等）。"""

    model_config = ConfigDict(extra="forbid")

    rule: str = Field(..., min_length=1)
    passed: bool
    detail: str = ""


class PortfolioProposal(BaseModel):
    """组合提案；任何约束未过必须标记 rejected 并给出原因。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1)
    positions: list[PositionAllocation] = Field(default_factory=list)
    exposures: ExposureSummary = Field(default_factory=ExposureSummary)
    constraints: list[ConstraintResult] = Field(default_factory=list)
    risk_budget_used_pct: float = Field(default=0.0, ge=0, le=1)
    rejected: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)
    schema_version: str = Field(default=SCHEMA_VERSION)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "PortfolioProposal":
        total = sum(p.weight for p in self.positions)
        if total > 1.0 + 1e-9:
            raise ValueError(f"仓位权重合计 {total:.3f} 超过 1.0")
        if self.rejected and not self.rejection_reasons:
            raise ValueError("rejected 时必须给出 rejection_reasons")
        if not self.rejected and any(not c.passed for c in self.constraints):
            raise ValueError("存在未通过的硬约束时必须标记 rejected")
        return self
