"""add missing indexes for paper_orders and paper_cash_events

Revision ID: 20261014_01
Revises: 20260910_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20261014_01"
down_revision = "20260910_01"
branch_labels = None
depends_on = None


def _get_existing_indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    # 1. paper_orders.approval_id
    if "ix_paper_orders_approval_id" not in _get_existing_indexes("paper_orders"):
        op.create_index(
            "ix_paper_orders_approval_id",
            "paper_orders",
            ["approval_id"],
            unique=False,
        )

    # 2. paper_cash_events.order_id
    if "ix_paper_cash_events_order_id" not in _get_existing_indexes("paper_cash_events"):
        op.create_index(
            "ix_paper_cash_events_order_id",
            "paper_cash_events",
            ["order_id"],
            unique=False,
        )


def downgrade() -> None:
    # 2. paper_cash_events.order_id
    if "ix_paper_cash_events_order_id" in _get_existing_indexes("paper_cash_events"):
        op.drop_index("ix_paper_cash_events_order_id", table_name="paper_cash_events")

    # 1. paper_orders.approval_id
    if "ix_paper_orders_approval_id" in _get_existing_indexes("paper_orders"):
        op.drop_index("ix_paper_orders_approval_id", table_name="paper_orders")
