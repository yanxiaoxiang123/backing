"""Add composite index to backtest_trades

Revision ID: 20260316_02
Revises: 20260316_01
Create Date: 2026-03-16 17:00:00
"""

from alembic import op


revision = "20260316_02"
down_revision = "20260316_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add composite index for backtest_trades table
    op.create_index(
        "idx_backtest_trades_result_stock",
        "backtest_trades",
        ["backtest_result_id", "stock_code"],
    )


def downgrade() -> None:
    op.drop_index("idx_backtest_trades_result_stock", table_name="backtest_trades")
