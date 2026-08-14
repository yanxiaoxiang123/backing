"""add user watchlist table (SQLite-safe, batch mode)

Revision ID: 20260319_01
Revises: 20260316_02
Create Date: 2026-03-19 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260319_01"
down_revision = "20260316_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "user_watchlist" not in inspector.get_table_names():
        # Fresh create: declare the foreign key inline in CREATE TABLE so
        # SQLite never needs the unsupported ALTER TABLE ... ADD CONSTRAINT.
        op.create_table(
            "user_watchlist",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("stock_code", sa.String(length=20), nullable=False),
            sa.Column(
                "added_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.ForeignKeyConstraint(
                ["stock_code"], ["stocks.code"], name="fk_watchlist_stock_code"
            ),
        )
    else:
        # Drift repair: a previous run of the broken migration may have left the
        # table behind *without* the FK (SQLite aborted at the ALTER step).
        # Batch mode recreates the table via copy-and-move, attaching the
        # missing constraint without data loss.
        if not inspector.get_foreign_keys("user_watchlist"):
            with op.batch_alter_table("user_watchlist") as batch_op:
                batch_op.create_foreign_key(
                    "fk_watchlist_stock_code",
                    "stocks",
                    ["stock_code"],
                    ["code"],
                )

    # Ensure indexes exist (fresh create adds them; the drift-repair path may
    # already carry them from the failed run).
    inspector = sa.inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes("user_watchlist")}
    if "ix_user_watchlist_id" not in existing:
        op.create_index("ix_user_watchlist_id", "user_watchlist", ["id"])
    if "ix_user_watchlist_stock_code" not in existing:
        op.create_index(
            "ix_user_watchlist_stock_code",
            "user_watchlist",
            ["stock_code"],
            unique=True,
        )
    if "idx_added_at" not in existing:
        op.create_index("idx_added_at", "user_watchlist", ["added_at"])


def downgrade() -> None:
    # Batch drop so SQLite recreates the table without the FK (no ALTER).
    with op.batch_alter_table("user_watchlist") as batch_op:
        batch_op.drop_constraint("fk_watchlist_stock_code", type_="foreignkey")
    op.drop_index("idx_added_at", table_name="user_watchlist")
    op.drop_index("ix_user_watchlist_stock_code", table_name="user_watchlist")
    op.drop_index("ix_user_watchlist_id", table_name="user_watchlist")
    op.drop_table("user_watchlist")
