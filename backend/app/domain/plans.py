"""RunPlan：单次 run 的目标、步骤计划与预算（规格决策 1、5）。"""

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.version import SCHEMA_VERSION


class RunStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class RunBudget(BaseModel):
    """run 执行预算；任一字段超限即自动终止（规格决策 1、US-1.3）。"""

    model_config = ConfigDict(extra="forbid")

    max_rounds: int = Field(default=10, ge=1)
    max_tool_calls: int = Field(default=30, ge=1)
    max_tokens: int = Field(default=100_000, ge=1)
    timeout_s: float = Field(default=600.0, gt=0)
    max_concurrency: int = Field(default=3, ge=1)


class PlanStep(BaseModel):
    """计划中的一步：由 Supervisor 生成，节点间为 checkpoint 边界。"""

    model_config = ConfigDict(extra="forbid")

    order: int = Field(..., ge=1)
    node: str = Field(..., min_length=1, description="执行节点名（如 data_qa/research/strategy_engineer）")
    description: str = Field(..., min_length=1)
    expected_output: str | None = Field(default=None, description="期望输出的 schema 名")


class RunPlan(BaseModel):
    """一次 run 的结构化计划（US-1.1 / US-2.1）。"""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    steps: list[PlanStep] = Field(default_factory=list)
    budget: RunBudget = Field(default_factory=RunBudget)
    status: RunStatus = RunStatus.PLANNED
    thread_id: str | None = None
    snapshot_id: str | None = Field(
        default=None, description="固定数据快照 id，支持结果重放（US-0.2 数据契约）"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = Field(default=SCHEMA_VERSION)

    @model_validator(mode="after")
    def _validate_steps_ordered(self) -> "RunPlan":
        orders = [s.order for s in self.steps]
        if orders != sorted(orders):
            raise ValueError("steps 必须按 order 升序")
        if len(set(orders)) != len(orders):
            raise ValueError("steps 的 order 必须唯一")
        return self
