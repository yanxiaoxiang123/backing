"""store strategy backtest parameters and portfolio-value snapshots"""

import sqlalchemy as sa
from alembic import op


revision = "20260825_01"
down_revision = "20260818_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("backtest_results")}
    if "parameters" not in columns:
        op.add_column("backtest_results", sa.Column("parameters", sa.JSON(), nullable=True))
    if "portfolio_values" not in columns:
        op.add_column(
            "backtest_results", sa.Column("portfolio_values", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("backtest_results")}
    if "portfolio_values" in columns:
        op.drop_column("backtest_results", "portfolio_values")
    if "parameters" in columns:
        op.drop_column("backtest_results", "parameters")
