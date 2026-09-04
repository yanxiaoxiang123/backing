"""TradingAgents 深度研究子图（规格 v2 决策 19-20；US-2.7）。

Supervisor 路由"深度研究"目标时，把 TradingAgents 图作为运行时子图执行：
- 取数全部经 gateway vendor 走类型化工具网关（权限 + 证据 + tool_call 落库）
- 产出归一为 ResearchClaim 列表 + 报告 artifact（结构化，非自由文本）
- LLM（DeepSeek）只做分析解释，事实来自网关 envelope
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.agent_runtime.runtime import NodeContext, RuntimeNode, SimpleNode
from app.domain.research import ResearchClaim

logger = logging.getLogger(__name__)

_TA_DIR = Path(__file__).resolve().parents[3] / "data" / "ta"  # backend/data/ta

_REPORT_TO_CATEGORY: dict[str, str] = {
    "market_report": "technical",
    "sentiment_report": "news",
    "news_report": "news",
    "fundamentals_report": "fundamental",
    "policy_report": "policy",
    "hot_money_report": "capital_flow",
    "lockup_report": "other",
}


def _ta_config(ctx: NodeContext) -> dict[str, Any]:
    """TradingAgents 配置：DeepSeek LLM + 隔离目录 + 轻量辩论。"""
    import os

    from tradingagents.default_config import DEFAULT_CONFIG

    from app.config import settings

    # TA openai client 从环境变量解析 key；进程内导出（与 backend 同一密钥）
    if settings.DEEPSEEK_API_KEY and not os.environ.get("DEEPSEEK_API_KEY"):
        os.environ["DEEPSEEK_API_KEY"] = settings.DEEPSEEK_API_KEY

    config = dict(DEFAULT_CONFIG)
    config.update(
        {
            "llm_provider": "deepseek",
            "deep_think_llm": settings.DEEPSEEK_MODEL,
            "quick_think_llm": settings.DEEPSEEK_MODEL,
            "api_key": settings.DEEPSEEK_API_KEY or "",
            "checkpoint_enabled": False,
            "results_dir": str(_TA_DIR / "logs"),
            "data_cache_dir": str(_TA_DIR / "cache"),
            "output_language": "Chinese",
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
        }
    )
    return config


def _direction_of(decision: str) -> str:
    text = (decision or "").lower()
    if any(k in text for k in ("bullish", "buy", "看多", "买入", "多头")):
        return "bullish"
    if any(k in text for k in ("bearish", "sell", "看空", "卖出", "空头")):
        return "bearish"
    return "neutral"


def _evidence(
    ctx: NodeContext, stock_code: str, report_key: str, run_id_ref: str
) -> dict[str, Any]:
    now = ctx.as_of or datetime.now(timezone.utc)
    return {
        "source_id": f"ta:{stock_code}:{report_key}",
        "as_of": now,
        "vendor": "TradingAgents+gateway",
        "data_version": "1.0.0",
        "summary": f"TradingAgents 深度研究报告（{report_key}，经类型化网关取数）",
        "reference": f"run:{run_id_ref}",
    }


def _normalize_claims(
    final_state: dict[str, Any], ctx: NodeContext, stock_code: str
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for key, category in _REPORT_TO_CATEGORY.items():
        text = final_state.get(key)
        if text:
            claims.append(
                ResearchClaim(
                    claim=str(text)[:200],
                    category=category,
                    direction="neutral",
                    confidence=0.5,
                    evidence=[_evidence(ctx, stock_code, key, ctx.run_id)],
                ).model_dump(mode="json")
            )
    decision = final_state.get("final_trade_decision") or ""
    if decision:
        claims.append(
            ResearchClaim(
                claim=f"TradingAgents 最终决策：{str(decision)[:120]}",
                category="other",
                direction=_direction_of(str(decision)),
                confidence=0.6,
                evidence=[_evidence(ctx, stock_code, "final_decision", ctx.run_id)],
            ).model_dump(mode="json")
        )
    return claims


def ta_research_node(stock_code: str, objective: str) -> RuntimeNode:
    """TradingAgents 深度研究子图节点（US-2.7）。"""

    def run(ctx: NodeContext) -> dict[str, Any]:
        import tradingagents.graph.trading_graph as ta_graph

        from app.agent_runtime.ta_bridge.vendor import (
            clear_gateway_context,
            install_gateway_vendor,
            set_gateway_context,
        )
        from app.tools.base import ToolContext as GatewayContext

        install_gateway_vendor()
        gateway = GatewayContext(
            db=ctx.db,
            stores=ctx.stores,
            run_id=ctx.run_id,
            granted_permissions={"read"},
            as_of=ctx.as_of,
        )
        set_gateway_context(gateway)
        trade_date = (
            ctx.as_of.strftime("%Y-%m-%d")
            if ctx.as_of
            else date.today().isoformat()
        )
        try:
            graph = ta_graph.TradingAgentsGraph(
                selected_analysts=[
                    "market",
                    "news",
                    "fundamentals",
                    "policy",
                    "lockup",
                ],
                config=_ta_config(ctx),
            )
            final_state, signal = graph.propagate(stock_code, trade_date)
        finally:
            clear_gateway_context()

        claims = _normalize_claims(final_state, ctx, stock_code)
        return {
            "output": {"claims": claims, "signal": signal},
            "output_schema": "ResearchClaim[]",
        }

    return SimpleNode("ta_research", run)
