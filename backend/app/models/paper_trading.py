"""模拟盘持久化模型（规格 v2 决策 21-23；US-3.1/3.5）。

订单/成交/资金流水为 append-only 事件（可重放审计）；账户与持仓为
物化投影。所有订单关联 run/approval，可全链路追溯。
"""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.config import Base

ORDER_STATUSES = "('pending_approval', 'approved', 'rejected', 'expired', 'filled', 'cancelled')"
SIDES = "('buy', 'sell')"
ORDER_EVENT_TYPES = "('proposed', 'approved', 'rejected', 'expired', 'cancelled', 'filled')"
CASH_EVENT_TYPES = "('deposit', 'buy', 'sell', 'fee')"


class PaperAccount(Base):
    """模拟盘账户（默认单账户，物化投影；现金可由事件重放重建）。"""

    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(32), unique=True, nullable=False, index=True)
    cash = Column(Float, nullable=False, default=0.0)
    initial_cash = Column(Float, nullable=False, default=1_000_000.0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PaperPosition(Base):
    """模拟盘持仓（物化投影；可由成交事件重放重建）。"""

    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String(32), unique=True, nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=0)
    avg_cost = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PaperOrder(Base):
    """模拟盘订单（生命周期由 paper_order_events 记录，本表为当前状态）。"""

    __tablename__ = "paper_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(64), unique=True, nullable=False, index=True)
    run_id = Column(
        String(64),
        ForeignKey("agent_runs.run_id", name="fk_paper_orders_run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approval_id = Column(
        Integer,
        ForeignKey("approvals.id", name="fk_paper_orders_approval_id", ondelete="SET NULL"),
        nullable=True,
    )
    stock_code = Column(String(32), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    limit_price = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="pending_approval")
    target_trade_date = Column(String(10), nullable=True)  # 撮合窗口（审批后下一交易日）
    trigger_note = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(f"side IN {SIDES}", name="ck_paper_orders_side"),
        CheckConstraint(f"status IN {ORDER_STATUSES}", name="ck_paper_orders_status"),
        CheckConstraint("quantity > 0", name="ck_paper_orders_qty_pos"),
    )


class PaperOrderEvent(Base):
    """订单生命周期 append-only 事件（proposed/approved/rejected/expired/cancelled/filled）。"""

    __tablename__ = "paper_order_events"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(
        String(64),
        ForeignKey("paper_orders.order_id", name="fk_order_events_order_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq = Column(Integer, nullable=False)
    event_type = Column(String(20), nullable=False)
    detail_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("order_id", "seq", name="uq_order_events_order_seq"),
        CheckConstraint(f"event_type IN {ORDER_EVENT_TYPES}", name="ck_order_events_type"),
    )


class PaperFill(Base):
    """模拟盘成交（append-only；与订单、审批、run 关联）。"""

    __tablename__ = "paper_fills"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(
        String(64),
        ForeignKey("paper_orders.order_id", name="fk_fills_order_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fill_seq = Column(Integer, nullable=False)
    trade_date = Column(String(10), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    commission = Column(Float, nullable=False, default=0.0)
    stamp_tax = Column(Float, nullable=False, default=0.0)
    transfer_fee = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("order_id", "fill_seq", name="uq_fills_order_seq"),
        CheckConstraint("quantity > 0", name="ck_fills_qty_pos"),
        CheckConstraint("price > 0", name="ck_fills_price_pos"),
    )


class PaperCashEvent(Base):
    """模拟盘资金流水（append-only；net 变动：买入为负、卖出/入金为正）。"""

    __tablename__ = "paper_cash_events"

    id = Column(Integer, primary_key=True, index=True)
    seq = Column(Integer, nullable=False)
    event_type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    order_id = Column(String(64), nullable=True)
    detail_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("seq", name="uq_cash_events_seq"),
        CheckConstraint(f"event_type IN {CASH_EVENT_TYPES}", name="ck_cash_events_type"),
    )
