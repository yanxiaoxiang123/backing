"""Explicit portfolio intent and the evidence required for deterministic sizing."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator


class RiskModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class RiskTarget(RiskModel):
    stock_code: str
    target_weight: float = Field(ge=0, le=1)
    stop_loss_pct: float | None = Field(default=None, gt=0, lt=1)
    reason: str = Field(min_length=1, max_length=1000)


class RiskLimits(RiskModel):
    max_single_weight: float = Field(default=0.15, gt=0, le=1)
    max_gross_weight: float = Field(default=0.8, gt=0, le=1)
    minimum_cash_weight: float = Field(default=0.1, ge=0, lt=1)
    max_position_loss: float = Field(default=0.01, gt=0, le=1)
    max_portfolio_loss: float = Field(default=0.05, gt=0, le=1)
    max_participation: float = Field(default=0.05, gt=0, le=1)
    max_sector_weight: float | None = Field(default=None, gt=0, le=1)

    def bounded_by(self, policy: "RiskLimits") -> "RiskLimits":
        values = self.model_dump()
        for name, ceiling in policy.model_dump().items():
            if name == "minimum_cash_weight":
                values[name] = max(values[name], ceiling)
            elif ceiling is not None:
                values[name] = min(values[name], ceiling) if values[name] is not None else ceiling
        return RiskLimits(**values)


class PortfolioRiskRequest(RiskModel):
    targets: list[RiskTarget] = Field(min_length=1, max_length=100)
    limits: RiskLimits = Field(default_factory=RiskLimits)

    @model_validator(mode="after")
    def unique_codes(self):
        from app.domain.stock_codes import normalize_stock_code

        for target in self.targets:
            target.stock_code = normalize_stock_code(target.stock_code)
        if len({target.stock_code for target in self.targets}) != len(self.targets):
            raise ValueError("Each security must have exactly one target")
        if sum(target.target_weight for target in self.targets) > 1 + 1e-9:
            raise ValueError("Target weights exceed one")
        return self


class RiskMarketEvidence(RiskModel):
    stock_code: str
    session: date
    expected_session: date
    price: float = Field(gt=0)
    volume: float = Field(ge=0)
    suspended: bool
    locked: bool
    listed: bool
    raw: bool
    batch_ids: list[str] = Field(min_length=1)
    sector: str | None = None


class RiskPositionEvidence(RiskModel):
    quantity: int = Field(ge=0)
    available_to_sell: int = Field(ge=0)

    @model_validator(mode="after")
    def available_is_owned(self):
        if self.available_to_sell > self.quantity:
            raise ValueError("Available shares exceed owned shares")
        return self


class RiskAccountEvidence(RiskModel):
    account_id: str
    observed_at: datetime
    cash: float = Field(ge=0)
    positions: dict[str, RiskPositionEvidence] = Field(default_factory=dict)
    reserved_cash: float = Field(default=0, ge=0)
    pending_codes: list[str] = Field(default_factory=list)
    pending_buys: dict[str, NonNegativeInt] = Field(default_factory=dict)
    kill_switch: bool = False
    source_ids: list[str] = Field(default_factory=list)


class RiskOrder(RiskModel):
    stock_code: str
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    reference_price: float = Field(gt=0)
    estimated_fees: float = Field(ge=0)
    sizing_reasons: list[str] = Field(default_factory=list)
