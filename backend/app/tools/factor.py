"""factor.* 工具：技术指标（只读，默认开放）。"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.services.indicator_service import indicator_service
from app.tools.base import Permission, Tool, ToolContext


class FactorIndicatorsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_code: str = Field(
        ..., min_length=1, description="股票代码，支持 sh.600000、sh600000、SH600000 或 600000"
    )
    period: str = Field(default="daily", pattern=r"^(daily|weekly|monthly)$")
    limit: int = Field(default=200, ge=1, le=1000)


def _factor_indicators(params: FactorIndicatorsParams, context: ToolContext) -> dict:
    if context.db is None:
        raise ValueError("缺少数据库会话，无法计算指标")
    klines = indicator_service.get_kline_with_indicators(
        context.db,
        params.stock_code,
        period=params.period,
        end_date=context.as_of.date() if context.as_of else None,
    )
    if not klines:
        raise ValueError("无 K 线数据，无法计算指标")
    trimmed = klines[-params.limit :]
    return {
        "source_id": f"factor:{params.stock_code}:{params.period}",
        "as_of": context.as_of or datetime.now(timezone.utc),
        "vendor": context.vendor,
        "stock_code": params.stock_code,
        "rows": len(trimmed),
        "indicators": trimmed,
    }


FACTOR_TOOLS = [
    Tool(
        name="factor.indicators",
        domain="factor",
        version="1.0.0",
        permission=Permission.READ,
        description="技术指标序列（MA/MACD/KDJ/RSI，确定性计算，只读）",
        input_schema=FactorIndicatorsParams,
        handler=_factor_indicators,
    ),
]
