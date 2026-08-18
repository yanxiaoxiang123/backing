"""T4 Agent 聊天 API 测试（规格 D8）。

覆盖：创建/列表/恢复、提交 turn + SSE 事件序列与 Last-Event-ID 重放、
Idempotency-Key 去重、取消（合成 turn.done 收口）、归档、404。
认证依赖走 override（既有 auth 体系由 test_auth 覆盖）。
"""

import json
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.agent_chat.api import router
from app.agent_chat.seam import FakeHarnessChatSeam
from app.agent_chat.service import HarnessChatService
from app.auth import get_current_api_key
from app.config import Base, get_db


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


@pytest.fixture()
def api(tmp_path):
    # 临时文件库：worker 线程与请求线程各自独立连接（StaticPool 共享连接会在
    # 并发写时触发 session.refresh 竞态，详见 T4 修复记录）。
    engine = create_engine(
        f"sqlite:///{tmp_path}/chat_api.db", connect_args={"timeout": 30}
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    gate = threading.Event()
    gate.set()  # 默认不阻塞；取消测试先 clear
    seam = BlockingSeam(FakeHarnessChatSeam(TestingSession), gate)
    service = HarnessChatService(TestingSession, seam)
    service.startup()
    app.state.harness_chat_service = service

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    async def fake_key():
        return "test-key"

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_api_key] = fake_key

    with TestClient(app) as client:
        yield client, service, seam, gate
    service.shutdown()


def _create_thread(client):
    resp = client.post("/api/v1/agent-chats")
    assert resp.status_code == 201
    return resp.json()["thread_id"]


def read_sse_until_done(client, url, max_lines=400, headers=None):
    """读取 SSE 直到 turn.done 帧完整（含其 data 行；防挂起上限）。"""
    with client.stream("GET", url, headers=headers) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        lines: list[str] = []
        done_seen = False
        for line in resp.iter_lines():
            lines.append(line)
            if line == "event: turn.done":
                done_seen = True
            elif done_seen and line == "":
                break  # turn.done 帧（event + data + 空行）完整
            elif len(lines) >= max_lines:
                break
    return lines


def parse_sse(lines):
    events = []
    current: dict = {}
    for line in lines:
        if line.startswith("id: "):
            current["id"] = int(line.split(": ", 1)[1])
        elif line.startswith("event: "):
            current["event"] = line.split(": ", 1)[1]
        elif line.startswith("data: "):
            current["data"] = line.split(": ", 1)[1]
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


def test_create_list_get(api):
    client, *_ = api
    tid = _create_thread(client)
    thread = client.get(f"/api/v1/agent-chats/{tid}").json()["thread"]
    assert thread["status"] == "idle"
    assert thread["archived"] is False

    listing = client.get("/api/v1/agent-chats").json()
    assert listing["total"] == 1
    assert listing["threads"][0]["thread_id"] == tid

    detail = client.get(f"/api/v1/agent-chats/{tid}").json()
    assert detail["thread"]["thread_id"] == tid
    assert detail["turns"] == []


def test_submit_turn_and_sse_events(api):
    client, *_ = api
    tid = _create_thread(client)
    resp = client.post(
        f"/api/v1/agent-chats/{tid}/turns",
        json={"content": "生成 ma_cross 并回测验证 sh.600000"},
    )
    assert resp.status_code == 202
    turn = resp.json()["turn"]
    assert turn["status"] == "queued"
    assert turn["content"] == "生成 ma_cross 并回测验证 sh.600000"

    lines = read_sse_until_done(client, f"/api/v1/agent-chats/{tid}/events")
    events = parse_sse(lines)
    types = [e["event"] for e in events]
    assert types == [
        "reasoning",
        "assistant_chunk",
        "tool_call",
        "tool_result",
        "run.linked",
        "assistant_chunk",
        "turn.done",
    ]
    ids = [e["id"] for e in events]
    assert ids == sorted(ids)

    linked = next(e for e in events if e["event"] == "run.linked")
    data = json.loads(linked["data"])
    assert data["run_id"]
    assert data["turn_id"] == turn["id"]

    done = next(e for e in events if e["event"] == "turn.done")
    assert json.loads(done["data"])["status"] == "completed"

    # run 联动：线程 last_run_id + run 详情
    detail = client.get(f"/api/v1/agent-chats/{tid}").json()
    assert detail["thread"]["last_run_id"] == data["run_id"]
    t = detail["turns"][0]
    assert t["status"] == "completed"
    assert t["final_reply"]


def test_idempotency_key_dedup(api):
    client, *_ = api
    tid = _create_thread(client)
    payload = {"content": "分析"}
    headers = {"Idempotency-Key": "dup-key-1"}
    r1 = client.post(f"/api/v1/agent-chats/{tid}/turns", json=payload, headers=headers)
    r2 = client.post(f"/api/v1/agent-chats/{tid}/turns", json=payload, headers=headers)
    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json()["turn"]["id"] == r2.json()["turn"]["id"]
    detail = client.get(f"/api/v1/agent-chats/{tid}").json()
    assert len(detail["turns"]) == 1


def test_sse_last_event_id_resume(api):
    client, *_ = api
    tid = _create_thread(client)
    client.post(f"/api/v1/agent-chats/{tid}/turns", json={"content": "第一轮"})
    first = parse_sse(
        read_sse_until_done(client, f"/api/v1/agent-chats/{tid}/events")
    )
    assert first and first[-1]["event"] == "turn.done"
    last_id = first[-1]["id"]

    client.post(f"/api/v1/agent-chats/{tid}/turns", json={"content": "第二轮"})
    resumed = parse_sse(
        read_sse_until_done(
            client,
            f"/api/v1/agent-chats/{tid}/events",
            headers={"Last-Event-ID": str(last_id)},
        )
    )
    # 带 Last-Event-ID 续传：只收新事件，无重复
    assert resumed
    assert all(e["id"] > last_id for e in resumed)
    assert resumed[-1]["event"] == "turn.done"


def test_cancel_via_api(api):
    client, _, seam, gate = api
    gate.clear()
    tid = _create_thread(client)
    client.post(f"/api/v1/agent-chats/{tid}/turns", json={"content": "分析"})
    assert seam.entered.wait(2), "worker 未进入 run_turn"
    resp = client.post(f"/api/v1/agent-chats/{tid}/cancel")
    assert resp.status_code == 200
    gate.set()

    lines = read_sse_until_done(client, f"/api/v1/agent-chats/{tid}/events")
    events = parse_sse(lines)
    done = next(e for e in events if e["event"] == "turn.done")
    assert json.loads(done["data"])["status"] == "cancelled"
    detail = client.get(f"/api/v1/agent-chats/{tid}").json()
    assert detail["turns"][0]["status"] == "cancelled"


def test_archive(api):
    client, *_ = api
    tid = _create_thread(client)
    resp = client.post(f"/api/v1/agent-chats/{tid}/archive")
    assert resp.status_code == 200
    assert resp.json()["archived"] is True
    listing = client.get("/api/v1/agent-chats").json()
    assert listing["total"] == 0


def test_404_for_unknown_thread(api):
    client, *_ = api
    assert client.get("/api/v1/agent-chats/thread-nope").status_code == 404
    assert (
        client.post("/api/v1/agent-chats/thread-nope/turns", json={"content": "x"}).status_code
        == 404
    )
    assert client.post("/api/v1/agent-chats/thread-nope/cancel").status_code == 404
    assert client.post("/api/v1/agent-chats/thread-nope/archive").status_code == 404
