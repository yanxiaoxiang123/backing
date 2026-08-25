"""类型化 Tool Gateway 基础类型（规格决策 3、13；US-2.4）。

- ``Tool``：名称/域/权限/输入 schema/handler 的不可变定义
- ``ToolContext``：db、repository stores、已授权权限、run 归属
- ``Permission``：read（只读工具默认开放）/ strategy（写策略与高成本回测）/
  approval（模拟下单，需人工审批）
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable

from pydantic import BaseModel


class Permission(StrEnum):
    READ = "read"
    STRATEGY = "strategy"
    APPROVAL = "approval"


@dataclass
class ToolContext:
    """一次工具调用的运行上下文。"""

    db: Any = None  # SQLAlchemy Session | None
    stores: Any = None  # app.agent_runtime.stores.Stores | None（用于落 tool_calls 事实）
    run_id: str | None = None
    # 运行事实时间点；内部工具按此时间点过滤数据，避免前视。
    as_of: datetime | None = None
    granted_permissions: set[str] = field(default_factory=lambda: {"read"})
    vendor: str = "backend"


@dataclass(frozen=True)
class Tool:
    """一个严格类型化的工具。handler 只做确定性包装，不发起任意执行。"""

    name: str
    domain: str
    version: str
    permission: Permission
    description: str
    input_schema: type[BaseModel]
    handler: Callable[[BaseModel, ToolContext], dict[str, Any]]
    max_output_bytes: int = 200_000

    def json_schema(self) -> dict[str, Any]:
        return self.input_schema.model_json_schema()
