"""Record complete corporate-action and adjustment-factor responses."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_05"
down_revision = "20261030_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_metadata_batches",
        sa.Column("batch_id", sa.String(64), primary_key=True),
        sa.Column("stock_code", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.CheckConstraint("start_date <= end_date", name="ck_market_metadata_range"),
        sa.CheckConstraint("kind IN ('adjustment_factor','dividend')", name="ck_market_metadata_kind"),
    )
    op.create_index("ix_market_metadata_asof", "market_metadata_batches", ["stock_code", "kind", "observed_at"])


def downgrade() -> None:
    op.drop_table("market_metadata_batches")
