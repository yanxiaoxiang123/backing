"""execution.paper.* 工具：模拟盘占位（必须人工审批；P3 实现前不成交）。

权限 approval：未经人工审批一律拒绝（规格决策 13；US-2.3 审批卡）。
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.tools.base import Permission, Tool, ToolContext

PaperAction = Literal["buy", "sell"]


class PaperOrderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1)
    action: PaperAction
    shares: int = Field(..., ge=100, multiple_of=100)
    price: float = Field(..., gt=0)
    expires_in_s: int = Field(default=3600, ge=60)


def _paper_order(params: PaperOrderParams, context: ToolContext) -> dict:
    # 权限在 invoke 管线已检查（approval）；此处为确定性占位实现。
    return {
        "source_id": f"paper-order:{context.run_id or 'unknown'}",
        "as_of": datetime.now(timezone.utc),
        "vendor": context.vendor,
        "accepted": True,
        "queue": "paper",
        "code": params.code,
        "action": params.action,
        "shares": params.shares,
        "price": params.price,
        "note": "已入模拟盘队列（P3 paper broker 实现前为占位，不产生真实成交）",
    }


EXECUTION_TOOLS = [
    Tool(
        name="execution.paper.order",
        domain="execution.paper",
        version="0.1.0",
        permission=Permission.APPROVAL,
        description="模拟盘委托（必须人工审批；P3 前为占位）",
        input_schema=PaperOrderParams,
        handler=_paper_order,
    ),
]
