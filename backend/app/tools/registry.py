"""Tool Registry：allowlist + 权限 + 参数校验 + 输出大小限制 + 统一 envelope。

调用管线（规格决策 13 安全与权限）：
1. 工具名必须在注册表内（allowlist）
2. 调用方 granted_permissions 必须包含工具所需权限
3. 参数经 input_schema 校验
4. handler 确定性执行（不执行任意宿主代码）
5. 输出大小限制；统一 envelope：data + source_id + as_of + vendor
6. 若提供 stores，则记录 tool_calls 事实（参数 hash、权限、状态、耗时）
"""

import hashlib
import json
import logging
import time
from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from typing import Any

from app.domain.stock_codes import StockCodeError, normalize_stock_code
from app.tools.base import Tool, ToolContext

logger = logging.getLogger(__name__)


def _params_hash(params: dict[str, Any]) -> str:
    canonical = json.dumps(params, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _size_bytes(data: Any) -> int:
    return len(json.dumps(data, ensure_ascii=False, default=str))


def _json_safe(data: Any) -> Any:
    """Normalize tool output before it enters JSON columns or SSE payloads."""
    return json.loads(json.dumps(data, ensure_ascii=False, default=str))


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool]):
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}

    @property
    def allowlist(self) -> set[str]:
        return set(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return sorted(
            (
                {
                    "name": tool.name,
                    "domain": tool.domain,
                    "version": tool.version,
                    "permission": tool.permission.value,
                    "description": tool.description,
                    "input_schema": tool.json_schema(),
                }
                for tool in self._tools.values()
            ),
            key=lambda item: item["name"],
        )

    def invoke(self, name: str, params: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        started = time.perf_counter()
        tool = self._tools.get(name)
        if tool is None:
            return {
                "ok": False,
                "tool": name,
                "error": {"code": "unknown_tool", "message": f"未注册的工具: {name}"},
            }

        # 权限检查（在参数校验之前，避免泄露 schema 细节）
        if tool.permission.value not in context.granted_permissions:
            return self._record_and_return(
                context, tool, params, started,
                {
                    "ok": False,
                    "tool": name,
                    "error": {
                        "code": "permission_denied",
                        "message": (
                            f"工具 {name} 需要权限 {tool.permission.value!r}，"
                            f"当前授权: {sorted(context.granted_permissions)}"
                        ),
                    },
                },
                status="denied",
            )

        effective_params = deepcopy(params)
        try:
            if "stock_code" in effective_params:
                effective_params["stock_code"] = normalize_stock_code(
                    effective_params["stock_code"], db=context.db
                )
            positions = effective_params.get("positions")
            if isinstance(positions, list):
                for position in positions:
                    if isinstance(position, dict) and "code" in position:
                        position["code"] = normalize_stock_code(
                            position["code"], db=context.db
                        )
        except StockCodeError as exc:
            return self._record_and_return(
                context,
                tool,
                params,
                started,
                {
                    "ok": False,
                    "tool": name,
                    "error": {"code": "validation", "message": str(exc)},
                },
                status="failed",
            )

        # 参数校验
        try:
            validated = tool.input_schema.model_validate(effective_params)
        except Exception as exc:
            return self._record_and_return(
                context, tool, effective_params, started,
                {
                    "ok": False,
                    "tool": name,
                    "error": {
                        "code": "validation",
                        "message": f"参数校验失败: {exc}",
                    },
                },
                status="failed",
            )

        # 确定性执行
        try:
            data = tool.handler(validated, context)
        except Exception as exc:
            logger.warning("tool %s handler failed: %s", name, exc)
            return self._record_and_return(
                context, tool, effective_params, started,
                {
                    "ok": False,
                    "tool": name,
                    "error": {
                        "code": "handler",
                        "message": f"工具执行失败: {exc}",
                    },
                },
                status="failed",
            )

        data = _json_safe(data)

        # 输出大小限制
        if _size_bytes(data) > tool.max_output_bytes:
            return self._record_and_return(
                context, tool, effective_params, started,
                {
                    "ok": False,
                    "tool": name,
                    "error": {
                        "code": "output_too_large",
                        "message": f"输出超过 {tool.max_output_bytes} 字节限制",
                    },
                },
                status="failed",
            )

        envelope = {
            "ok": True,
            "tool": name,
            "permission": tool.permission.value,
            "data": data,
            "source_id": data.get("source_id") if isinstance(data, dict) else None,
            "as_of": (
                data.get("as_of").isoformat()
                if isinstance(data, dict) and isinstance(data.get("as_of"), datetime)
                else data.get("as_of") if isinstance(data, dict) else None
            ),
            "vendor": context.vendor,
        }
        return self._record_and_return(
            context, tool, effective_params, started, envelope, status="ok"
        )

    def _record_and_return(
        self,
        context: ToolContext,
        tool: Tool,
        params: dict[str, Any],
        started: float,
        envelope: dict[str, Any],
        *,
        status: str,
    ) -> dict[str, Any]:
        """记录 tool_calls 事实（规格 US-1.4）后返回 envelope。"""
        if context.stores is not None and context.run_id:
            try:
                context.stores.tool_calls.create_tool_call(
                    run_id=context.run_id,
                    tool_name=tool.name,
                    tool_version=tool.version,
                    params_hash=_params_hash(params),
                    params_json=params,
                    permission=tool.permission.value,
                    status=status,
                    result_ref=(
                        envelope.get("source_id")
                        if envelope.get("ok") and envelope.get("source_id")
                        else None
                    ),
                    duration_s=round(time.perf_counter() - started, 4),
                    error=(
                        envelope.get("error", {}).get("message")
                        if not envelope.get("ok")
                        else None
                    ),
                )
            except Exception:
                logger.exception("tool_calls 事实记录失败: %s", tool.name)
        return envelope


def build_registry() -> ToolRegistry:
    """组装全部工具（八域）为默认注册表。"""
    from app.tools.backtest import BACKTEST_TOOLS
    from app.tools.event import EVENT_TOOLS
    from app.tools.execution import EXECUTION_TOOLS
    from app.tools.factor import FACTOR_TOOLS
    from app.tools.fundamental import FUNDAMENTAL_TOOLS
    from app.tools.market import MARKET_TOOLS
    from app.tools.portfolio import PORTFOLIO_TOOLS
    from app.tools.strategy import STRATEGY_TOOLS

    return ToolRegistry(
        MARKET_TOOLS
        + FUNDAMENTAL_TOOLS
        + EVENT_TOOLS
        + FACTOR_TOOLS
        + STRATEGY_TOOLS
        + BACKTEST_TOOLS
        + PORTFOLIO_TOOLS
        + EXECUTION_TOOLS
    )


DEFAULT_REGISTRY = build_registry()
