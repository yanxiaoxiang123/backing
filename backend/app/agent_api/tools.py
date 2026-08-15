"""工具直调端点（规格决策 2：DSH 插件只调 FastAPI Tool Gateway）。

POST /api/v1/tools/invoke  → 经类型化网关执行单个工具（只读/策略权限；
approval 工具拒绝——模拟下单审批留在后端工作台）。
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import get_current_api_key
from app.config import get_db
from app.tools import DEFAULT_REGISTRY, ToolContext

logger = logging.getLogger(__name__)

router = APIRouter()

#: DSH 对话外壳允许的工具权限（只读 + 策略回测；不含 approval 下单）
GATEWAY_GRANTED = {"read", "strategy"}


class ToolInvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/tools/invoke")
def invoke_tool(
    body: ToolInvokeRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict[str, Any]:
    """直调单个类型化网关工具（证据 envelope 返回；approval 工具拒绝）。"""
    context = ToolContext(db=db, granted_permissions=set(GATEWAY_GRANTED))
    env = DEFAULT_REGISTRY.invoke(body.tool, body.params, context)
    if not env.get("ok") and env.get("error", {}).get("code") == "permission_denied":
        raise HTTPException(status_code=403, detail=env["error"]["message"])
    return env
