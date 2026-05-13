"""add user watchlist table

Revision ID: 20260319_01
Revises: 20260316_02
Create Date: 2026-03-19 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260319_01"
down_revision = "20260316_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_watchlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
    )
    op.create_index("ix_user_watchlist_id", "user_watchlist", ["id"])
    op.create_index(
        "ix_user_watchlist_stock_code", "user_watchlist", ["stock_code"], unique=True
    )
    op.create_index("idx_added_at", "user_watchlist", ["added_at"])
    # Foreign key
    op.create_foreign_key(
        "fk_watchlist_stock_code",
        "user_watchlist",
        "stocks",
        ["stock_code"],
        ["code"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_watchlist_stock_code", "user_watchlist", type_="foreignkey")
    op.drop_index("idx_added_at", table_name="user_watchlist")
    op.drop_index("ix_user_watchlist_stock_code", table_name="user_watchlist")
    op.drop_index("ix_user_watchlist_id", table_name="user_watchlist")
    op.drop_table("user_watchlist")
