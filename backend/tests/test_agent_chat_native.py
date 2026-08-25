"""Native backend Agent chat runtime tests (no network and no Harness checkout)."""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.agent_chat.policy import TurnToolPolicy
from app.agent_chat.runtime import (
    NativeAgentChatRuntime,
    NativeModelResponse,
    NativeToolCall,
)
from app.agent_chat.seam import RUN_LINKED, TOOL_CALL, TOOL_RESULT, ChatEvent
from app.agent_chat.stores import create_chat_stores
from app.config import Base


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/native-chat.db")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


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

    outcome = runtime.run_turn("thread-native", "帮我分析一只股票", turn_id=turn_id, emit=lambda _: None)

    assert outcome.status == "completed"
    assert model.tools_seen == [[]]


def test_read_tool_schema_uses_openai_safe_function_names(tmp_path):
    runtime = NativeAgentChatRuntime(
        _session_factory(tmp_path),
        model=ScriptedModel([]),
        api_key="test",
    )
    admission = TurnToolPolicy().classify("查询 sh.600000 的 K 线")
    names = [item["function"]["name"] for item in runtime._tool_schemas(admission)]
    assert names == [
        "fundamental_financials",
        "fundamental_stock_info",
        "market_kline",
        "market_snapshot",
    ]
    assert all("." not in name for name in names)


def test_explicit_analysis_links_run_and_pairs_call_id(tmp_path):
    factory = _session_factory(tmp_path)
    model = ScriptedModel(
        [
            NativeModelResponse(
                tool_calls=[
                    NativeToolCall(
                        call_id="call-analysis-1",
                        name="quant_run_analysis",
                        arguments={"objective": "分析 sh.600000 并回测 ma_cross"},
                    )
                ]
            ),
            NativeModelResponse(text="分析已完成，结果已挂载到右侧。"),
        ]
    )
    runtime = NativeAgentChatRuntime(factory, model=model, api_key="test")
    runtime._execute_tool = lambda *_args: {  # type: ignore[method-assign]
        "ok": True,
        "run_id": "run-native-1",
        "status": "completed",
    }
    turn_id = _turn(factory, "分析 sh.600000 并回测 ma_cross")
    events: list[ChatEvent] = []

    outcome = runtime.run_turn(
        "thread-native", "分析 sh.600000 并回测 ma_cross", turn_id=turn_id, emit=events.append
    )

    assert outcome.status == "completed"
    call = next(event for event in events if event.type == TOOL_CALL)
    result = next(event for event in events if event.type == TOOL_RESULT)
    assert call.payload["call_id"] == "call-analysis-1"
    assert result.payload["call_id"] == "call-analysis-1"
    assert next(event for event in events if event.type == RUN_LINKED).payload["run_id"] == "run-native-1"
    assert model.tools_seen[0][-1] == "quant_run_analysis"
