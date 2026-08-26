"""store optional page context for agent chat turns

Revision ID: 20260826_01
Revises: 20260825_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260826_01"
down_revision = "20260825_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("agent_chat_turns")}
    if "context_json" not in columns:
        op.add_column("agent_chat_turns", sa.Column("context_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("agent_chat_turns")}
    if "context_json" in columns:
        op.drop_column("agent_chat_turns", "context_json")
