"""execution.paper.* 工具：模拟盘（规格 v2 决策 21-22；US-3.1/3.2）。

- propose_order：提议订单（创建订单 + 待审批卡；必须人工审批）
- cancel_order：撤销未成交订单（pending_approval/approved）
- positions / account / orders：只读账户状态

权限：下单/撤单 approval；查询 read。无审批任何订单不成交（撮合层拒绝
pending 订单）。所有订单关联 run/approval，可全链路追溯。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func

from app.agent_runtime.paper.rules import validate_order
from app.models.agent_runtime import ApprovalRecord
from app.models.models import Stock
from app.models.paper_trading import (
    PaperAccount,
    PaperOrder,
    PaperOrderEvent,
    PaperPosition,
)
from app.tools.base import Permission, Tool, ToolContext

PaperSide = Literal["buy", "sell"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProposeOrderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stock_code: str = Field(..., min_length=1)
    side: PaperSide
    quantity: int = Field(..., gt=0)
    limit_price: float | None = Field(default=None, gt=0)
    trigger_note: str | None = Field(default=None, max_length=500)


def _propose_order(params: ProposeOrderParams, context: ToolContext) -> dict:
    if context.db is None:
        raise ValueError("缺少数据库会话")
    if context.run_id is None:
        raise ValueError("缺少 run 上下文（模拟盘订单必须关联 run）")
    err = validate_order(params.side, params.quantity)
    if err:
        raise ValueError(err)
    stock = (
        context.db.query(Stock)
        .filter(Stock.code == params.stock_code)
        .one_or_none()
    )
    if stock is None:
        raise ValueError(f"未找到股票 {params.stock_code}")

    order_id = f"po-{uuid4().hex[:12]}"
    order = PaperOrder(
        order_id=order_id,
        run_id=context.run_id,
        stock_code=params.stock_code,
        side=params.side,
        quantity=params.quantity,
        limit_price=params.limit_price,
        status="pending_approval",
        trigger_note=params.trigger_note,
    )
    context.db.add(order)
    context.db.flush()
    approval = ApprovalRecord(
        run_id=context.run_id,
        action="paper.order",
        summary=f"{params.side} {params.quantity} 股 {params.stock_code}",
        direction=params.side,
        risk_summary="模拟盘订单：批准后下一交易日开盘价撮合，一次性窗口，用后失效",
        status="pending",
    )
    context.db.add(approval)
    context.db.flush()
    order.approval_id = approval.id
    context.db.add(
        PaperOrderEvent(
            order_id=order_id,
            seq=1,
            event_type="proposed",
            detail_json={
                "side": params.side,
                "quantity": params.quantity,
                "limit_price": params.limit_price,
                "stock_code": params.stock_code,
            },
        )
    )
    context.db.commit()
    return {
        "source_id": f"paper-order:{order_id}",
        "as_of": _now(),
        "vendor": context.vendor,
        "order_id": order_id,
        "approval_id": approval.id,
        "status": "pending_approval",
        "stock_code": params.stock_code,
        "side": params.side,
        "quantity": params.quantity,
        "limit_price": params.limit_price,
        "note": "订单已入模拟盘，等待人工审批；审批后下一交易日开盘价撮合",
    }


class CancelOrderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(..., min_length=1)


def _cancel_order(params: CancelOrderParams, context: ToolContext) -> dict:
    if context.db is None:
        raise ValueError("缺少数据库会话")
    order = (
        context.db.query(PaperOrder)
        .filter(PaperOrder.order_id == params.order_id)
        .one_or_none()
    )
    if order is None:
        raise ValueError(f"未找到订单 {params.order_id}")
    if order.status not in ("pending_approval", "approved"):
        raise ValueError(f"订单状态 {order.status} 不可撤销")
    order.status = "cancelled"
    seq = (
        context.db.query(func.max(PaperOrderEvent.seq))
        .filter(PaperOrderEvent.order_id == order.order_id)
        .scalar()
        or 0
    ) + 1
    context.db.add(
        PaperOrderEvent(
            order_id=order.order_id, seq=seq, event_type="cancelled"
        )
    )
    context.db.commit()
    return {
        "source_id": f"paper-order:{order.order_id}",
        "as_of": _now(),
        "vendor": context.vendor,
        "order_id": order.order_id,
        "status": "cancelled",
        "note": "订单已撤销",
    }


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _positions(params: NoParams, context: ToolContext) -> dict:
    if context.db is None:
        raise ValueError("缺少数据库会话")
    rows = (
        context.db.query(PaperPosition)
        .order_by(PaperPosition.stock_code.asc())
        .all()
    )
    return {
        "source_id": "paper:positions",
        "as_of": _now(),
        "vendor": context.vendor,
        "positions": [
            {
                "stock_code": row.stock_code,
                "quantity": row.quantity,
                "avg_cost": row.avg_cost,
            }
            for row in rows
        ],
    }


def _account(params: NoParams, context: ToolContext) -> dict:
    if context.db is None:
        raise ValueError("缺少数据库会话")
    row = context.db.query(PaperAccount).order_by(PaperAccount.id.asc()).first()
    if row is None:
        raise ValueError("模拟盘账户未初始化")
    return {
        "source_id": "paper:account",
        "as_of": _now(),
        "vendor": context.vendor,
        "account_id": row.account_id,
        "cash": row.cash,
        "initial_cash": row.initial_cash,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


class OrdersParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(default=None)


def _orders(params: OrdersParams, context: ToolContext) -> dict:
    if context.db is None:
        raise ValueError("缺少数据库会话")
    query = context.db.query(PaperOrder)
    if params.status:
        query = query.filter(PaperOrder.status == params.status)
    rows = query.order_by(PaperOrder.created_at.desc()).limit(100).all()
    return {
        "source_id": "paper:orders",
        "as_of": _now(),
        "vendor": context.vendor,
        "orders": [
            {
                "order_id": row.order_id,
                "run_id": row.run_id,
                "approval_id": row.approval_id,
                "stock_code": row.stock_code,
                "side": row.side,
                "quantity": row.quantity,
                "limit_price": row.limit_price,
                "status": row.status,
                "target_trade_date": row.target_trade_date,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }


EXECUTION_TOOLS = [
    Tool(
        name="execution.paper.propose_order",
        domain="execution.paper",
        version="1.0.0",
        permission=Permission.APPROVAL,
        description="提议模拟盘订单（创建订单与待审批卡；必须人工审批）",
        input_schema=ProposeOrderParams,
        handler=_propose_order,
    ),
    Tool(
        name="execution.paper.cancel_order",
        domain="execution.paper",
        version="1.0.0",
        permission=Permission.APPROVAL,
        description="撤销未成交的模拟盘订单（pending_approval/approved）",
        input_schema=CancelOrderParams,
        handler=_cancel_order,
    ),
    Tool(
        name="execution.paper.positions",
        domain="execution.paper",
        version="1.0.0",
        permission=Permission.READ,
        description="查询模拟盘持仓（只读）",
        input_schema=NoParams,
        handler=_positions,
    ),
    Tool(
        name="execution.paper.account",
        domain="execution.paper",
        version="1.0.0",
        permission=Permission.READ,
        description="查询模拟盘账户现金（只读）",
        input_schema=NoParams,
        handler=_account,
    ),
    Tool(
        name="execution.paper.orders",
        domain="execution.paper",
        version="1.0.0",
        permission=Permission.READ,
        description="查询模拟盘订单列表（只读，可按状态过滤）",
        input_schema=OrdersParams,
        handler=_orders,
    ),
]
