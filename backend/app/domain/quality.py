"""DataQualityReport：数据质量审计输出（规格第四节、US-0.2）。"""

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.version import SCHEMA_VERSION

Severity = Literal["warn", "fail"]
Overall = Literal["pass", "warn", "fail"]
Adjustment = Literal["none", "forward", "backward"]


class QualityCheck(BaseModel):
    """单项质量检查。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="如 missing/split/suspension/pit/consistency")
    severity: Severity
    passed: bool
    detail: str = ""


class MissingPeriod(BaseModel):
    """缺失区间（停牌/未上市/数据缺口）。"""

    model_config = ConfigDict(extra="forbid")

    start: date
    end: date
    reason: str = ""


class DataQualityReport(BaseModel):
    """一次 run 使用的数据快照质量结论。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1)
    stock_code: str = Field(..., min_length=1)
    snapshot_id: str = Field(..., min_length=1)
    as_of: datetime = Field(..., description="取数时间")
    checks: list[QualityCheck] = Field(default_factory=list)
    missing_periods: list[MissingPeriod] = Field(default_factory=list)
    adjustment: Adjustment = "none"
    vendor_sources: list[str] = Field(default_factory=list)
    overall: Overall = "pass"
    schema_version: str = Field(default=SCHEMA_VERSION)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "DataQualityReport":
        failed = [c for c in self.checks if not c.passed and c.severity == "fail"]
        warned = [c for c in self.checks if not c.passed and c.severity == "warn"]
        if failed and self.overall != "fail":
            raise ValueError("存在 fail 级检查时必须 overall=fail")
        if not failed and warned and self.overall == "pass":
            raise ValueError("存在 warn 级检查时 overall 不能为 pass")
        if self.as_of.tzinfo is None:
            raise ValueError("as_of 必须携带时区")
        if self.as_of > datetime.now(timezone.utc):
            raise ValueError("as_of 不能是未来时间")
        return self
