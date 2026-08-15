"""默认流水线（任务 09 之前为确定性占位；之后替换为 Supervisor 动态路由图）。

占位节点保证 API 端到端可用且完全确定性（无 LLM、无网络），
供任务 06/10 联调与评测门禁使用。
"""

from typing import Any

from app.agent_runtime.runtime import (
    NodeContext,
    RuntimeNode,
    SimpleNode,
    record_tool_call,
)
from app.domain.plans import PlanStep, RunPlan
from app.domain.research import ResearchClaim


def _plan_node(ctx: NodeContext) -> dict[str, Any]:
    plan = RunPlan(
        run_id=ctx.run_id,
        objective="演示流水线",
        steps=[
            PlanStep(order=1, node="plan", description="制定计划"),
            PlanStep(order=2, node="research", description="证据采集（占位）"),
            PlanStep(order=3, node="verdict", description="汇总结论（占位）"),
        ],
    )
    return {"output": plan.model_dump(mode="json"), "output_schema": "RunPlan"}


def _research_node(ctx: NodeContext) -> dict[str, Any]:
    record_tool_call(ctx, "strategy.list", {})
    claim = ResearchClaim(
        claim="演示结论：未接入真实证据，仅为假设",
        category="other",
        direction="neutral",
        confidence=0.5,
        hypothesis=True,
    )
    return {
        "output": {"claims": [claim.model_dump(mode="json")]},
        "output_schema": "ResearchClaim[]",
    }


def _verdict_node(ctx: NodeContext) -> dict[str, Any]:
    return {
        "output": {"summary": "演示流水线完成（占位）", "demo": True},
        "output_schema": "demo.verdict",
    }


def default_pipeline() -> list[RuntimeNode]:
    """任务 09 的 Supervisor 图接入前，供 RunExecutor 使用的占位流水线。"""
    return [
        SimpleNode("plan", _plan_node),
        SimpleNode("research", _research_node),
        SimpleNode("verdict", _verdict_node),
    ]
