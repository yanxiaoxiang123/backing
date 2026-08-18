"""Agent 运行时持久化模型（规格决策 6、7；US-1.4）。

五张表：agent_runs / agent_steps / tool_calls / artifacts / approvals。
run/step/tool/artifact/approval 的读写一律经 app/agent_runtime/stores/
repository 接口，换 PostgreSQL 只换实现类。
"""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.config import Base

RUN_STATUSES = "('planned', 'running', 'completed', 'failed', 'cancelled', 'superseded')"
STEP_STATUSES = "('pending', 'running', 'completed', 'failed')"
TOOL_STATUSES = "('ok', 'failed', 'denied', 'approved', 'rejected')"
APPROVAL_STATUSES = "('pending', 'approved', 'rejected', 'expired')"
PERMISSIONS = "('read', 'strategy', 'approval')"


class AgentRun(Base):
    """一次 run 的事实记录（US-1.1：刷新/断线/重启后按 run_id 恢复）。"""

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    objective = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="planned")
    budget_json = Column(JSON, nullable=True)  # RunBudget 序列化
    thread_id = Column(String(64), nullable=True, index=True)  # T1: 补索引（D4），迁移 20260818_01 创建 ix_agent_runs_thread_id
    snapshot_id = Column(String(64), nullable=True)
    # 研究/回测事实时间点；恢复运行时必须沿用，不能退回当前时间。
    as_of = Column(DateTime, nullable=True)
    execution_owner = Column(String(120), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    model_version = Column(String(100), nullable=True)
    harness_version = Column(String(100), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(f"status IN {RUN_STATUSES}", name="ck_agent_runs_status"),
    )


class AgentStep(Base):
    """run 内一个节点（checkpoint 边界）的执行事实。"""

    __tablename__ = "agent_steps"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        String(64),
        ForeignKey("agent_runs.run_id", name="fk_agent_steps_run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq = Column(Integer, nullable=False)
    node = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    input_summary = Column(Text, nullable=True)
    output_schema = Column(String(100), nullable=True)
    output_json = Column(JSON, nullable=True)
    retries = Column(Integer, nullable=False, default=0)
    duration_s = Column(Float, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_agent_steps_run_seq"),
        CheckConstraint(f"status IN {STEP_STATUSES}", name="ck_agent_steps_status"),
        CheckConstraint("retries >= 0", name="ck_agent_steps_retries_nonneg"),
    )


class ToolCallRecord(Base):
    """一次类型化工具调用（US-1.4 全链路证据；规格决策 13 权限分级）。"""

    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        String(64),
        ForeignKey("agent_runs.run_id", name="fk_tool_calls_run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id = Column(
        Integer,
        ForeignKey("agent_steps.id", name="fk_tool_calls_step_id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_name = Column(String(100), nullable=False)
    tool_version = Column(String(50), nullable=True)
    params_hash = Column(String(64), nullable=False)
    params_json = Column(JSON, nullable=False)
    permission = Column(String(20), nullable=False, default="read")
    status = Column(String(20), nullable=False, default="ok")
    result_ref = Column(String(255), nullable=True)  # artifact uri / 引用
    duration_s = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"permission IN {PERMISSIONS}", name="ck_tool_calls_permission"),
        CheckConstraint(f"status IN {TOOL_STATUSES}", name="ck_tool_calls_status"),
    )


class ArtifactRecord(Base):
    """证据与产物（原始大数据写入 artifact，不直接塞对话；US-0.2）。"""

    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        String(64),
        ForeignKey("agent_runs.run_id", name="fk_artifacts_run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type = Column(String(50), nullable=False)
    uri = Column(String(500), nullable=False)
    checksum = Column(String(64), nullable=True)
    source_id = Column(String(255), nullable=True)
    as_of = Column(DateTime, nullable=True)
    schema_version = Column(String(20), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ApprovalRecord(Base):
    """人工审批事实（高风险操作：模拟下单等；US-2.3 审批卡）。"""

    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        String(64),
        ForeignKey("agent_runs.run_id", name="fk_approvals_run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = Column(String(50), nullable=False)
    summary = Column(Text, nullable=False)
    direction = Column(String(20), nullable=True)
    target_position_pct = Column(Float, nullable=True)
    risk_summary = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    decided_by = Column(String(100), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"status IN {APPROVAL_STATUSES}", name="ck_approvals_status"),
    )
