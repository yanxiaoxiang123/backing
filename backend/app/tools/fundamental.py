"""fundamental.* 工具：基本面（当前接入确定性数据为股票基础信息；财报
数据层接入前，其余基本面工具返回明确"未接入"错误，不伪造数据）。"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import Stock
from app.tools.base import Permission, Tool, ToolContext


class FundamentalStockInfoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_code: str = Field(..., min_length=1)


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
        "as_of": datetime.now(timezone.utc),
        "vendor": context.vendor,
        "code": row.code,
        "name": row.name,
        "market": row.market,
        "list_date": row.list_date.isoformat() if row.list_date else None,
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
]
