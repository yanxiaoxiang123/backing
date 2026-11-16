"""Persist execution assumptions and immutable backtest inputs."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_02"
down_revision = "20261030_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backtest_results", sa.Column("execution_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("backtest_results", "execution_metadata")
