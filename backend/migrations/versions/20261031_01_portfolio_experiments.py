"""Persist reproducible shared-cash portfolio experiments."""

import sqlalchemy as sa
from alembic import op

revision = "20261031_01"
down_revision = "20261030_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_experiments",
        sa.Column("experiment_id", sa.String(32), primary_key=True),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("result_sha256", sa.String(64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_portfolio_experiments_owner_created", "portfolio_experiments", ["owner", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_experiments_owner_created", table_name="portfolio_experiments")
    op.drop_table("portfolio_experiments")
