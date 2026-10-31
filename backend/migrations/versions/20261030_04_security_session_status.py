"""Explicit per-security suspension evidence independent of price bars."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_04"
down_revision = "20261030_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_session_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stock_code", sa.String(20), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("suspended", sa.Boolean(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.UniqueConstraint("stock_code", "date", "provider", "observed_at", "checksum", name="uq_security_session_observation"),
    )
    op.create_index("ix_security_session_asof", "security_session_observations",
                    ["stock_code", "date", "observed_at"])


def downgrade() -> None:
    op.drop_table("security_session_observations")
