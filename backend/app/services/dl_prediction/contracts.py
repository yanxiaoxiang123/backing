"""Validated requests for asynchronous DL experiments."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.stock_codes import normalize_stock_code

ModelId = Literal["kronos-small", "kronos-base", "timesfm-2.5", "legacy"]


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    stock_code: str
    model: ModelId = "kronos-small"
    kline_days: int = Field(default=256, ge=30, le=512)
    prediction_days: int = Field(default=5, ge=1, le=30)

    @field_validator("stock_code")
    @classmethod
    def stock_identity(cls, value: str) -> str:
        code = normalize_stock_code(value)
        if not code:
            raise ValueError("Invalid stock code")
        return code

    @model_validator(mode="after")
    def model_limits(self):
        if self.model == "legacy":
            if self.prediction_days != 5 or self.kline_days > 250:
                raise ValueError("现有预测器仅支持 5 日预测及 30–250 根历史")
        elif self.kline_days < 60:
            raise ValueError("远程预测模型需要至少 60 根历史 K 线")
        if not self.stock_code.startswith(("sh.", "sz.")):
            raise ValueError("当前数据日历仅支持沪深股票")
        return self


class BacktestExperimentRequest(ExperimentRequest):
    start_date: date
    end_date: date
    initial_capital: float = Field(default=100000, gt=0, le=1e12)

    @model_validator(mode="after")
    def valid_period(self):
        if self.end_date < self.start_date:
            raise ValueError("回测结束日期不能早于开始日期")
        if (self.end_date - self.start_date).days > 3660:
            raise ValueError("单次回测区间不能超过 10 年")
        return self
