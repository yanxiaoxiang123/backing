"""paper trading tables: paper_accounts, paper_positions, paper_orders,
paper_order_events, paper_fills, paper_cash_events

Revision ID: 20260815_02
Revises: 20260815_01
Create Date: 2026-08-15

规格 v2 决策 21-23（模拟盘闭环）：
- paper_accounts：默认模拟盘账户（物化投影）
- paper_positions：持仓（物化投影）
- paper_orders：订单当前状态（关联 run/approval）
- paper_order_events：订单生命周期 append-only 事件
- paper_fills：成交 append-only（含费用明细）
- paper_cash_events：资金流水 append-only
"""

import sqlalchemy as sa
from alembic import op

revision = "20260815_02"
down_revision = "20260815_01"
branch_labels = None
depends_on = None


def _table_names(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    existing = _table_names(bind)

    if "paper_accounts" not in existing:
        op.create_table(
            "paper_accounts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("account_id", sa.String(length=32), nullable=False),
            sa.Column("cash", sa.Float(), nullable=False),
            sa.Column("initial_cash", sa.Float(), nullable=False),
            sa.Column(
                "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
        )
        op.create_index("ix_paper_accounts_id", "paper_accounts", ["id"])
        op.create_index(
            "ix_paper_accounts_account_id", "paper_accounts", ["account_id"], unique=True
        )

    if "paper_positions" not in existing:
        op.create_table(
            "paper_positions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("stock_code", sa.String(length=32), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("avg_cost", sa.Float(), nullable=False),
            sa.Column(
                "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
        )
        op.create_index("ix_paper_positions_id", "paper_positions", ["id"])
        op.create_index(
            "ix_paper_positions_stock_code", "paper_positions", ["stock_code"], unique=True
        )

    if "paper_orders" not in existing:
        op.create_table(
            "paper_orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.String(length=64), nullable=False),
            sa.Column(
                "run_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "agent_runs.run_id", name="fk_paper_orders_run_id", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column(
                "approval_id",
                sa.Integer(),
                sa.ForeignKey(
                    "approvals.id", name="fk_paper_orders_approval_id", ondelete="SET NULL"
                ),
                nullable=True,
            ),
            sa.Column("stock_code", sa.String(length=32), nullable=False),
            sa.Column("side", sa.String(length=10), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("limit_price", sa.Float(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("target_trade_date", sa.String(length=10), nullable=True),
            sa.Column("trigger_note", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.Column(
                "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.CheckConstraint(
                "side IN ('buy', 'sell')", name="ck_paper_orders_side"
            ),
            sa.CheckConstraint(
                "status IN ('pending_approval', 'approved', 'rejected', "
                "'expired', 'filled', 'cancelled')",
                name="ck_paper_orders_status",
            ),
            sa.CheckConstraint("quantity > 0", name="ck_paper_orders_qty_pos"),
        )
        op.create_index("ix_paper_orders_id", "paper_orders", ["id"])
        op.create_index("ix_paper_orders_order_id", "paper_orders", ["order_id"], unique=True)
        op.create_index("ix_paper_orders_run_id", "paper_orders", ["run_id"])
        op.create_index("ix_paper_orders_stock_code", "paper_orders", ["stock_code"])

    if "paper_order_events" not in existing:
        op.create_table(
            "paper_order_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "order_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "paper_orders.order_id",
                    name="fk_order_events_order_id",
                    ondelete="CASCADE",
                ),
                nullable=False,
            ),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=20), nullable=False),
            sa.Column("detail_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.UniqueConstraint("order_id", "seq", name="uq_order_events_order_seq"),
            sa.CheckConstraint(
                "event_type IN ('proposed', 'approved', 'rejected', "
                "'expired', 'cancelled', 'filled')",
                name="ck_order_events_type",
            ),
        )
        op.create_index("ix_paper_order_events_id", "paper_order_events", ["id"])
        op.create_index(
            "ix_paper_order_events_order_id", "paper_order_events", ["order_id"]
        )

    if "paper_fills" not in existing:
        op.create_table(
            "paper_fills",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "order_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "paper_orders.order_id", name="fk_fills_order_id", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column("fill_seq", sa.Integer(), nullable=False),
            sa.Column("trade_date", sa.String(length=10), nullable=False),
            sa.Column("price", sa.Float(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("commission", sa.Float(), nullable=False),
            sa.Column("stamp_tax", sa.Float(), nullable=False),
            sa.Column("transfer_fee", sa.Float(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.UniqueConstraint("order_id", "fill_seq", name="uq_fills_order_seq"),
            sa.CheckConstraint("quantity > 0", name="ck_fills_qty_pos"),
            sa.CheckConstraint("price > 0", name="ck_fills_price_pos"),
        )
        op.create_index("ix_paper_fills_id", "paper_fills", ["id"])
        op.create_index("ix_paper_fills_order_id", "paper_fills", ["order_id"])

    if "paper_cash_events" not in existing:
        op.create_table(
            "paper_cash_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=20), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("order_id", sa.String(length=64), nullable=True),
            sa.Column("detail_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.UniqueConstraint("seq", name="uq_cash_events_seq"),
            sa.CheckConstraint(
                "event_type IN ('deposit', 'buy', 'sell', 'fee')",
                name="ck_cash_events_type",
            ),
        )
        op.create_index("ix_paper_cash_events_id", "paper_cash_events", ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    for table in (
        "paper_cash_events",
        "paper_fills",
        "paper_order_events",
        "paper_orders",
        "paper_positions",
        "paper_accounts",
    ):
        if table in tables:
            op.drop_table(table)
