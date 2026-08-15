"""run 事件重放（US-1.1：SSE 断线重放的事件源；任务 06 消费）。

事件事实层 = agent_steps（节点事件，seq 单调）+ tool_calls（工具事件）。
"""

from typing import Any

from app.agent_runtime.stores import Stores


def iter_run_events(stores: Stores, run_id: str) -> list[dict[str, Any]]:
    """按确定性顺序合并节点事件与工具事件。

    - 每个 step 一条节点事件（seq 升序）；
    - 归属该 step 的 tool_call 紧随其后（按创建顺序）；
    - 无归属的 tool_call 排在最后（按创建顺序）。
    """
    steps = sorted(stores.steps.list_steps(run_id), key=lambda s: s["seq"])
    calls = stores.tool_calls.list_tool_calls(run_id)

    by_step: dict[int, list[dict[str, Any]]] = {}
    orphans: list[dict[str, Any]] = []
    for call in calls:
        if call.get("step_id"):
            by_step.setdefault(call["step_id"], []).append(call)
        else:
            orphans.append(call)

    events: list[dict[str, Any]] = []
    for step in steps:
        events.append(
            {
                "type": "step",
                "seq": step["seq"],
                "node": step["node"],
                "status": step["status"],
                "output_schema": step.get("output_schema"),
                "tokens_used": step.get("tokens_used"),
                "duration_s": step.get("duration_s"),
                "error": step.get("error"),
                "started_at": step.get("started_at"),
                "finished_at": step.get("finished_at"),
            }
        )
        for call in by_step.get(step["id"], []):
            events.append(_tool_event(call))
    for call in orphans:
        events.append(_tool_event(call))
    return events


def _tool_event(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "tool_call",
        "tool": call["tool_name"],
        "permission": call.get("permission"),
        "status": call.get("status"),
        "params_hash": call.get("params_hash"),
        "result_ref": call.get("result_ref"),
        "duration_s": call.get("duration_s"),
        "error": call.get("error"),
        "created_at": call.get("created_at"),
    }
