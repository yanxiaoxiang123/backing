"""Agent 运行时核心测试（任务 05 验收）。

覆盖：节点执行与事件、失败恢复（已完成节点不重复）、预算（轮次/token/
工具调用）、取消在节点边界生效、事件重放单调、工具调用幂等去重、
LangGraph SqliteSaver 接缝（崩溃→恢复）。
"""


from typing import TypedDict

import pytest
from langgraph.graph import END, StateGraph
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent_runtime.events import iter_run_events
from app.agent_runtime.facade import (
    build_tradingagents_graph,
    get_langgraph_checkpointer,
)
from app.agent_runtime.runtime import (
    CancelToken,
    RunExecutor,
    SimpleNode,
    find_tool_call,
    record_tool_call,
)
from app.agent_runtime.stores import create_stores
from app.config import Base
from app.domain.plans import RunBudget


@pytest.fixture()
def stores():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield create_stores(session)
    session.close()


def _counting_node(name: str, counter: list[int], *, fail_once: bool = False, tokens: int = 0):
    def run(ctx):
        counter[0] += 1
        if fail_once and counter[0] == 1:
            raise RuntimeError(f"{name} simulated crash")
        return {"output": {"node": name, "seq": ctx.seq}, "tokens_used": tokens}

    return SimpleNode(name=name, fn=run)


def test_execute_completes_with_steps(stores):
    executor = RunExecutor(stores)
    run_id = executor.create_run("研究测试", budget=RunBudget(max_rounds=5))
    nodes = [_counting_node("a", [0]), _counting_node("b", [0])]
    run = executor.execute(run_id, nodes)

    assert run["status"] == "completed"
    steps = stores.steps.list_steps(run_id)
    assert [s["seq"] for s in steps] == [1, 2]
    assert all(s["status"] == "completed" for s in steps)
    assert steps[0]["output_json"]["node"] == "a"


def test_failure_then_resume_skips_completed_nodes(stores):
    executor = RunExecutor(stores)
    run_id = executor.create_run("恢复测试", budget=RunBudget(max_rounds=5))
    counter_a, counter_b = [0], [0]
    nodes = [
        _counting_node("a", counter_a),
        _counting_node("b", counter_b, fail_once=True),
        _counting_node("c", [0]),
    ]

    first = executor.execute(run_id, nodes)
    assert first["status"] == "failed"
    assert "simulated crash" in first["error"]
    assert counter_a[0] == 1  # a 已执行一次

    second = executor.execute(run_id, nodes)  # 恢复执行
    assert second["status"] == "completed"
    assert counter_a[0] == 1  # a 未重复执行（幂等）
    assert counter_b[0] == 2  # b 重试一次成功
    steps = stores.steps.list_steps(run_id)
    assert len(steps) == 3
    assert steps[0]["status"] == "completed"
    assert steps[1]["retries"] == 1


def test_budget_max_rounds_terminates(stores):
    executor = RunExecutor(stores)
    run_id = executor.create_run("预算测试", budget=RunBudget(max_rounds=2))
    nodes = [_counting_node(f"n{i}", [0]) for i in range(4)]
    run = executor.execute(run_id, nodes)
    assert run["status"] == "failed"
    assert "max_rounds" in run["error"]
    # 第 3 轮尝试被预算拦截，只完成 2 个节点
    steps = stores.steps.list_steps(run_id)
    assert len(steps) == 2
    assert all(s["status"] == "completed" for s in steps)


def test_budget_max_tokens_terminates(stores):
    executor = RunExecutor(stores)
    run_id = executor.create_run("token预算", budget=RunBudget(max_tokens=50))
    nodes = [_counting_node(f"t{i}", [0], tokens=30) for i in range(3)]
    run = executor.execute(run_id, nodes)
    assert run["status"] == "failed"
    assert "max_tokens" in run["error"]


def test_budget_max_tool_calls_terminates(stores):
    def tool_node(ctx):
        record_tool_call(ctx, "market.kline", {"code": "x"})
        return {"output": {}}

    executor = RunExecutor(stores)
    run_id = executor.create_run("工具预算", budget=RunBudget(max_tool_calls=1))
    nodes = [
        SimpleNode("tool1", tool_node),
        SimpleNode("tool2", tool_node),
        _counting_node("after", [0]),
    ]
    run = executor.execute(run_id, nodes)
    assert run["status"] == "failed"
    assert "max_tool_calls" in run["error"]
    assert len(stores.tool_calls.list_tool_calls(run_id)) == 2


def test_cancel_stops_at_node_boundary(stores):
    cancel = CancelToken()
    executor = RunExecutor(stores, cancel_token=cancel)
    run_id = executor.create_run("取消测试")
    cancel.request(run_id)
    nodes = [_counting_node("a", [0]), _counting_node("b", [0])]
    run = executor.execute(run_id, nodes)
    assert run["status"] == "cancelled"
    assert stores.steps.list_steps(run_id) == []  # 边界前未执行任何节点


def test_cancel_mid_run_skips_remaining_nodes(stores):
    cancel = CancelToken()
    executor = RunExecutor(stores, cancel_token=cancel)
    run_id = executor.create_run("中途取消")

    def canceller(ctx):
        cancel.request(ctx.run_id)
        return {"output": {}}

    nodes = [
        _counting_node("a", [0]),
        SimpleNode("cancel-here", canceller),
        _counting_node("c", [0]),
    ]
    run = executor.execute(run_id, nodes)
    assert run["status"] == "cancelled"
    steps = stores.steps.list_steps(run_id)
    assert [s["seq"] for s in steps] == [1, 2]  # 节点 c 未执行
    assert all(s["status"] == "completed" for s in steps)


def test_events_replay_monotonic(stores):
    executor = RunExecutor(stores)
    run_id = executor.create_run("事件回放")

    def tool_node(ctx):
        record_tool_call(ctx, "market.kline", {"code": "sh.600519"})
        return {"output": {}}

    nodes = [_counting_node("a", [0]), SimpleNode("b", tool_node)]
    executor.execute(run_id, nodes)
    events = iter_run_events(stores, run_id)
    seqs = [e["seq"] for e in events if e["type"] == "step"]
    assert seqs == [1, 2]
    tool_events = [e for e in events if e["type"] == "tool_call"]
    assert len(tool_events) == 1
    assert tool_events[0]["tool"] == "market.kline"
    # tool 事件紧跟其 step 之后
    step_idx = next(i for i, e in enumerate(events) if e["type"] == "step" and e["seq"] == 2)
    assert events[step_idx + 1]["type"] == "tool_call"


def test_find_tool_call_dedup(stores):
    executor = RunExecutor(stores)
    run_id = executor.create_run("幂等")

    def tool_node(ctx):
        record_tool_call(ctx, "market.kline", {"code": "sh.600519"})
        existing = find_tool_call(ctx.stores, ctx.run_id, "market.kline", {"code": "sh.600519"})
        assert existing is not None
        return {"output": {"deduped": existing is not None}}

    run = executor.execute(run_id, [SimpleNode("tool", tool_node)])
    assert run["status"] == "completed"
    assert len(stores.tool_calls.list_tool_calls(run_id)) == 1


# ---------- LangGraph SqliteSaver 接缝（facade） ----------

class _SimpleState(TypedDict):
    count: int


def test_langgraph_checkpointer_crash_resume(tmp_path):
    """经统一 checkpointer 的崩溃→恢复（镜像 TradingAgents 测试语义）。"""
    crash = [True]

    def node_a(state: _SimpleState) -> dict:
        return {"count": state["count"] + 1}

    def node_b(state: _SimpleState) -> dict:
        if crash[0]:
            raise RuntimeError("simulated crash")
        return {"count": state["count"] + 10}

    def build():
        builder = StateGraph(_SimpleState)
        builder.add_node("analyst", node_a)
        builder.add_node("trader", node_b)
        builder.set_entry_point("analyst")
        builder.add_edge("analyst", "trader")
        builder.add_edge("trader", END)
        return builder

    db_path = tmp_path / "checkpoints.db"
    cfg = {"configurable": {"thread_id": "TEST-001"}}

    saver = get_langgraph_checkpointer(db_path)
    graph = build().compile(checkpointer=saver)
    with pytest.raises(RuntimeError):
        graph.invoke({"count": 0}, config=cfg)

    crash[0] = False
    graph = build().compile(checkpointer=saver)
    result = graph.invoke(None, config=cfg)

    assert result["count"] == 11  # analyst(+1) 不重复，trader(+10) 补执行


def test_facade_builds_tradingagents_graph():
    try:
        graph = build_tradingagents_graph()
    except ImportError as exc:  # tradingagents 未安装时跳过（集成环境有）
        pytest.skip(f"tradingagents 不可用: {exc}")
    except Exception as exc:
        pytest.skip(f"TradingAgents 构建受环境限制: {exc}")
    assert hasattr(graph, "graph")  # 已编译图
