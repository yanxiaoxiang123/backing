"""证据契约：全链路证据的公共结构（规格 US-0.2）。"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.version import SCHEMA_VERSION


class Evidence(BaseModel):
    """一条可追溯证据。

    ``as_of`` 语义为「市场当时可获得时间」，必须不晚于当前时间；
    缺失或未来时间在证据类 schema 上直接拒绝。
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, description="证据来源标识（公告/新闻/数据行 id）")
    as_of: datetime = Field(..., description="市场当时可获得时间")
    vendor: str = Field(..., min_length=1, description="数据供应商（如 baostock/akshare）")
    data_version: str = Field(..., min_length=1, description="数据版本")
    summary: str = Field(..., min_length=1, description="证据摘要")
    reference: str | None = Field(
        default=None, description="原文入口（URI/路径），可空"
    )
    schema_version: str = Field(default=SCHEMA_VERSION, description="契约版本")

    @model_validator(mode="after")
    def _validate_as_of_not_future(self) -> "Evidence":
        if self.as_of.tzinfo is None:
            raise ValueError("as_of 必须携带时区（市场当时可获得时间）")
        if self.as_of > datetime.now(timezone.utc):
            raise ValueError("as_of 不能是未来时间（必须是市场当时可获得时间）")
        return self
