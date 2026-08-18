"""T3 HarnessChatService 测试（规格 D6/D7）。

覆盖：单 worker FIFO 顺序、事件持久化与 run.linked 联动、Idempotency-Key
去重、取消（cancelled 且不建 run）、重启恢复（running->interrupted、
queued 继续）、线程状态流转。
"""

import threading
import time

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
    FakeHarnessChatSeam,
)
from app.agent_chat.service import HarnessChatService
from app.agent_chat.stores import create_chat_stores
from app.agent_runtime.stores import create_stores
from app.config import Base


def _engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/chat.db", connect_args={"timeout": 30}
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def session_factory(tmp_path):
    engine = _engine(tmp_path)
    return sessionmaker(bind=engine)


def wait_until(predicate, timeout=5.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def turns_of(session_factory, thread_id):
    session = session_factory()
    try:
        return create_chat_stores(session).turns.list_turns(thread_id)
    finally:
        session.close()


def threads_get(session_factory, thread_id):
    session = session_factory()
    try:
        return create_chat_stores(session).threads.get_thread(thread_id)
    finally:
        session.close()


def runs_list(session_factory):
    session = session_factory()
    try:
        return create_stores(session).runs.list_runs()
    finally:
        session.close()


class RecordingSeam:
    """记录 run_turn 调用顺序（int turn_id），委托给内层 seam。"""

    def __init__(self, inner, log):
        self._inner = inner
        self._log = log

    def run_turn(self, session_id, user_message, *, turn_id, emit):
        self._log.append(turn_id)
        return self._inner.run_turn(
            session_id, user_message, turn_id=turn_id, emit=emit
        )

    def stop(self, session_id):
        self._inner.stop(session_id)

    def shutdown(self):
        self._inner.shutdown()


class BlockingSeam:
    """run_turn 在 gate 释放前阻塞；entered 标记 worker 已进入。"""

    def __init__(self, inner, gate):
        self._inner = inner
        self._gate = gate
        self.entered = threading.Event()

    def run_turn(self, session_id, user_message, *, turn_id, emit):
        self.entered.set()
        if not self._gate.wait(timeout=5):
            raise TimeoutError("gate not released")
        return self._inner.run_turn(
            session_id, user_message, turn_id=turn_id, emit=emit
        )

    def stop(self, session_id):
        self._inner.stop(session_id)

    def shutdown(self):
        self._inner.shutdown()


def test_fifo_order(session_factory):
    log: list[int] = []
    seam = RecordingSeam(FakeHarnessChatSeam(session_factory), log)
    service = HarnessChatService(session_factory, seam)
    service.startup()
    try:
        thread = service.create_thread()
        t1 = service.submit_turn(thread["thread_id"], "第一")
        t2 = service.submit_turn(thread["thread_id"], "第二")
        t3 = service.submit_turn(thread["thread_id"], "第三")

        def all_done():
            ts = turns_of(session_factory, thread["thread_id"])
            return len(ts) == 3 and all(t["status"] == "completed" for t in ts)

        assert wait_until(all_done), "turns 未全部完成"
        assert log == [t1["id"], t2["id"], t3["id"]]
    finally:
        service.shutdown()


def test_events_persisted_and_run_linked(session_factory):
    service = HarnessChatService(
        session_factory, FakeHarnessChatSeam(session_factory)
    )
    service.startup()
    try:
        thread = service.create_thread()
        service.submit_turn(thread["thread_id"], "生成 ma_cross 并回测验证 sh.600000")

        def done():
            ts = turns_of(session_factory, thread["thread_id"])
            return ts and ts[0]["status"] == "completed"

        assert wait_until(done)

        session = session_factory()
        try:
            events = create_chat_stores(session).events.list_events(
                thread["thread_id"]
            )
        finally:
            session.close()
        assert [e["event_type"] for e in events] == [
            REASONING,
            ASSISTANT_CHUNK,
            TOOL_CALL,
            TOOL_RESULT,
            RUN_LINKED,
            ASSISTANT_CHUNK,
            TURN_DONE,
        ]
        assert [e["seq"] for e in events] == [1, 2, 3, 4, 5, 6, 7]

        linked = next(e for e in events if e["event_type"] == RUN_LINKED)
        run_id = linked["payload"]["run_id"]
        assert threads_get(session_factory, thread["thread_id"])["last_run_id"] == run_id
        session = session_factory()
        try:
            run = create_stores(session).runs.get_run(run_id)
        finally:
            session.close()
        assert run is not None
        assert run["thread_id"] == thread["thread_id"]
    finally:
        service.shutdown()


def test_idempotent_submit(session_factory):
    service = HarnessChatService(
        session_factory, FakeHarnessChatSeam(session_factory)
    )
    thread = service.create_thread()
    first = service.submit_turn(
        thread["thread_id"], "分析", idempotency_key="key-1"
    )
    second = service.submit_turn(
        thread["thread_id"], "分析", idempotency_key="key-1"
    )
    assert second["turn_id"] == first["turn_id"]
    assert len(turns_of(session_factory, thread["thread_id"])) == 1


def test_cancel_turn(session_factory):
    gate = threading.Event()
    seam = BlockingSeam(FakeHarnessChatSeam(session_factory), gate)
    service = HarnessChatService(session_factory, seam)
    service.startup()
    try:
        thread = service.create_thread()
        service.submit_turn(thread["thread_id"], "分析")
        assert seam.entered.wait(2), "worker 未进入 run_turn"
        service.stop_turn(thread["thread_id"])
        gate.set()

        def cancelled():
            ts = turns_of(session_factory, thread["thread_id"])
            return ts and ts[0]["status"] == "cancelled"

        assert wait_until(cancelled)
        t = turns_of(session_factory, thread["thread_id"])[0]
        assert t["finish_reason"] == "user_cancelled"
        assert runs_list(session_factory) == []
    finally:
        service.shutdown()


def test_restart_recovery(session_factory):
    service = HarnessChatService(
        session_factory, FakeHarnessChatSeam(session_factory)
    )
    thread = service.create_thread()
    session = session_factory()
    try:
        stores = create_chat_stores(session)
        stores.turns.create_turn(
            turn_id="turn-running",
            thread_id=thread["thread_id"],
            user_input="进行中",
            status="running",
        )
        stores.turns.create_turn(
            turn_id="turn-queued",
            thread_id=thread["thread_id"],
            user_input="排队中",
            status="queued",
        )
    finally:
        session.close()
    service.startup()
    try:
        def settled():
            ts = turns_of(session_factory, thread["thread_id"])
            by_id = {t["turn_id"]: t for t in ts}
            rt = by_id.get("turn-running")
            qt = by_id.get("turn-queued")
            return (
                rt is not None
                and qt is not None
                and rt["status"] == "interrupted"
                and qt["status"] == "completed"
            )

        assert wait_until(settled)
        rt = next(
            t
            for t in turns_of(session_factory, thread["thread_id"])
            if t["turn_id"] == "turn-running"
        )
        assert rt["finish_reason"] == "restart"
    finally:
        service.shutdown()


def test_thread_status_flow(session_factory):
    gate = threading.Event()
    seam = BlockingSeam(FakeHarnessChatSeam(session_factory), gate)
    service = HarnessChatService(session_factory, seam)
    service.startup()
    try:
        thread = service.create_thread()
        service.submit_turn(thread["thread_id"], "分析")
        assert seam.entered.wait(2), "worker 未进入 run_turn"
        # worker 阻塞在 gate：线程状态应为 running
        assert threads_get(session_factory, thread["thread_id"])["status"] == "running"
        gate.set()

        def idle():
            return threads_get(session_factory, thread["thread_id"])["status"] == "idle"

        assert wait_until(idle)
        t = turns_of(session_factory, thread["thread_id"])[0]
        assert t["status"] == "completed"
        assert t["final_reply"]
    finally:
        service.shutdown()
