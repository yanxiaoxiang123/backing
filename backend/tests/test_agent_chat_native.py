"""Native backend Agent chat runtime tests (no network and no Harness checkout)."""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.agent_chat.policy import ToolScope, TurnToolPolicy, stock_reference
from app.agent_chat.runtime import (
    NativeAgentChatRuntime,
    NativeModelResponse,
    NativeToolCall,
)
from app.agent_chat.seam import RUN_LINKED, TOOL_CALL, TOOL_RESULT, ChatEvent
from app.agent_chat.stores import create_chat_stores
from app.config import Base
from app.models.models import Stock


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/native-chat.db")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add_all([
            Stock(code="sz.000001", name="平安银行", market="sz"),
            Stock(code="sh.600000", name="浦发银行", market="sh"),
            Stock(code="sz.000002", name="万科A", market="sz"),
        ])
        session.commit()
    return factory


class ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.tools_seen = []

    def complete(self, messages, tools, *, emit_text, emit_reasoning, cancel_event):
        self.tools_seen.append([item["function"]["name"] for item in tools])
        response = self.responses.pop(0)
        if response.text:
            emit_text(response.text)
        return response


def _turn(session_factory, message, thread_id="thread-native", turn_id="turn-native"):
    session = session_factory()
    stores = create_chat_stores(session)
    stores.threads.create_thread(
        thread_id=thread_id,
        session_id=thread_id,
        title=None,
        status="running",
        archived=False,
    )
    row = stores.turns.create_turn(
        turn_id=turn_id,
        thread_id=thread_id,
        user_input=message,
        status="running",
    )
    session.close()
    return row["id"]


def test_greeting_has_no_tools_or_quant_run(tmp_path):
    factory = _session_factory(tmp_path)
    model = ScriptedModel([NativeModelResponse(text="你好！我可以查询行情、财务数据并协助回测策略。")])
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    turn_id = _turn(factory, "你好")
    events: list[ChatEvent] = []

    outcome = runtime.run_turn("thread-native", "你好", turn_id=turn_id, emit=events.append)

    assert outcome.status == "completed"
    assert not [event for event in events if event.type in (TOOL_CALL, TOOL_RESULT, RUN_LINKED)]
    assert model.tools_seen == [[]]


def test_incomplete_analysis_does_not_expose_analysis_tool(tmp_path):
    factory = _session_factory(tmp_path)
    model = ScriptedModel([NativeModelResponse(text="请告诉我股票代码和研究周期。")])
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    turn_id = _turn(factory, "帮我分析一只股票")
    events: list[ChatEvent] = []

    outcome = runtime.run_turn(
        "thread-native", "帮我分析一只股票", turn_id=turn_id, emit=events.append
    )

    assert outcome.status == "completed"
    assert outcome.end_reason == "target_unresolved"
    # 缺少股票目标时直接追问，不调用模型，也绝不暴露研究工具。
    assert model.tools_seen == []
    assert not [event for event in events if event.type in (TOOL_CALL, RUN_LINKED)]
    assert any(event.type == "assistant_chunk" for event in events)


def test_read_tool_schema_uses_openai_safe_function_names(tmp_path):
    runtime = NativeAgentChatRuntime(
        _session_factory(tmp_path),
        model=ScriptedModel([]),
        api_key="test",
    )
    admission = TurnToolPolicy().classify("查询 sh.600000 的 K 线")
    names = [item["function"]["name"] for item in runtime._tool_schemas(admission)]
    assert names == [
        "event_announcement",
        "event_news",
        "fundamental_financials",
        "fundamental_stock_info",
        "market_kline",
        "market_search",
        "market_snapshot",
    ]
    assert all("." not in name for name in names)


def test_stock_code_without_leading_space_is_recognized():
    admission = TurnToolPolicy().classify("分析sz000002")

    assert admission.scope is ToolScope.ANALYSIS
    assert stock_reference("分析sz000002") == "sz.000002"


def test_failed_turn_does_not_replay_orphan_tool_call(tmp_path):
    factory = _session_factory(tmp_path)
    _turn(factory, "分析 sz.000001")
    session = factory()
    stores = create_chat_stores(session)
    stores.events.create_event(
        turn_id="turn-native",
        seq=1,
        event_type=TOOL_CALL,
        payload={
            "call_id": "orphan-call",
            "tool": "fundamental_stock_info",
            "args": {"stock_code": "sz.000001"},
        },
    )
    stores.turns.update_turn_status("turn-native", "failed", error="服务端执行异常")
    session.close()

    runtime = NativeAgentChatRuntime(factory, model=ScriptedModel([]), api_key="test")
    messages, history_text = runtime._history("thread-native", current_turn_id=-1)

    assert messages == [{"role": "user", "content": "分析 sz.000001"}]
    assert history_text == "分析 sz.000001"


def test_explicit_analysis_deterministically_links_run(tmp_path):
    factory = _session_factory(tmp_path)
    model = ScriptedModel([NativeModelResponse(text="分析已完成，结果已挂载到右侧。")])
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    calls = []

    execute_original = runtime._execute_tool

    def execute(*args):
        if args[1].name != "quant_run_analysis":
            return execute_original(*args)
        calls.append(args[1])
        return {
            "ok": True,
            "run_id": "run-native-1",
            "status": "completed",
        }

    runtime._execute_tool = execute  # type: ignore[method-assign]
    turn_id = _turn(factory, "分析 sh.600000 并回测 ma_cross")
    events: list[ChatEvent] = []

    outcome = runtime.run_turn(
        "thread-native", "分析 sh.600000 并回测 ma_cross", turn_id=turn_id, emit=events.append
    )

    assert outcome.status == "completed"
    call = next(event for event in events if event.type == TOOL_CALL and event.payload["tool"] == "quant_run_analysis")
    result = next(event for event in events if event.type == TOOL_RESULT and event.payload["tool"] == "quant_run_analysis")
    assert call.payload["call_id"] == f"auto-analysis-{turn_id}"
    assert result.payload["call_id"] == f"auto-analysis-{turn_id}"
    assert next(event for event in events if event.type == RUN_LINKED).payload["run_id"] == "run-native-1"
    assert [item.name for item in calls] == ["quant_run_analysis"]
    assert "quant_run_analysis" not in model.tools_seen[0]


def test_auto_analysis_uses_canonical_code_and_internal_context(tmp_path):
    factory = _session_factory(tmp_path)

    class InspectingModel(ScriptedModel):
        def __init__(self):
            super().__init__([NativeModelResponse(text="分析完成。")])
            self.messages_seen = []

        def complete(self, messages, tools, **kwargs):
            self.messages_seen.append(messages)
            return super().complete(messages, tools, **kwargs)

    model = InspectingModel()
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    calls = []

    execute_original = runtime._execute_tool

    def execute(_session_id, call, _admission, _cancel_event):
        if call.name != "quant_run_analysis":
            return execute_original(_session_id, call, _admission, _cancel_event)
        calls.append(call)
        return {"ok": True, "run_id": "run-canonical", "status": "completed"}

    runtime._execute_tool = execute  # type: ignore[method-assign]
    turn_id = _turn(factory, "分析一下sh600000")
    events: list[ChatEvent] = []

    outcome = runtime.run_turn(
        "thread-native", "分析一下sh600000", turn_id=turn_id, emit=events.append
    )

    assert outcome.status == "completed"
    assert len(calls) == 1
    assert calls[0].name == "quant_run_analysis"
    assert calls[0].arguments == {"objective": "分析一下sh.600000"}
    messages = model.messages_seen[0]
    assert not any(message.get("tool_calls") for message in messages)
    assert any("不要声称调用了未提供的工具" in message["content"] for message in messages)
    assert next(event for event in events if event.type == RUN_LINKED).payload == {
        "run_id": "run-canonical"
    }


def test_chat_read_tool_normalizes_model_stock_code(tmp_path):
    factory = _session_factory(tmp_path)
    session = factory()
    session.close()
    model = ScriptedModel(
        [
            NativeModelResponse(
                tool_calls=[
                    NativeToolCall(
                        call_id="read-stock",
                        name="fundamental_stock_info",
                        arguments={"stock_code": "sh600000"},
                    )
                ]
            ),
            NativeModelResponse(text="已获取浦发银行基础信息。"),
        ]
    )
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    turn_id = _turn(factory, "查询sh600000基础信息")
    events: list[ChatEvent] = []

    outcome = runtime.run_turn(
        "thread-native", "查询sh600000基础信息", turn_id=turn_id, emit=events.append
    )

    assert outcome.status == "completed"
    result_event = next(event for event in events if event.type == TOOL_RESULT)
    assert result_event.payload["result"]["ok"] is True
    assert result_event.payload["result"]["data"]["code"] == "sh.600000"


def test_follow_up_analysis_uses_stock_from_history(tmp_path):
    factory = _session_factory(tmp_path)
    first_id = _turn(factory, "查询 sz.000001 行情", turn_id="turn-first")
    session = factory()
    stores = create_chat_stores(session)
    stores.turns.update_turn_status("turn-first", "completed", final_reply="已查询。")
    session.close()

    model = ScriptedModel([NativeModelResponse(text="回测研究已完成。")])
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    objectives = []
    execute_tool = runtime._execute_tool

    def execute(_session_id, call, _admission, _cancel_event):
        if call.name == "quant_run_analysis":
            objectives.append(call.arguments["objective"])
            return {"ok": True, "run_id": "run-follow-up", "status": "completed"}
        return execute_tool(_session_id, call, _admission, _cancel_event)

    runtime._execute_tool = execute  # type: ignore[method-assign]
    session = factory()
    stores = create_chat_stores(session)
    second = stores.turns.create_turn(
        turn_id="turn-second",
        thread_id="thread-native",
        user_input="帮我回测一下",
        status="running",
    )
    turn_id = second["id"]
    session.close()
    events: list[ChatEvent] = []

    outcome = runtime.run_turn(
        "thread-native", "帮我回测一下", turn_id=turn_id, emit=events.append
    )

    assert first_id != turn_id
    assert outcome.status == "completed"
    assert objectives == ["帮我回测一下（股票：sz.000001）"]
    assert next(event for event in events if event.type == RUN_LINKED).payload["run_id"] == "run-follow-up"


def _second_turn(factory, user_input, turn_id):
    session = factory()
    stores = create_chat_stores(session)
    row = stores.turns.create_turn(
        turn_id=turn_id,
        thread_id="thread-native",
        user_input=user_input,
        status="running",
    )
    session.close()
    return row["id"]


def test_analysis_without_any_target_asks_for_stock_before_model(tmp_path):
    factory = _session_factory(tmp_path)
    runtime = NativeAgentChatRuntime(factory, model=ScriptedModel([]), api_key="test")
    turn_id = _turn(factory, "帮我回测 ma_cross 策略", turn_id="turn-no-target")
    events: list[ChatEvent] = []

    outcome = runtime.run_turn(
        "thread-native", "帮我回测 ma_cross 策略", turn_id=turn_id, emit=events.append
    )

    assert outcome.status == "completed"
    assert outcome.end_reason == "target_unresolved"
    assert not [event for event in events if event.type == RUN_LINKED]
    assert not [event for event in events if event.type == TOOL_CALL]
    assert any(event.type == "assistant_chunk" for event in events)


def test_rejected_multi_target_turn_does_not_become_history_target(tmp_path):
    factory = _session_factory(tmp_path)
    _turn(factory, "比较000001.sz与600000.sh", turn_id="turn-compare")
    session = factory()
    stores = create_chat_stores(session)
    stores.turns.update_turn_status(
        "turn-compare",
        "completed",
        final_reply="检测到多个股票代码，请选择本次查询或研究的一只股票。",
        finish_reason="target_unresolved",
    )
    session.close()

    runtime = NativeAgentChatRuntime(
        factory, model=ScriptedModel([NativeModelResponse(text="请先选择一只股票。")]), api_key="test"
    )
    turn_id = _second_turn(factory, "分析一下", "turn-after-compare")
    events: list[ChatEvent] = []

    outcome = runtime.run_turn("thread-native", "分析一下", turn_id=turn_id, emit=events.append)

    assert outcome.status == "completed"
    assert not [event for event in events if event.type == RUN_LINKED]
    assert not [event for event in events if event.type == "stock.selected"]
    assert not [event for event in events if event.type == TOOL_CALL]


def test_general_chat_does_not_reuse_previous_stock(tmp_path):
    factory = _session_factory(tmp_path)
    _turn(factory, "000001.sz", turn_id="turn-stock")
    session = factory()
    stores = create_chat_stores(session)
    stores.turns.update_turn_status("turn-stock", "completed", final_reply="已查询。")
    session.close()

    runtime = NativeAgentChatRuntime(
        factory, model=ScriptedModel([NativeModelResponse(text="我是研究助手。")]), api_key="test"
    )
    turn_id = _second_turn(factory, "介绍一下你自己", "turn-chat")
    events: list[ChatEvent] = []

    outcome = runtime.run_turn("thread-native", "介绍一下你自己", turn_id=turn_id, emit=events.append)

    assert outcome.status == "completed"
    assert not [event for event in events if event.type == TOOL_CALL]
    assert not [event for event in events if event.type == "stock.selected"]


def test_suffix_input_automatically_queries_without_model_tool_choice(tmp_path, monkeypatch):
    from app.services.realtime_service import FetchResult, STATUS_OK, realtime_service

    monkeypatch.setattr(realtime_service, "fetch_bars", lambda *args: FetchResult(status=STATUS_OK, data=[{"close": 10}], provider="fixture"))
    factory = _session_factory(tmp_path)
    model = ScriptedModel([NativeModelResponse(text="已查询。")])
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    turn_id = _turn(factory, "000001.sz")
    events = []
    outcome = runtime.run_turn("thread-native", "000001.sz", turn_id=turn_id, emit=events.append)
    assert outcome.status == "completed"
    selected = [event for event in events if event.type == "stock.selected"]
    assert selected[0].payload == {"stock_code": "sz.000001"}
    calls = [event.payload for event in events if event.type == TOOL_CALL]
    assert [call["tool"] for call in calls] == ["fundamental_stock_info", "market_snapshot"]
    assert all(call["args"]["stock_code"] == "sz.000001" for call in calls)
    assert not [event for event in events if event.type == RUN_LINKED]
    results = [event.payload["result"] for event in events if event.type == TOOL_RESULT]
    assert results[0]["data"]["name"] == "平安银行"
    assert results[1]["data"]["latest"]["close"] == 10


def test_invalid_new_target_never_queries_previous_stock(tmp_path):
    factory = _session_factory(tmp_path)
    turn_id = _turn(factory, "000001.xyz")
    runtime = NativeAgentChatRuntime(factory, model=ScriptedModel([]), api_key="test")
    events = []
    outcome = runtime.run_turn("thread-native", "000001.xyz", turn_id=turn_id, emit=events.append)
    assert outcome.status == "completed"
    assert outcome.final_reply
    assert not [event for event in events if event.type in (RUN_LINKED, "stock.selected")]


@pytest.mark.parametrize("tool", ["event_news", "event_announcement"])
def test_news_and_announcements_use_gateway(tmp_path, monkeypatch, tool):
    from app.tools.registry import DEFAULT_REGISTRY

    factory = _session_factory(tmp_path)
    model = ScriptedModel([
        NativeModelResponse(tool_calls=[NativeToolCall("news", tool, {"stock_code": "000001.sz"})]),
        NativeModelResponse(text="暂无消息。"),
    ])
    original = DEFAULT_REGISTRY.invoke
    invoked = []

    def invoke(name, params, context):
        invoked.append(name)
        if name.startswith("event."):
            return {"ok": True, "data": {"rows": 0}, "source_id": "fixture", "as_of": "2026-10-30", "vendor": "fixture"}
        return original(name, params, context)

    monkeypatch.setattr(DEFAULT_REGISTRY, "invoke", invoke)
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    turn_id = _turn(factory, "查询000001.sz新闻")
    outcome = runtime.run_turn("thread-native", "查询000001.sz新闻", turn_id=turn_id, emit=lambda _: None)
    assert outcome.status == "completed"
    assert tool.replace("_", ".", 1) in invoked


def test_none_scope_cannot_execute_read_tool(tmp_path):
    from app.agent_chat.policy import ToolAdmission

    runtime = NativeAgentChatRuntime(_session_factory(tmp_path), model=ScriptedModel([]), api_key="test")
    result = runtime._execute_tool("thread-native", NativeToolCall("bad", "fundamental_stock_info", {"stock_code": "sz.000001"}), ToolAdmission(ToolScope.NONE, "social"), threading.Event())
    assert result["ok"] is False


def test_model_cannot_query_different_stock_than_current_target(tmp_path):
    factory = _session_factory(tmp_path)
    model = ScriptedModel([
        NativeModelResponse(tool_calls=[NativeToolCall("wrong", "fundamental_stock_info", {"stock_code": "sh.600000"})]),
        NativeModelResponse(text="已停止错误查询。"),
    ])
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    turn_id = _turn(factory, "查询000001.sz基本信息")
    events = []
    outcome = runtime.run_turn("thread-native", "查询000001.sz基本信息", turn_id=turn_id, emit=events.append)
    assert outcome.status == "completed"
    result = next(event.payload["result"] for event in events if event.type == TOOL_RESULT and event.payload["call_id"] == "wrong")
    assert result["ok"] is False
    assert result["error"]["code"] == "stock_target_mismatch"
