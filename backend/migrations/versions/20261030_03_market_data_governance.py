"""Versioned market bars, calendars and point-in-time metadata."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_03"
down_revision = "20261030_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_data_batches",
        sa.Column("batch_id", sa.String(64), primary_key=True),
        sa.Column("stock_code", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("adjustment", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("adjustment IN ('raw','qfq','hfq','legacy_unknown')", name="ck_market_batch_adjustment"),
        sa.CheckConstraint("row_count > 0 AND start_date <= end_date", name="ck_market_batch_range"),
    )
    op.create_index("ix_market_batch_security_observed", "market_data_batches", ["stock_code", "observed_at"])
    op.create_table(
        "market_daily_bars",
        sa.Column("batch_id", sa.String(64), sa.ForeignKey("market_data_batches.batch_id", name="fk_market_bar_batch", ondelete="CASCADE"), primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        *[sa.Column(key, sa.Numeric(16, 6), nullable=False) for key in ("open", "high", "low", "close")],
        sa.Column("volume", sa.Numeric(22, 2), nullable=False),
        sa.Column("amount", sa.Numeric(22, 2), nullable=True),
        sa.Column("suspended", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_st", sa.Boolean(), nullable=True),
        sa.CheckConstraint("open > 0 AND close > 0 AND low > 0 AND high >= open AND high >= close AND low <= open AND low <= close AND volume >= 0", name="ck_market_bar_ohlcv"),
    )
    op.create_table(
        "trading_sessions",
        sa.Column("exchange", sa.String(8), primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "security_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_code", sa.String(20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("listed_on", sa.Date(), nullable=True),
        sa.Column("delisted_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.UniqueConstraint("stock_code", "checksum", name="uq_security_observation"),
    )
    op.create_index("ix_security_observation_asof", "security_observations", ["stock_code", "observed_at", "effective_date"])
    op.create_table(
        "corporate_action_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_code", sa.String(20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("announced_at", sa.DateTime(), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("stock_code", "kind", "checksum", name="uq_corporate_action_observation"),
    )
    op.create_index("ix_corporate_action_asof", "corporate_action_observations", ["stock_code", "effective_date", "observed_at"])


def downgrade() -> None:
    for table in ("corporate_action_observations", "security_observations", "trading_sessions",
                  "market_daily_bars", "market_data_batches"):
        op.drop_table(table)
