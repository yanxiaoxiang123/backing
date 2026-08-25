"""TradingAgents gateway vendor（规格 v2 决策 19-20；US-2.7）。

把 TradingAgents 的数据方法路由到后端类型化工具网关（权限分级、证据
envelope、tool_call 落库）。gateway 模式下：

- 已接入方法：经 ``DEFAULT_REGISTRY.invoke`` 取数（只读权限）
- 未接入方法：显式报"未接入"，**不回退**直连 vendor（规格决策 19 硬约束）

``route_to_vendor`` 仅在 AlphaVantageRateLimitError 时回退；gateway 实现
抛普通异常，天然无回退。
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any, Callable

from app.tools.registry import DEFAULT_REGISTRY

logger = logging.getLogger(__name__)

#: TA 方法 → (网关工具名, 位置参数名列表)。未列出的方法显式未接入。
_METHOD_SIGNATURES: dict[str, dict[str, Any]] = {
    "get_stock_data": {
        "tool": "market.kline",
        "pos": ["symbol", "start_date", "end_date"],
    },
    "get_indicators": {
        "tool": "factor.indicators",
        "pos": ["symbol", "indicator", "curr_date", "look_back_days"],
    },
    "get_fundamentals": {
        "tool": "fundamental.financials",
        "pos": ["ticker", "curr_date"],
    },
    "get_news": {
        "tool": "event.news",
        "pos": ["ticker", "start_date", "end_date"],
    },
    "get_lockup_expiry": {
        "tool": "event.announcement",
        "pos": ["ticker", "curr_date"],
    },
}

# 每个执行上下文独立保存 run/db，避免后台线程并发时串单。
_context: ContextVar[Any | None] = ContextVar("ta_gateway_context", default=None)


class _ContextStateProxy:
    """向旧测试/诊断代码提供只读 ``_state['context']`` 兼容视图。"""

    def __getitem__(self, key: str) -> Any:
        if key != "context":
            raise KeyError(key)
        return _context.get()


_state = _ContextStateProxy()


def set_gateway_context(context: Any) -> None:
    _context.set(context)


def clear_gateway_context() -> None:
    _context.set(None)


def _require_context() -> Any:
    context = _context.get()
    if context is None:
        raise ValueError("gateway vendor 未初始化（缺少 run 上下文）")
    return context


def normalize_code(symbol: str) -> str:
    """把 TA 各种代码格式归一为 'sh./sz./bj.' + 6 位。

    'sh.600000' -> 'sh.600000'；'600000' -> 'sh.600000'；'SH600000' -> 'sh.600000'；
    '000001' -> 'sz.000001'；'300750' -> 'sz.300750'；'688017' -> 'sh.688017'。
    """
    raw = (symbol or "").strip().upper()
    if not raw:
        raise ValueError("空股票代码")
    if "." in raw:
        prefix, code = raw.split(".", 1)
        return f"{prefix.lower()}.{code}"
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 6:
        raise ValueError(f"无法解析股票代码: {symbol!r}")
    code = digits[-6:]
    if code.startswith(("6", "9", "688", "689")):
        return f"sh.{code}"
    if code.startswith(("4", "8")):
        return f"bj.{code}"
    return f"sz.{code}"


def _today() -> str:
    from datetime import date

    return date.today().isoformat()


def _map_params(method: str, spec: dict[str, Any], args: tuple, kwargs: dict) -> dict[str, Any]:
    """TA 位置参数 → 网关工具参数。"""
    pos = spec["pos"]
    values = dict(zip(pos, args))
    values.update({k: v for k, v in kwargs.items() if k in pos})
    tool = spec["tool"]

    if tool == "market.kline":
        return {
            "stock_code": normalize_code(values.get("symbol", "")),
            "start_date": values.get("start_date", "2020-01-01"),
            "end_date": values.get("end_date", _today()),
        }
    if tool == "factor.indicators":
        return {
            "stock_code": normalize_code(values.get("symbol", "")),
            "limit": max(1, int(values.get("look_back_days") or 200)),
        }
    if tool == "fundamental.financials":
        return {
            "stock_code": normalize_code(values.get("ticker", "")),
            "periods": 5,
        }
    if tool == "event.news":
        return {
            "stock_code": normalize_code(values.get("ticker", "")),
            "limit": 10,
        }
    if tool == "event.announcement":
        return {
            "stock_code": normalize_code(values.get("ticker", "")),
            "date": (values.get("curr_date") or _today()),
        }
    raise ValueError(f"gateway 未配置方法 {method} 的参数映射")


def _format_result(tool: str, env: dict[str, Any]) -> str:
    """网关 envelope → LLM 可读字符串（TA 工具契约返回 str）。"""
    data = env.get("data") or {}
    payload = dict(data)
    payload.pop("source_id", None)
    payload.pop("as_of", None)
    payload.pop("vendor", None)
    payload.pop("data_version", None)
    lines = [f"[gateway:{tool}] source_id={env.get('source_id')}"]
    lines.append(json.dumps(payload, ensure_ascii=False, default=str)[:4000])
    return "\n".join(lines)


def _make_impl(method: str, spec: dict[str, Any]) -> Callable[..., str]:
    tool = spec["tool"]

    def impl(*args: Any, **kwargs: Any) -> str:
        context = _require_context()
        params = _map_params(method, spec, args, kwargs)
        env = DEFAULT_REGISTRY.invoke(tool, params, context)
        if not env.get("ok"):
            raise ValueError(
                f"网关工具 {tool} 调用失败: "
                f"{env.get('error', {}).get('message', 'unknown')}"
            )
        return _format_result(tool, env)

    impl.__name__ = f"gateway_{method}"
    return impl


def _not_connected(method: str) -> Callable[..., str]:
    def impl(*args: Any, **kwargs: Any) -> str:
        raise ValueError(
            f"TradingAgents 方法 {method} 在 gateway 模式下未接入"
            "（显式失败，不回退直连数据源）"
        )

    impl.__name__ = f"gateway_{method}_unavailable"
    return impl


def install_gateway_vendor() -> None:
    """注册 gateway vendor 并把 TA 配置切到 gateway（无直连回退）。"""
    from tradingagents.dataflows import interface as ta_interface
    from tradingagents.dataflows.config import set_config

    for method, spec in _METHOD_SIGNATURES.items():
        entry = dict(ta_interface.VENDOR_METHODS.get(method, {}))
        entry["gateway"] = _make_impl(method, spec)
        ta_interface.VENDOR_METHODS[method] = entry

    for method in ta_interface.VENDOR_METHODS:
        if method not in _METHOD_SIGNATURES:
            entry = dict(ta_interface.VENDOR_METHODS[method])
            entry.setdefault("gateway", _not_connected(method))
            ta_interface.VENDOR_METHODS[method] = entry

    set_config(
        {
            "data_vendors": {
                category: "gateway" for category in ta_interface.TOOLS_CATEGORIES
            },
            "tool_vendors": {},
        }
    )
    logger.info("TradingAgents gateway vendor installed (all categories -> gateway)")
