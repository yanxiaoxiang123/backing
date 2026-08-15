"""StrategySpec：声明式策略契约（规格决策 1、US-2.2）。

禁止任何可执行代码字符串字段；策略必须能被确定性回测引擎
（backtest_executor）直接消费。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.version import SCHEMA_VERSION

UniverseKind = Literal["index", "custom", "watchlist"]
SignalType = Literal["ma_cross", "momentum", "reversal", "breakout", "composite"]
RebalanceFreq = Literal["none", "daily", "weekly", "monthly"]
SizingMethod = Literal["equal_weight", "vol_target", "fixed_fraction"]


class UniverseSpec(BaseModel):
    """股票池定义。"""

    model_config = ConfigDict(extra="forbid")

    kind: UniverseKind
    ref: str = Field(..., min_length=1, description="指数代码 / 自定义股票池 id / 自选列表名")
    codes: list[str] = Field(default_factory=list, description="显式股票代码列表（可选）")


class RiskConstraints(BaseModel):
    """组合硬约束（A 股规则见 cost_model）。"""

    model_config = ConfigDict(extra="forbid")

    max_position_pct: float = Field(default=0.2, gt=0, le=1)
    max_drawdown_pct: float = Field(default=0.15, gt=0, le=1)
    stop_loss_pct: float | None = Field(default=None, gt=0, le=1)
    sector_exposure_cap: float | None = Field(default=None, gt=0, le=1)


class CostModel(BaseModel):
    """A 股成本与成交规则（US-2.2 / 规格第四节）。"""

    model_config = ConfigDict(extra="forbid")

    commission_bp: float = Field(default=2.5, ge=0, description="佣金（万分之）")
    stamp_tax_bp: float = Field(default=5.0, ge=0, description="印花税（卖出，万分之）")
    slippage_bp: float = Field(default=1.0, ge=0, description="滑点（万分之）")
    lot_size: int = Field(default=100, ge=1, description="一手股数")
    t_plus_1: bool = Field(default=True, description="T+1 规则")


class PositionSizing(BaseModel):
    """仓位方法。"""

    model_config = ConfigDict(extra="forbid")

    method: SizingMethod = "equal_weight"
    fraction: float = Field(default=1.0, gt=0, le=1)


class StrategySpec(BaseModel):
    """一份可被确定性引擎执行的声明式策略。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    description: str = ""
    universe: UniverseSpec = Field(
        default_factory=lambda: UniverseSpec(kind="custom", ref="default")
    )
    signal: str = Field(..., min_length=1, description="信号规则名（registry 中已注册的 strategy 名）")
    signal_parameters: dict[str, float | int | str | bool] = Field(
        default_factory=dict, description="信号参数（数值/枚举，禁止代码）"
    )
    rebalance: RebalanceFreq = "weekly"
    position_sizing: PositionSizing = Field(default_factory=PositionSizing)
    risk_constraints: RiskConstraints = Field(default_factory=RiskConstraints)
    cost_model: CostModel = Field(default_factory=CostModel)
    schema_version: str = Field(default=SCHEMA_VERSION)

    @model_validator(mode="after")
    def _validate_signal_parameters_types(self) -> "StrategySpec":
        for key, value in self.signal_parameters.items():
            if not isinstance(value, (float, int, str, bool)):
                raise TypeError(f"signal_parameters[{key!r}] 必须是数值/字符串/布尔，禁止代码对象")
        return self
