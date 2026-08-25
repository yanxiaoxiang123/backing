"""persist the point-in-time timestamp used by agent runs

Revision ID: 20260817_01
Revises: 20260815_03
"""

import sqlalchemy as sa
from alembic import op

revision = "20260817_01"
down_revision = "20260815_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_runs")}
    if "as_of" not in columns:
        op.add_column("agent_runs", sa.Column("as_of", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("agent_runs")}
    if "as_of" in columns:
        op.drop_column("agent_runs", "as_of")
