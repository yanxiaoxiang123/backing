"""add performance indexes for queries and background sweeps

Revision ID: 20260910_01
Revises: 20260826_01
"""

import sqlalchemy as sa
from alembic import op

revision = "20260910_01"
down_revision = "20260826_01"
branch_labels = None
depends_on = None


def _get_existing_indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    # 1. backtest_results.strategy_id
    if "ix_backtest_results_strategy_id" not in _get_existing_indexes("backtest_results"):
        op.create_index(
            "ix_backtest_results_strategy_id",
            "backtest_results",
            ["strategy_id"],
            unique=False,
        )

    # 2. agent_runs(status, created_at)
    if "ix_agent_runs_status_created" not in _get_existing_indexes("agent_runs"):
        op.create_index(
            "ix_agent_runs_status_created",
            "agent_runs",
            ["status", "created_at"],
            unique=False,
        )

    # 3. agent_chat_turns(status)
    if "ix_agent_chat_turns_status" not in _get_existing_indexes("agent_chat_turns"):
        op.create_index(
            "ix_agent_chat_turns_status",
            "agent_chat_turns",
            ["status"],
            unique=False,
        )

    # 4. tool_calls(step_id) & (status, created_at)
    tool_calls_indexes = _get_existing_indexes("tool_calls")
    if "ix_tool_calls_step_id" not in tool_calls_indexes:
        op.create_index(
            "ix_tool_calls_step_id",
            "tool_calls",
            ["step_id"],
            unique=False,
        )
    if "ix_tool_calls_status_created" not in tool_calls_indexes:
        op.create_index(
            "ix_tool_calls_status_created",
            "tool_calls",
            ["status", "created_at"],
            unique=False,
        )

    # 5. alerts(alert_type, data_ref, created_at) & (is_read, created_at)
    alerts_indexes = _get_existing_indexes("alerts")
    if "ix_alerts_dedup" not in alerts_indexes:
        op.create_index(
            "ix_alerts_dedup",
            "alerts",
            ["alert_type", "data_ref", "created_at"],
            unique=False,
        )
    if "ix_alerts_unread" not in alerts_indexes:
        op.create_index(
            "ix_alerts_unread",
            "alerts",
            ["is_read", "created_at"],
            unique=False,
        )

    # 6. jobs(status, created_at)
    if "ix_jobs_status_created" not in _get_existing_indexes("jobs"):
        op.create_index(
            "ix_jobs_status_created",
            "jobs",
            ["status", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    # 6. jobs
    if "ix_jobs_status_created" in _get_existing_indexes("jobs"):
        op.drop_index("ix_jobs_status_created", table_name="jobs")

    # 5. alerts
    alerts_indexes = _get_existing_indexes("alerts")
    if "ix_alerts_unread" in alerts_indexes:
        op.drop_index("ix_alerts_unread", table_name="alerts")
    if "ix_alerts_dedup" in alerts_indexes:
        op.drop_index("ix_alerts_dedup", table_name="alerts")

    # 4. tool_calls
    tool_calls_indexes = _get_existing_indexes("tool_calls")
    if "ix_tool_calls_status_created" in tool_calls_indexes:
        op.drop_index("ix_tool_calls_status_created", table_name="tool_calls")
    if "ix_tool_calls_step_id" in tool_calls_indexes:
        op.drop_index("ix_tool_calls_step_id", table_name="tool_calls")

    # 3. agent_chat_turns
    if "ix_agent_chat_turns_status" in _get_existing_indexes("agent_chat_turns"):
        op.drop_index("ix_agent_chat_turns_status", table_name="agent_chat_turns")

    # 2. agent_runs
    if "ix_agent_runs_status_created" in _get_existing_indexes("agent_runs"):
        op.drop_index("ix_agent_runs_status_created", table_name="agent_runs")

    # 1. backtest_results
    if "ix_backtest_results_strategy_id" in _get_existing_indexes("backtest_results"):
        op.drop_index("ix_backtest_results_strategy_id", table_name="backtest_results")
