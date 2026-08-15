"""agent runtime tables: agent_runs, agent_steps, tool_calls, artifacts, approvals

Revision ID: 20260815_01
Revises: 20260323_01
Create Date: 2026-08-15

规格决策 6/7（SQLite-first + repository 接口）：
- agent_runs：run 事实（run_id 唯一、状态机 CheckConstraint）
- agent_steps：节点执行事实，(run_id, seq) 唯一（幂等重放）
- tool_calls：类型化工具调用（权限/状态枚举 + 参数 hash）
- artifacts：证据与产物（source_id/as_of/schema version）
- approvals：人工审批事实（pending/approved/rejected/expired）
"""

import sqlalchemy as sa
from alembic import op

revision = "20260815_01"
down_revision = "20260323_01"
branch_labels = None
depends_on = None


def _table_names(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    existing = _table_names(bind)

    if "agent_runs" not in existing:
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("objective", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("budget_json", sa.JSON(), nullable=True),
            sa.Column("thread_id", sa.String(length=64), nullable=True),
            sa.Column("snapshot_id", sa.String(length=64), nullable=True),
            sa.Column("model_version", sa.String(length=100), nullable=True),
            sa.Column("harness_version", sa.String(length=100), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "status IN ('planned', 'running', 'completed', 'failed', "
                "'cancelled', 'superseded')",
                name="ck_agent_runs_status",
            ),
        )
        op.create_index("ix_agent_runs_id", "agent_runs", ["id"])
        op.create_index("ix_agent_runs_run_id", "agent_runs", ["run_id"], unique=True)

    if "agent_steps" not in existing:
        op.create_table(
            "agent_steps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "run_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "agent_runs.run_id", name="fk_agent_steps_run_id", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("node", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("input_summary", sa.Text(), nullable=True),
            sa.Column("output_schema", sa.String(length=100), nullable=True),
            sa.Column("output_json", sa.JSON(), nullable=True),
            sa.Column("retries", sa.Integer(), nullable=False),
            sa.Column("duration_s", sa.Float(), nullable=True),
            sa.Column("tokens_used", sa.Integer(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("run_id", "seq", name="uq_agent_steps_run_seq"),
            sa.CheckConstraint(
                "status IN ('pending', 'running', 'completed', 'failed')",
                name="ck_agent_steps_status",
            ),
            sa.CheckConstraint("retries >= 0", name="ck_agent_steps_retries_nonneg"),
        )
        op.create_index("ix_agent_steps_id", "agent_steps", ["id"])
        op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])

    if "tool_calls" not in existing:
        op.create_table(
            "tool_calls",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "run_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "agent_runs.run_id", name="fk_tool_calls_run_id", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column(
                "step_id",
                sa.Integer(),
                sa.ForeignKey(
                    "agent_steps.id", name="fk_tool_calls_step_id", ondelete="SET NULL"
                ),
                nullable=True,
            ),
            sa.Column("tool_name", sa.String(length=100), nullable=False),
            sa.Column("tool_version", sa.String(length=50), nullable=True),
            sa.Column("params_hash", sa.String(length=64), nullable=False),
            sa.Column("params_json", sa.JSON(), nullable=False),
            sa.Column("permission", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("result_ref", sa.String(length=255), nullable=True),
            sa.Column("duration_s", sa.Float(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.CheckConstraint(
                "permission IN ('read', 'strategy', 'approval')",
                name="ck_tool_calls_permission",
            ),
            sa.CheckConstraint(
                "status IN ('ok', 'failed', 'denied', 'approved', 'rejected')",
                name="ck_tool_calls_status",
            ),
        )
        op.create_index("ix_tool_calls_id", "tool_calls", ["id"])
        op.create_index("ix_tool_calls_run_id", "tool_calls", ["run_id"])

    if "artifacts" not in existing:
        op.create_table(
            "artifacts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "run_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "agent_runs.run_id", name="fk_artifacts_run_id", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column("artifact_type", sa.String(length=50), nullable=False),
            sa.Column("uri", sa.String(length=500), nullable=False),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.Column("source_id", sa.String(length=255), nullable=True),
            sa.Column("as_of", sa.DateTime(), nullable=True),
            sa.Column("schema_version", sa.String(length=20), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
        )
        op.create_index("ix_artifacts_id", "artifacts", ["id"])
        op.create_index("ix_artifacts_run_id", "artifacts", ["run_id"])

    if "approvals" not in existing:
        op.create_table(
            "approvals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "run_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "agent_runs.run_id", name="fk_approvals_run_id", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("direction", sa.String(length=20), nullable=True),
            sa.Column("target_position_pct", sa.Float(), nullable=True),
            sa.Column("risk_summary", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("decided_by", sa.String(length=100), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'approved', 'rejected', 'expired')",
                name="ck_approvals_status",
            ),
        )
        op.create_index("ix_approvals_id", "approvals", ["id"])
        op.create_index("ix_approvals_run_id", "approvals", ["run_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    for table in ("approvals", "artifacts", "tool_calls", "agent_steps", "agent_runs"):
        if table in tables:
            op.drop_table(table)
