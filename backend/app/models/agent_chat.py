"""Agent 工作台聊天持久化模型（规格 2026-08-18 决策 D4）。

三张表：agent_chat_threads / agent_chat_turns / agent_chat_events。
- threads：会话事实（thread_id 唯一、Harness session_id、标题、运行状态、
  最近一次量化 run_id、软归档标记、时间戳；US-C1/C9）。
- turns：一轮用户输入的执行事实（状态机、最终回复、结束原因、错误；
  Idempotency-Key 全局唯一，重复提交返回原 turn；US-C2/C5/C7/C8）。
- events：可重放原始事件（类型、序号、载荷 JSON），(turn_id, seq) 唯一，
  支撑 SSE 断线按 Last-Event-ID 重放不丢不重（US-C3/C6）。

复用既有 agent_runs.thread_id 列（仅补索引，见迁移 20260818_01）。
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.config import Base

THREAD_STATUSES = "('idle', 'running')"
TURN_STATUSES = (
    "('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')"
)


class AgentChatThread(Base):
    """一个聊天会话（左栏列表项；软归档不删数据，可恢复）。"""

    __tablename__ = "agent_chat_threads"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String(64), unique=True, nullable=False, index=True)
    # Harness 侧 session_id（D5：thread_id ↔ session_id 映射可查可恢复）。
    session_id = Column(String(64), unique=True, nullable=True, index=True)
    title = Column(String(255), nullable=True)  # 默认取首条用户消息前 36 字符
    status = Column(String(20), nullable=False, default="idle")
    # 最近一次量化 run（右栏跟随 attach；引用 agent_runs.run_id，不加 FK，
    # 避免 run 清理与会话生命周期耦合——D4 仅要求 turns/events 外键）。
    last_run_id = Column(String(64), nullable=True)
    archived = Column(Boolean, nullable=False, default=False)  # 软归档标记
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            f"status IN {THREAD_STATUSES}", name="ck_agent_chat_threads_status"
        ),
    )


class AgentChatTurn(Base):
    """一轮用户消息的执行事实（单 worker FIFO；取消/中断语义见 US-C5/C7）。"""

    __tablename__ = "agent_chat_turns"

    id = Column(Integer, primary_key=True, index=True)
    turn_id = Column(String(64), unique=True, nullable=False, index=True)
    thread_id = Column(
        String(64),
        ForeignKey(
            "agent_chat_threads.thread_id",
            name="fk_agent_chat_turns_thread_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    user_input = Column(Text, nullable=False)
    context_json = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="queued")
    final_reply = Column(Text, nullable=True)  # 助手最终 Markdown 回复
    finish_reason = Column(String(50), nullable=True)  # stop/tool_calls/error/...
    error = Column(Text, nullable=True)
    # US-C8 幂等提交：全局唯一；允许 NULL（未带 key 的旧客户端互不冲突）。
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            f"status IN {TURN_STATUSES}", name="ck_agent_chat_turns_status"
        ),
    )


class AgentChatEvent(Base):
    """turn 内一条可重放原始事件（reasoning/assistant/tool_call/tool_result 等）。"""

    __tablename__ = "agent_chat_events"

    id = Column(Integer, primary_key=True, index=True)
    turn_id = Column(
        String(64),
        ForeignKey(
            "agent_chat_turns.turn_id",
            name="fk_agent_chat_events_turn_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    seq = Column(Integer, nullable=False)  # turn 内单调递增，重放游标
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("turn_id", "seq", name="uq_agent_chat_events_turn_seq"),
    )
