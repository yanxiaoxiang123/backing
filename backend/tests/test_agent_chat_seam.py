"""T2 HarnessChatSeam 接缝测试（规格 D1/D2）。

覆盖：事件类型与顺序可重放、quant_run_analysis 真实创建 run（thread_id
关联、step/tool_call 落库）、run_id 确定性派生、stop 取消语义、turn.done
终态载荷。
"""

import hashlib
import re

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.agent_chat.seam import (
    ASSISTANT_CHUNK,
    REASONING,
    RUN_LINKED,
    TOOL_CALL,
    TOOL_RESULT,
    TURN_DONE,
    ChatEvent,
    FakeHarnessChatSeam,
)
from app.agent_runtime.stores import create_stores
from app.config import Base


def _engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def session_factory():
    engine = _engine()
    return sessionmaker(bind=engine)


@pytest.fixture()
def seam(session_factory):
    return FakeHarnessChatSeam(session_factory)


@pytest.fixture()
def run_stores(session_factory):
    return lambda: create_stores(session_factory())


def _collect(seam, session_id, message, turn_id=1):
    events: list[ChatEvent] = []
    outcome = seam.run_turn(session_id, message, turn_id=turn_id, emit=events.append)
    return events, outcome


def test_event_sequence_and_order(seam):
    events, outcome = _collect(seam, "thread-1", "分析 sh.600000")
    assert [e.type for e in events] == [
        REASONING,
        ASSISTANT_CHUNK,
        TOOL_CALL,
        TOOL_RESULT,
        RUN_LINKED,
        ASSISTANT_CHUNK,
        TURN_DONE,
    ]
    assert outcome.status == "completed"
    assert "run-" in outcome.final_reply
    # 事件全部归属该 turn
    assert all(e.turn_id == 1 for e in events)


def test_quant_run_analysis_creates_real_run(run_stores, seam):
    events, _ = _collect(seam, "thread-1", "生成 ma_cross 并回测验证 sh.600000")
    linked = next(e for e in events if e.type == RUN_LINKED)
    run_id = linked.payload["run_id"]

    run = run_stores().runs.get_run(run_id)
    assert run is not None
    assert run["thread_id"] == "thread-1"
    assert run["status"] == "completed"
    assert run["objective"] == "生成 ma_cross 并回测验证 sh.600000"

    steps = run_stores().steps.list_steps(run_id)
    assert steps and steps[0]["node"] == "research"
    assert steps[0]["status"] == "completed"

    calls = run_stores().tool_calls.list_tool_calls(run_id)
    assert calls and calls[0]["tool_name"] == "quant_run_analysis"
    assert calls[0]["status"] == "ok"

    # tool_result 与 run.linked 载荷携带同一 run_id
    result = next(e for e in events if e.type == TOOL_RESULT)
    assert result.payload["run_id"] == run_id
    assert result.payload["tool"] == "quant_run_analysis"


def test_run_id_deterministic(seam):
    events, _ = _collect(seam, "thread-1", "分析", turn_id=7)
    linked = next(e for e in events if e.type == RUN_LINKED)
    digest = hashlib.sha1(b"thread-1:7").hexdigest()[:12]
    assert linked.payload["run_id"] == f"run-{digest}"


def test_same_input_same_event_sequence(seam):
    e1, _ = _collect(seam, "thread-a", "分析", turn_id=1)
    e2, _ = _collect(seam, "thread-b", "分析", turn_id=1)
    assert [e.type for e in e1] == [e.type for e in e2]

    def normalize(payload):
        p = dict(payload)
        p.pop("run_id", None)
        for key in ("content", "final_reply"):
            if key in p:
                p[key] = re.sub(r"run-[0-9a-f]{12}", "run-X", p[key])
        return p

    # 除 run_id 及其在文本中的引用外载荷一致
    for a, b in zip(e1, e2):
        assert normalize(a.payload) == normalize(b.payload)


def test_stop_cancels_turn(seam):
    seam.stop("thread-1")
    events, outcome = _collect(seam, "thread-1", "分析")
    assert outcome.status == "cancelled"
    assert outcome.end_reason == "user_cancelled"
    types = [e.type for e in events]
    assert REASONING in types
    assert TOOL_CALL not in types
    assert TOOL_RESULT not in types
    assert RUN_LINKED not in types
    assert TURN_DONE not in types


def test_turn_done_carries_final_reply(seam):
    events, outcome = _collect(seam, "thread-1", "分析")
    done = next(e for e in events if e.type == TURN_DONE)
    assert done.payload["status"] == "completed"
    assert done.payload["final_reply"] == outcome.final_reply
