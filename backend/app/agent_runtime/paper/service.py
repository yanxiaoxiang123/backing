"""模拟盘编排服务（规格 v2 决策 21-23；US-3.1/3.2/3.5）。

- decide_approval：审批状态机（approve/reject/expired），联动订单与事件
- run_matching_cycle：每日撮合循环（确定性、可重入、单事务原子）
- ensure_account：默认账户初始化

撮合规则见 ``rules.py``；本服务负责把纯函数规则应用到 DB 状态，
并保证「无审批不成交」「一次性窗口」「T+1」「现金/可用校验」。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agent_runtime.paper.rules import (
    Bar,
    available_to_sell,
    compute_fees,
    match_order,
    price_limit_pct,
)
from app.models.agent_runtime import ApprovalRecord
from app.models.models import DailyKline, Stock
from app.models.paper_trading import (
    PaperAccount,
    PaperCashEvent,
    PaperFill,
    PaperOrder,
    PaperOrderEvent,
    PaperPosition,
)

logger = logging.getLogger(__name__)

DEFAULT_ACCOUNT_ID = "default"
DEFAULT_INITIAL_CASH = 1_000_000.0


def ensure_account(db: Session) -> PaperAccount:
    """默认模拟盘账户（物化投影；现金可由事件重放重建）。"""
    row = (
        db.query(PaperAccount)
        .filter(PaperAccount.account_id == DEFAULT_ACCOUNT_ID)
        .one_or_none()
    )
    if row is None:
        row = PaperAccount(
            account_id=DEFAULT_ACCOUNT_ID,
            cash=DEFAULT_INITIAL_CASH,
            initial_cash=DEFAULT_INITIAL_CASH,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _next_order_event_seq(db: Session, order_id: str) -> int:
    return (
        db.query(func.max(PaperOrderEvent.seq))
        .filter(PaperOrderEvent.order_id == order_id)
        .scalar()
        or 0
    ) + 1


def _next_cash_event_seq(db: Session) -> int:
    return (db.query(func.max(PaperCashEvent.seq)).scalar() or 0) + 1


def _next_trading_day(db: Session, stock_code: str, after: date) -> str | None:
    """股票 K 线日历上的下一交易日（严格晚于 after）。"""
    row = (
        db.query(DailyKline.date)
        .filter(DailyKline.stock_code == stock_code, DailyKline.date > after)
        .order_by(DailyKline.date.asc())
        .first()
    )
    return row[0].isoformat() if row else None


def _find_bar(db: Session, stock_code: str, trade_date: str) -> tuple[Bar | None, float | None]:
    """返回 (target 日 bar, prev_close)；无 bar 或无可比前收盘返回 (None, None)。"""
    rows = (
        db.query(DailyKline)
        .filter(DailyKline.stock_code == stock_code)
        .order_by(DailyKline.date.asc())
        .all()
    )
    target = date.fromisoformat(trade_date)
    prev_close: float | None = None
    bar: Bar | None = None
    for row in rows:
        if row.date < target:
            prev_close = float(row.close)
        elif row.date == target:
            bar = Bar(
                date=trade_date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
            )
            break
    return bar, prev_close


def _has_bar_after(db: Session, stock_code: str, trade_date: str) -> bool:
    return (
        db.query(DailyKline.id)
        .filter(
            DailyKline.stock_code == stock_code,
            DailyKline.date > date.fromisoformat(trade_date),
        )
        .first()
        is not None
    )


def _bought_today(db: Session, stock_code: str, trade_date: str) -> int:
    """当日（T）买入份额：T+1 规则下当日不可卖。"""
    return (
        db.query(func.coalesce(func.sum(PaperFill.quantity), 0))
        .filter(
            PaperFill.trade_date == trade_date,
        )
        .join(PaperOrder, PaperOrder.order_id == PaperFill.order_id)
        .filter(PaperOrder.stock_code == stock_code, PaperOrder.side == "buy")
        .scalar()
        or 0
    )


def decide_approval(
    db: Session,
    approval_id: int,
    decision: str,
    *,
    decided_by: str = "user",
) -> dict[str, Any]:
    """审批状态机：pending → approved/rejected（联动 paper 订单）。

    - approved：订单进入 approved，target_trade_date = 审批后下一交易日
      （一次性窗口；窗口过后未成交则 expired）
    - rejected：订单 rejected
    """
    if decision not in ("approved", "rejected"):
        raise ValueError(f"非法决策: {decision}")
    approval = db.get(ApprovalRecord, approval_id)
    if approval is None:
        raise ValueError(f"审批不存在: {approval_id}")
    if approval.status != "pending":
        raise ValueError(f"审批状态 {approval.status} 不可再决策")

    decided_at = datetime.now(timezone.utc)
    approval.status = decision
    approval.decided_by = decided_by
    approval.decided_at = decided_at

    order = (
        db.query(PaperOrder)
        .filter(PaperOrder.approval_id == approval.id)
        .one_or_none()
    )
    if order is not None:
        if decision == "approved":
            target = _next_trading_day(db, order.stock_code, decided_at.date())
            order.status = "approved"
            order.target_trade_date = target
            db.add(
                PaperOrderEvent(
                    order_id=order.order_id,
                    seq=_next_order_event_seq(db, order.order_id),
                    event_type="approved",
                    detail_json={"target_trade_date": target, "decided_by": decided_by},
                )
            )
            if target:
                # 有效期（展示）：目标撮合日收盘
                approval.expires_at = datetime.combine(
                    date.fromisoformat(target), time(15, 0), tzinfo=timezone.utc
                )
        else:
            order.status = "rejected"
            db.add(
                PaperOrderEvent(
                    order_id=order.order_id,
                    seq=_next_order_event_seq(db, order.order_id),
                    event_type="rejected",
                    detail_json={"decided_by": decided_by},
                )
            )
    db.commit()
    db.refresh(approval)
    return {
        "approval_id": approval.id,
        "status": approval.status,
        "order_id": order.order_id if order else None,
        "target_trade_date": order.target_trade_date if order else None,
        "decided_by": decided_by,
        "decided_at": decided_at.isoformat(),
    }


def _expire_order(db: Session, order: PaperOrder, reason: str) -> None:
    order.status = "expired"
    db.add(
        PaperOrderEvent(
            order_id=order.order_id,
            seq=_next_order_event_seq(db, order.order_id),
            event_type="expired",
            detail_json={"reason": reason},
        )
    )


def _fill_order(
    db: Session,
    account: PaperAccount,
    order: PaperOrder,
    bar: Bar,
    fill_price: float,
    fees: Any,
) -> None:
    """成交：写 fill + 现金事件 + 持仓更新 + 订单终态（单事务）。"""
    notional = round(fill_price * order.quantity, 4)
    fill_seq = (
        db.query(func.max(PaperFill.fill_seq))
        .filter(PaperFill.order_id == order.order_id)
        .scalar()
        or 0
    ) + 1
    db.add(
        PaperFill(
            order_id=order.order_id,
            fill_seq=fill_seq,
            trade_date=bar.date,
            price=fill_price,
            quantity=order.quantity,
            commission=fees.commission,
            stamp_tax=fees.stamp_tax,
            transfer_fee=fees.transfer_fee,
        )
    )
    if order.side == "buy":
        amount = round(-(notional + fees.total), 4)
        event_type = "buy"
    else:
        amount = round(notional - fees.total, 4)
        event_type = "sell"
    db.add(
        PaperCashEvent(
            seq=_next_cash_event_seq(db),
            event_type=event_type,
            amount=amount,
            order_id=order.order_id,
            detail_json={"trade_date": bar.date, "price": fill_price, "quantity": order.quantity},
        )
    )
    account.cash = round(account.cash + amount, 4)

    pos = (
        db.query(PaperPosition)
        .filter(PaperPosition.stock_code == order.stock_code)
        .one_or_none()
    )
    if order.side == "buy":
        if pos is None:
            pos = PaperPosition(
                stock_code=order.stock_code, quantity=order.quantity, avg_cost=fill_price
            )
            db.add(pos)
        else:
            total_cost = pos.avg_cost * pos.quantity + fill_price * order.quantity
            pos.quantity += order.quantity
            pos.avg_cost = round(total_cost / pos.quantity, 4) if pos.quantity else 0.0
    else:
        if pos is not None:
            pos.quantity -= order.quantity
            if pos.quantity <= 0:
                db.delete(pos)

    order.status = "filled"
    db.add(
        PaperOrderEvent(
            order_id=order.order_id,
            seq=_next_order_event_seq(db, order.order_id),
            event_type="filled",
            detail_json={
                "trade_date": bar.date,
                "price": fill_price,
                "quantity": order.quantity,
                "fees": {
                    "commission": fees.commission,
                    "stamp_tax": fees.stamp_tax,
                    "transfer_fee": fees.transfer_fee,
                },
            },
        )
    )


def _resolve_target(db: Session, order: PaperOrder) -> str | None:
    """订单撮合窗口：已设置则用之；否则按审批时间解析下一交易日。

    返回 None 表示数据尚未到达（同步滞后/周末），订单保持 approved 等待。
    """
    if order.target_trade_date:
        return order.target_trade_date
    if order.approval_id is None:
        return None
    approval = db.get(ApprovalRecord, order.approval_id)
    if approval is None or approval.decided_at is None:
        return None
    return _next_trading_day(db, order.stock_code, approval.decided_at.date())


def _match_one(db: Session, account: PaperAccount, order: PaperOrder) -> str:
    """处理单个 approved 订单，返回 'filled' | 'expired' | 'noop'。"""
    target = _resolve_target(db, order)
    if target is None:
        # 下一交易日数据未到（周末/同步滞后）：等待，不消费窗口
        return "noop"
    order.target_trade_date = target

    bar, prev_close = _find_bar(db, order.stock_code, order.target_trade_date)
    if bar is None:
        # 窗口已过（停牌/缺数据）→ 过期；数据未到 → 稍后再试（noop）
        if _has_bar_after(db, order.stock_code, order.target_trade_date):
            _expire_order(db, order, f"窗口过期（{order.target_trade_date} 无行情）")
            return "expired"
        return "noop"
    if prev_close is None:
        _expire_order(db, order, "缺少前收盘价，无法判定涨跌停")
        return "expired"

    stock = (
        db.query(Stock).filter(Stock.code == order.stock_code).one_or_none()
    )
    limit_pct = price_limit_pct(order.stock_code, stock.name if stock else None)

    pos = (
        db.query(PaperPosition)
        .filter(PaperPosition.stock_code == order.stock_code)
        .one_or_none()
    )
    if order.side == "sell":
        available = available_to_sell(
            pos.quantity if pos else 0,
            _bought_today(db, order.stock_code, order.target_trade_date),
        )
        if order.quantity > available:
            _expire_order(db, order, f"T+1 可用不足（可卖 {available}）")
            return "expired"

    notional = round(bar.open * order.quantity, 4)
    fees = compute_fees(order.side, notional)
    if order.side == "buy" and notional + fees.total > account.cash:
        _expire_order(db, order, f"现金不足（可用 {account.cash:.2f}）")
        return "expired"

    decision = match_order(
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        bar=bar,
        prev_close=prev_close,
        limit_pct=limit_pct,
    )
    if not decision.fill:
        _expire_order(db, order, decision.reason)
        return "expired"

    _fill_order(db, account, order, bar, decision.fill_price, decision.fees)
    return "filled"


def run_matching_cycle(db: Session) -> dict[str, int]:
    """每日撮合循环：处理全部 approved 订单（确定性、可重入）。"""
    ensure_account(db)
    account = (
        db.query(PaperAccount)
        .filter(PaperAccount.account_id == DEFAULT_ACCOUNT_ID)
        .one()
    )
    summary = {"processed": 0, "filled": 0, "expired": 0, "noop": 0}
    orders = (
        db.query(PaperOrder)
        .filter(PaperOrder.status == "approved")
        .order_by(PaperOrder.created_at.asc())
        .all()
    )
    for order in orders:
        outcome = _match_one(db, account, order)
        summary[outcome] += 1
        summary["processed"] += 1
    db.commit()
    return summary


def list_orders(db: Session, *, status: str | None = None, limit: int = 100) -> list[dict]:
    query = db.query(PaperOrder)
    if status:
        query = query.filter(PaperOrder.status == status)
    rows = query.order_by(PaperOrder.created_at.desc()).limit(limit).all()
    return [
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
            "trigger_note": row.trigger_note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def account_state(db: Session) -> dict[str, Any]:
    ensure_account(db)
    row = (
        db.query(PaperAccount)
        .filter(PaperAccount.account_id == DEFAULT_ACCOUNT_ID)
        .one()
    )
    positions = [
        {
            "stock_code": p.stock_code,
            "quantity": p.quantity,
            "avg_cost": p.avg_cost,
        }
        for p in db.query(PaperPosition).order_by(PaperPosition.stock_code.asc()).all()
    ]
    return {
        "account_id": row.account_id,
        "cash": row.cash,
        "initial_cash": row.initial_cash,
        "positions": positions,
    }
