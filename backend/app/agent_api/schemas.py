"""agent_api 请求/响应 schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.plans import RunBudget


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str = Field(..., min_length=1, max_length=2000)
    budget: RunBudget | None = None
    thread_id: str | None = Field(default=None, max_length=64)
    snapshot_id: str | None = Field(default=None, max_length=64)
    as_of: datetime | None = Field(
        default=None,
        description="研究/回测事实时间点；不传则使用创建时间",
    )
    strategy_params: dict | None = Field(
        default=None,
        description="策略参数（如 ma_cross 的 short_period/long_period）；参数修改产生新 run，旧回测永不覆盖（US-2.2/2.8）",
    )
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
