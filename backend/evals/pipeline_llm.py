"""当前 Agent 流水线的评测适配器（任务 03，live 集成时使用）。

把 AgentOrchestrator.run 的输出转换为评测用结构化 dict：
``{"claims": [...], "tokens_used": ...}``。
回放模式下不会被调用（默认 mock/缓存）。
"""

from typing import Any

from app.agent.orchestrator import AgentOrchestrator


def pipeline_llm(case: dict[str, Any]) -> dict[str, Any] | None:
    """对 golden case 跑当前流水线并返回评测用结构化结果。"""
    orchestrator = AgentOrchestrator(mode="standard")
    if not orchestrator.is_available:
        return None
    result = orchestrator.run(
        stock_code=case["stock_code"],
        stock_name="",
        query=case.get("objective", ""),
    )
    # OrchestratorResult → 结构化 claims 的适配（保守映射，缺失则返回 None）
    opinions = getattr(result, "opinions", None) or []
    claims = []
    for opinion in opinions:
        if isinstance(opinion, dict) and opinion.get("conclusion"):
            claims.append(
                {
                    "claim": str(opinion.get("conclusion")),
                    "category": "technical",
                    "direction": None,
                    "confidence": float(opinion.get("confidence", 0.5)),
                    "evidence": [],
                    "hypothesis": True,
                }
            )
    if not claims:
        return None
    return {"claims": claims, "tokens_used": None}
