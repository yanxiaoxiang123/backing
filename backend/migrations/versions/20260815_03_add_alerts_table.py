"""alerts table

Revision ID: 20260815_03
Revises: 20260815_02
Create Date: 2026-08-15

规格 v2 决策 24（US-3.4 告警）：
- alerts：类型/级别/消息 + run/数据事件关联 + 已读状态
"""

import sqlalchemy as sa
from alembic import op

revision = "20260815_03"
down_revision = "20260815_02"
branch_labels = None
depends_on = None


def _table_names(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if "alerts" in _table_names(bind):
        return
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_type", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("data_ref", sa.String(length=255), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("is_read", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.CheckConstraint(
            "alert_type IN ('drawdown', 'data_staleness', 'provider_failure', "
            "'cost_anomaly', 'signal_drift')",
            name="ck_alerts_type",
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="ck_alerts_severity",
        ),
    )
    op.create_index("ix_alerts_id", "alerts", ["id"])
    op.create_index("ix_alerts_run_id", "alerts", ["run_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if "alerts" in _table_names(bind):
        op.drop_table("alerts")
