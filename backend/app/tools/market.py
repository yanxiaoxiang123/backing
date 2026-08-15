"""market.* 工具：K 线、快照（只读，默认开放）。"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.services.baostock_service import baostock_service
from app.services.indicator_service import indicator_service
from app.tools.base import Permission, Tool, ToolContext

MAX_KLINE_ROWS = 500


class MarketKlineParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_code: str = Field(..., min_length=1)
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


def _market_kline(params: MarketKlineParams, context: ToolContext) -> dict:
    df = baostock_service.get_daily_kline(
        params.stock_code, params.start_date, params.end_date
    )
    if df is None or df.empty:
        raise ValueError("无 K 线数据（数据缺失或日期区间无效）")
    records = df.head(MAX_KLINE_ROWS).to_dict(orient="records")
    return {
        "source_id": f"kline:{params.stock_code}:{params.start_date}:{params.end_date}",
        "as_of": datetime.now(timezone.utc),
        "vendor": context.vendor,
        "stock_code": params.stock_code,
        "rows": len(records),
        "truncated": len(df) > MAX_KLINE_ROWS,
        "kline": records,
    }


class MarketSnapshotParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_code: str = Field(..., min_length=1)
    period: str = Field(default="daily", pattern=r"^(daily|weekly|monthly)$")


def _market_snapshot(params: MarketSnapshotParams, context: ToolContext) -> dict:
    if context.db is None:
        raise ValueError("缺少数据库会话，无法获取快照")
    klines = indicator_service.get_kline_with_indicators(
        context.db, params.stock_code, period=params.period
    )
    if not klines:
        raise ValueError("无行情快照数据")
    latest = klines[-1]
    return {
        "source_id": f"snapshot:{params.stock_code}:{params.period}",
        "as_of": datetime.now(timezone.utc),
        "vendor": context.vendor,
        "stock_code": params.stock_code,
        "period": params.period,
        "latest": latest,
    }


MARKET_TOOLS = [
    Tool(
        name="market.kline",
        domain="market",
        version="1.0.0",
        permission=Permission.READ,
        description="获取日 K 线（确定性数据服务，只读）",
        input_schema=MarketKlineParams,
        handler=_market_kline,
    ),
    Tool(
        name="market.snapshot",
        domain="market",
        version="1.0.0",
        permission=Permission.READ,
        description="获取最新行情快照与技术指标摘要（只读）",
        input_schema=MarketSnapshotParams,
        handler=_market_snapshot,
    ),
]
