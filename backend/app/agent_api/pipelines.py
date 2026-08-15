"""默认流水线：任务 09 起由 Supervisor 动态路由图驱动。

``default_pipeline(objective)`` 按目标生成 RunPlan 并动态组装专家节点；
无目标时退回最小占位流水线（确定性，供任务 06/10 联调）。
"""

from typing import Any

from app.agent_runtime.graphs import build_supervisor_pipeline
from app.agent_runtime.runtime import (
    NodeContext,
    RuntimeNode,
    SimpleNode,
    record_tool_call,
)
from app.domain.plans import RunBudget
from app.domain.research import ResearchClaim


def _placeholder_node(ctx: NodeContext) -> dict[str, Any]:
    record_tool_call(ctx, "strategy.list", {})
    claim = ResearchClaim(
        claim="演示结论：未提供目标，占位假设",
        category="other",
        direction="neutral",
        confidence=0.5,
        hypothesis=True,
    )
    return {
        "output": {"claims": [claim.model_dump(mode="json")]},
        "output_schema": "ResearchClaim[]",
    }


def default_pipeline(objective: str | None = None) -> list[RuntimeNode]:
    """Supervisor 动态路由；无目标时退回确定性占位。"""
    if objective:
        return build_supervisor_pipeline(objective, RunBudget())
    return [SimpleNode("research_placeholder", _placeholder_node)]
