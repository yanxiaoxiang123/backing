"""add a database-backed execution lease for agent runs

Revision ID: 20260817_02
Revises: 20260817_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260817_02"
down_revision = "20260817_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_runs")}
    if "execution_owner" not in columns:
        op.add_column("agent_runs", sa.Column("execution_owner", sa.String(120), nullable=True))
    if "lease_expires_at" not in columns:
        op.add_column("agent_runs", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_runs")}
    if "lease_expires_at" in columns:
        op.drop_column("agent_runs", "lease_expires_at")
    if "execution_owner" in columns:
        op.drop_column("agent_runs", "execution_owner")
