"""event.* 工具：新闻、公告（只读，默认开放；规格 v2 决策 17）。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.services import research_data
from app.tools.base import Permission, Tool, ToolContext

MAX_EVENT_ROWS = 50


class EventNewsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_code: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


def _event_news(params: EventNewsParams, context: ToolContext) -> dict:
    entry = research_data.fetch_stock_news(params.stock_code, limit=params.limit)
    return {
        "source_id": entry["source_id"],
        "as_of": entry["as_of"],
        "vendor": entry["vendor"],
        "data_version": entry["data_version"],
        "stock_code": params.stock_code,
        "rows": entry["payload"]["rows"],
        "news": entry["payload"]["news"],
    }


class EventAnnouncementParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_code: str = Field(..., min_length=1)
    date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d"),
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )


def _event_announcement(
    params: EventAnnouncementParams, context: ToolContext
) -> dict:
    entry = research_data.fetch_announcements(params.stock_code, params.date)
    return {
        "source_id": entry["source_id"],
        "as_of": entry["as_of"],
        "vendor": entry["vendor"],
        "data_version": entry["data_version"],
        "stock_code": params.stock_code,
        "date": params.date,
        "rows": entry["payload"]["rows"],
        "announcements": entry["payload"]["announcements"],
    }


EVENT_TOOLS = [
    Tool(
        name="event.news",
        domain="event",
        version="1.0.0",
        permission=Permission.READ,
        description="个股新闻（确定性数据服务，只读，带证据五元组）",
        input_schema=EventNewsParams,
        handler=_event_news,
    ),
    Tool(
        name="event.announcement",
        domain="event",
        version="1.0.0",
        permission=Permission.READ,
        description="指定日期个股公告列表（只读，带证据五元组）",
        input_schema=EventAnnouncementParams,
        handler=_event_announcement,
    ),
]
