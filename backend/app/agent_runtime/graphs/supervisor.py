"""Supervisor 动态路由图（任务 09；US-2.1/2.2/2.5）。

- Supervisor 生成 ``RunPlan`` 并动态选择专家（Data QA / Research /
  Strategy Engineer / Backtest Critic / Portfolio Risk；可选辩论）
- 专家输出必须通过领域 schema（SchemaGuardedNode 校验、重试一次后失败）
- 回测数字来自确定性引擎（BacktestExecutor），LLM 不得篡改
"""

import re
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent_runtime.runtime import NodeContext, RuntimeNode, SimpleNode
from app.domain.plans import PlanStep, RunBudget, RunPlan

DEFAULT_STOCK_CODE = "sh.600000"

_HIGH_RISK_KEYWORDS = ("高风险", "杠杆", "追涨", "全仓", "重仓", "满仓")


def extract_stock_code(objective: str) -> str:
    """从目标文本提取股票代码（sh./sz. 前缀 + 6 位数字）；缺省返回默认代码。"""
    match = re.search(r"\b(sh|sz)\.\d{6}\b", objective)
    return match.group(0) if match else DEFAULT_STOCK_CODE


class SupervisorPlanProvider:
    """计划提供者：目标 → RunPlan（LLM 或确定性规则）。"""

    def plan(self, objective: str, budget: RunBudget) -> RunPlan:  # pragma: no cover
        raise NotImplementedError


class RuleBasedSupervisor(SupervisorPlanProvider):
    """确定性规则路由（无 LLM，可测试；LLM 版在任务 12 评测门禁接入）。"""

    def plan(self, objective: str, budget: RunBudget) -> RunPlan:
        steps: list[PlanStep] = [
            PlanStep(order=1, node="supervisor", description="制定运行计划"),
            PlanStep(order=2, node="data_qa", description="数据质量检查"),
            PlanStep(order=3, node="research", description="证据采集与研究结论"),
        ]
        order = 4
        if "策略" in objective or "signal" in objective.lower():
            steps.append(
                PlanStep(order=order, node="strategy_engineer", description="生成策略")
            )
            order += 1
        if "回测" in objective or "验证" in objective or "策略" in objective:
            steps.append(
                PlanStep(order=order, node="backtest_critic", description="回测审计")
            )
            order += 1
        # 默认或高风险目标都做组合风控
        steps.append(
            PlanStep(order=order, node="portfolio_risk", description="组合风险与合规")
        )
        return RunPlan(
            run_id="pending",
            objective=objective,
            steps=steps,
            budget=budget,
            status="planned",
        )


def _emit_plan(plan: RunPlan) -> RuntimeNode:
    def run(ctx: NodeContext) -> dict[str, Any]:
        plan.run_id = ctx.run_id
        return {"output": plan.model_dump(mode="json"), "output_schema": "RunPlan"}

    return SimpleNode("supervisor", run)


def build_supervisor_pipeline(
    objective: str,
    budget: RunBudget,
    provider: SupervisorPlanProvider | None = None,
) -> list[RuntimeNode]:
    """按 Supervisor 计划动态组装专家节点列表。"""
    provider = provider or RuleBasedSupervisor()
    plan = provider.plan(objective, budget)

    from app.agent_runtime.graphs.experts import (
        backtest_critic_node,
        data_qa_node,
        portfolio_risk_node,
        research_node,
        strategy_engineer_node,
    )

    node_factory = {
        "data_qa": lambda: data_qa_node(extract_stock_code(objective)),
        "research": lambda: research_node(extract_stock_code(objective)),
        "strategy_engineer": lambda: strategy_engineer_node(extract_stock_code(objective)),
        "backtest_critic": lambda: backtest_critic_node(extract_stock_code(objective)),
        "portfolio_risk": lambda: portfolio_risk_node(extract_stock_code(objective)),
    }
    nodes = [_emit_plan(plan)]
    for step in sorted(plan.steps, key=lambda s: s.order):
        factory = node_factory.get(step.node)
        if factory is not None:
            nodes.append(factory())
    return nodes


def guard(node: RuntimeNode, schema: type[BaseModel], *, retries: int = 1) -> RuntimeNode:
    """输出必须通过 schema；校验失败重试（重跑节点），仍失败则抛错。"""

    def run(ctx: NodeContext) -> dict[str, Any]:
        last_error: ValidationError | None = None
        for _ in range(retries + 1):
            result = node.run(ctx)
            output = result.get("output")
            if output is None:
                return result
            try:
                schema.model_validate(output)
                return result
            except ValidationError as exc:
                last_error = exc
        raise ValueError(
            f"节点 {node.name} 输出未通过 {schema.__name__} 校验: {last_error}"
        )

    return SimpleNode(node.name, run)
