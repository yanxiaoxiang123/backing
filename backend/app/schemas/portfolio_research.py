"""Explicit, long-only target allocations for reproducible portfolio research."""

from datetime import date
from math import fsum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.backtest_simulation import ExecutionCosts


class PortfolioResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="Portfolio research", min_length=1, max_length=120)
    weights: dict[str, float] = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    initial_capital: float = Field(default=100000, gt=0, le=1e12, allow_inf_nan=False)
    rebalance: Literal["none", "daily", "weekly", "monthly"] = "monthly"
    benchmark: str | None = None
    costs: ExecutionCosts = Field(default_factory=ExecutionCosts)
    corporate_action_mode: Literal["verified", "price_only"] = "verified"
    dividend_tax_rate: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        import re
        from math import isfinite

        if any(not re.fullmatch(r"(?:sh|sz|bj)\.\d{6}", code) for code in weights):
            raise ValueError("Use canonical security codes, e.g. sh.600000")
        if any(not isfinite(weight) or not 0 <= weight <= 1 for weight in weights.values()):
            raise ValueError("Weights must be finite and in [0,1]")
        if not 0 < fsum(weights.values()) <= 1:
            raise ValueError("Total weight must be positive and at most one; remainder stays in cash")
        return dict(sorted(weights.items()))

    @field_validator("benchmark")
    @classmethod
    def validate_benchmark(cls, code: str | None) -> str | None:
        if code is not None:
            cls.validate_weights({code: 1.0})
        return code

    @model_validator(mode="after")
    def validate_period(self) -> "PortfolioResearchRequest":
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 3660:
            raise ValueError("Research period must be ordered and at most ten years")
        return self
