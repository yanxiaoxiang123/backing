"""ResearchClaim：研究结论 + 证据（US-2.2 全链路证据）。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.evidence import Evidence
from app.domain.version import SCHEMA_VERSION

ClaimCategory = Literal["technical", "fundamental", "news", "policy", "capital_flow", "other"]
ClaimDirection = Literal["bullish", "bearish", "neutral"]


class ResearchClaim(BaseModel):
    """一条研究结论。

    规则（规格决策 1「无证据只能标记为假设」）：
    - 无证据时必须 ``hypothesis=True``；
    - ``hypothesis=True`` 表示该结论未经证据支撑，仅为假设。
    """

    model_config = ConfigDict(extra="forbid")

    claim: str = Field(..., min_length=1)
    category: ClaimCategory
    direction: ClaimDirection | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    hypothesis: bool = Field(
        default=False, description="True 表示无证据支撑、仅为假设"
    )
    schema_version: str = Field(default=SCHEMA_VERSION)

    @model_validator(mode="after")
    def _validate_evidence_rule(self) -> "ResearchClaim":
        if not self.evidence and not self.hypothesis:
            raise ValueError("无证据的结论必须标记 hypothesis=True（只能作为假设）")
        if not self.evidence and self.hypothesis and self.direction not in (None, "neutral"):
            raise ValueError("假设不能声明强方向（bullish/bearish），只能 neutral 或留空")
        return self
