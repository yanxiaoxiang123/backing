"""fundamental.* 工具：基本面（当前接入确定性数据为股票基础信息；财报
数据层接入前，其余基本面工具返回明确"未接入"错误，不伪造数据）。"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import Stock
from app.tools.base import Permission, Tool, ToolContext


class FundamentalStockInfoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_code: str = Field(
        ..., min_length=1, description="股票代码，支持 sh.600000、sh600000、SH600000 或 600000"
    )


def _fundamental_stock_info(
    params: FundamentalStockInfoParams, context: ToolContext
) -> dict:
    if context.db is None:
        raise ValueError("缺少数据库会话，无法查询")
    row = (
        context.db.query(Stock)
        .filter(Stock.code == params.stock_code)
        .one_or_none()
    )
    if row is None:
        raise ValueError(f"未找到股票 {params.stock_code}")
    return {
        "source_id": f"stock:{row.code}",
        "as_of": context.as_of or datetime.now(timezone.utc),
        "vendor": context.vendor,
        "code": row.code,
        "name": row.name,
        "market": row.market,
        "list_date": row.list_date.isoformat() if row.list_date else None,
    }


class FundamentalFinancialsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_code: str = Field(
        ..., min_length=1, description="股票代码，支持 sh.600000、sh600000、SH600000 或 600000"
    )
    periods: int = Field(default=5, ge=1, le=20)


def _fundamental_financials(
    params: FundamentalFinancialsParams, context: ToolContext
) -> dict:
    from app.services import research_data

    entry = research_data.fetch_financials_summary(
        params.stock_code, periods=params.periods, as_of=context.as_of
    )
    return {
        "source_id": entry["source_id"],
        "as_of": entry["as_of"],
        "vendor": entry["vendor"],
        "data_version": entry["data_version"],
        "stock_code": params.stock_code,
        "rows": entry["payload"]["rows"],
        "financials": entry["payload"]["financials"],
    }


FUNDAMENTAL_TOOLS = [
    Tool(
        name="fundamental.stock_info",
        domain="fundamental",
        version="1.0.0",
        permission=Permission.READ,
        description="股票基础信息（代码/名称/市场/上市日期，只读）",
        input_schema=FundamentalStockInfoParams,
        handler=_fundamental_stock_info,
    ),
    Tool(
        name="fundamental.financials",
        domain="fundamental",
        version="1.0.0",
        permission=Permission.READ,
        description="财报摘要（最近 N 个报告期，只读，带证据五元组）",
        input_schema=FundamentalFinancialsParams,
        handler=_fundamental_financials,
    ),
]
