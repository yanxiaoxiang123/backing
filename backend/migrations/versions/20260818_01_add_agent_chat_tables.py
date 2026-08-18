"""agent chat tables: agent_chat_threads, agent_chat_turns, agent_chat_events

Revision ID: 20260818_01
Revises: 20260817_02
Create Date: 2026-08-18

规格 2026-08-18 决策 D4（agent 工作台聊天化）：
- agent_chat_threads：会话（thread_id 唯一、Harness session_id、标题、状态、
  最近 run_id、软归档标记、时间戳）
- agent_chat_turns：一轮用户输入的执行事实（Idempotency-Key 全局唯一去重，
  thread_id 外键 -> agent_chat_threads.thread_id）
- agent_chat_events：可重放原始事件（(turn_id, seq) 唯一，turn_id 外键 ->
  agent_chat_turns.turn_id，载荷 JSON）
- agent_runs.thread_id 补索引（右栏“最近 run”按 thread 查询加速；列已存在，
  不重复建列）
"""

import sqlalchemy as sa
from alembic import op

revision = "20260818_01"
down_revision = "20260817_02"
branch_labels = None
depends_on = None

THREAD_STATUSES = "('idle', 'running')"
TURN_STATUSES = (
    "('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')"
)
THREAD_ID_INDEX = "ix_agent_runs_thread_id"


def _table_names(bind) -> set:
    return set(sa.inspect(bind).get_table_names())


def _index_names(bind, table: str) -> set:
    return {ix["name"] for ix in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    existing = _table_names(bind)

    if "agent_chat_threads" not in existing:
        op.create_table(
            "agent_chat_threads",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("thread_id", sa.String(length=64), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("last_run_id", sa.String(length=64), nullable=True),
            sa.Column("archived", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.Column(
                "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.CheckConstraint(
                f"status IN {THREAD_STATUSES}", name="ck_agent_chat_threads_status"
            ),
        )
        op.create_index("ix_agent_chat_threads_id", "agent_chat_threads", ["id"])
        op.create_index(
            "ix_agent_chat_threads_thread_id",
            "agent_chat_threads",
            ["thread_id"],
            unique=True,
        )
        op.create_index(
            "ix_agent_chat_threads_session_id",
            "agent_chat_threads",
            ["session_id"],
            unique=True,
        )

    if "agent_chat_turns" not in existing:
        op.create_table(
            "agent_chat_turns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("turn_id", sa.String(length=64), nullable=False),
            sa.Column(
                "thread_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "agent_chat_threads.thread_id",
                    name="fk_agent_chat_turns_thread_id",
                    ondelete="CASCADE",
                ),
                nullable=False,
            ),
            sa.Column("user_input", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("final_reply", sa.Text(), nullable=True),
            sa.Column("finish_reason", sa.String(length=50), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column(
                "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.CheckConstraint(
                f"status IN {TURN_STATUSES}", name="ck_agent_chat_turns_status"
            ),
        )
        op.create_index("ix_agent_chat_turns_id", "agent_chat_turns", ["id"])
        op.create_index(
            "ix_agent_chat_turns_turn_id",
            "agent_chat_turns",
            ["turn_id"],
            unique=True,
        )
        op.create_index(
            "ix_agent_chat_turns_thread_id", "agent_chat_turns", ["thread_id"]
        )
        op.create_index(
            "ix_agent_chat_turns_idempotency_key",
            "agent_chat_turns",
            ["idempotency_key"],
            unique=True,
        )

    if "agent_chat_events" not in existing:
        op.create_table(
            "agent_chat_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "turn_id",
                sa.String(length=64),
                sa.ForeignKey(
                    "agent_chat_turns.turn_id",
                    name="fk_agent_chat_events_turn_id",
                    ondelete="CASCADE",
                ),
                nullable=False,
            ),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.UniqueConstraint(
                "turn_id", "seq", name="uq_agent_chat_events_turn_seq"
            ),
        )
        op.create_index("ix_agent_chat_events_id", "agent_chat_events", ["id"])
        op.create_index(
            "ix_agent_chat_events_turn_id", "agent_chat_events", ["turn_id"]
        )

    # 既有 agent_runs.thread_id 列补索引（列由 20260815_01 创建，不在此重建）。
    if "agent_runs" in _table_names(bind) and THREAD_ID_INDEX not in _index_names(
        bind, "agent_runs"
    ):
        op.create_index(THREAD_ID_INDEX, "agent_runs", ["thread_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "agent_runs" in tables and THREAD_ID_INDEX in _index_names(bind, "agent_runs"):
        op.drop_index(THREAD_ID_INDEX, table_name="agent_runs")

    for table in ("agent_chat_events", "agent_chat_turns", "agent_chat_threads"):
        if table in tables:
            op.drop_table(table)
