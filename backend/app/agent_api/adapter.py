"""旧端点 adapter（任务 07；US-1.6）。

``/api/v1/agent/*`` 的同步分析经统一 runtime 执行：产生 ``agent_runs`` +
legacy 节点 step + ``market.kline`` 工具事实；SSE 可重放。行为（响应形状、
LLM 不可用 503 语义）与旧版一致，未新增第二套状态机。
"""

from typing import Any

from app.agent.orchestrator import AgentOrchestrator
from app.agent_runtime.runtime import (
    NodeContext,
    RunExecutor,
    RuntimeNode,
    SimpleNode,
    record_tool_call,
)
from app.agent_runtime.stores import Stores, create_stores


def _legacy_node(request: Any, holder: dict[str, Any]) -> RuntimeNode:
    def run(ctx: NodeContext) -> dict[str, Any]:
        record_tool_call(
            ctx,
            "market.kline",
            {"stock_code": request.stock_code},
            tool_version="baostock",
        )
        orchestrator = AgentOrchestrator(mode=request.mode)
        if not orchestrator.is_available:
            raise ValueError(
                "LLM service not available. Please check API key configuration."
            )
        result = orchestrator.run(
            stock_code=request.stock_code,
            stock_name=request.stock_name or request.stock_code,
        )
        holder["result"] = result
        return {
            "output": {
                "success": result.success,
                "final_signal": result.final_signal,
                "final_confidence": result.final_confidence,
                "stages": [s.get("stage_name") for s in (result.stages or [])],
                "duration_s": result.duration_s,
                "error": result.error,
            },
            "output_schema": "legacy.analysis.summary",
        }

    return SimpleNode("legacy_orchestrator", run)


def run_legacy_analysis(
    db: Any,
    request: Any,
    *,
    stores: Stores | None = None,
    executor: RunExecutor | None = None,
) -> tuple[str, dict[str, Any], Any | None]:
    """同步执行旧版分析并落 run/step/tool 事实；返回 (run_id, final_run, result)。"""
    stores = stores or create_stores(db)
    executor = executor or RunExecutor(stores, db=db)
    run_id = executor.create_run(
        objective=f"legacy agent analysis {request.stock_code} [{request.mode}]",
        model_version="legacy",
    )
    holder: dict[str, Any] = {}
    final = executor.execute(run_id, [_legacy_node(request, holder)])
    return run_id, final, holder.get("result")
