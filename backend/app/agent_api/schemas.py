"""agent_api 请求/响应 schema。"""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.plans import RunBudget


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str = Field(..., min_length=1, max_length=2000)
    budget: RunBudget | None = None
    thread_id: str | None = Field(default=None, max_length=64)
    snapshot_id: str | None = Field(default=None, max_length=64)
    execute_inline: bool = Field(
        default=False, description="测试/调试用：同步执行到完成后再返回"
    )


class RunResponse(BaseModel):
    run_id: str
    status: str
    events_url: str


class RunListResponse(BaseModel):
    total: int
    runs: list[dict]
