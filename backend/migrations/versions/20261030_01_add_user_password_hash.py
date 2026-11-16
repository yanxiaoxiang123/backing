"""add users.password_hash for browser account login

Revision ID: 20261030_01
Revises: 20261014_01

密码哈希由启动引导写入（app/services/auth_users.py）。迁移前已有的
default 用户 password_hash 为 NULL，无法用密码登录，也不会影响 API Key 认证。
"""

import sqlalchemy as sa
from alembic import op

revision = "20261030_01"
down_revision = "20261014_01"
branch_labels = None
depends_on = None


def _user_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if "users" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("users")}


def upgrade() -> None:
    if "password_hash" not in _user_columns():
        op.add_column(
            "users",
            sa.Column("password_hash", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    if "password_hash" in _user_columns():
        op.drop_column("users", "password_hash")
