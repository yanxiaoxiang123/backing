"""agent_api 测试（任务 06 验收）。

覆盖：创建/查询/列表/取消/恢复、SSE 事件流与 Last-Event-ID 重放、
artifacts、404/422、认证依赖走 override（既有 auth 体系由 test_auth 覆盖）。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent_api.routes import router
from app.auth import get_current_api_key
from app.config import Base, get_db


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # 共享同一内存库（TestClient 跨请求/线程）
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

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
    return TestClient(app)


def _create(client, **overrides):
    payload = {"objective": "研究测试", "execute_inline": True}
    payload.update(overrides)
    return client.post("/api/v1/agent-runs", json=payload)


def test_create_run_inline_completes(client):
    resp = _create(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "completed"
    assert body["run_id"]
    assert body["events_url"].endswith("/events")

    run = client.get(f"/api/v1/agent-runs/{body['run_id']}").json()
    assert run["status"] == "completed"


def test_events_sse_replays_steps_and_tools(client):
    run_id = _create(client).json()["run_id"]
    with client.stream("GET", f"/api/v1/agent-runs/{run_id}/events") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        text = resp.read().decode()

    ids = [int(line.split(": ", 1)[1]) for line in text.splitlines() if line.startswith("id: ")]
    assert ids == sorted(ids) and len(ids) >= 3  # supervisor 动态路由后的节点事件
    assert "event: done" in text
    # 节点事件内容
    assert '"type": "step"' in text
    assert '"node": "supervisor"' in text
    # 工具事件（data_qa/research 节点调用确定性工具）
    assert '"type": "tool_call"' in text
    assert '"tool": "market.snapshot"' in text


def test_events_sse_last_event_id_resume(client):
    run_id = _create(client).json()["run_id"]
    with client.stream("GET", f"/api/v1/agent-runs/{run_id}/events") as resp:
        full = resp.read().decode()
    ids = [int(line.split(": ", 1)[1]) for line in full.splitlines() if line.startswith("id: ")]
    assert ids

    with client.stream(
        "GET", f"/api/v1/agent-runs/{run_id}/events", headers={"Last-Event-ID": str(ids[0])}
    ) as resp:
        resumed = resp.read().decode()
    resumed_ids = [
        int(line.split(": ", 1)[1]) for line in resumed.splitlines() if line.startswith("id: ")
    ]
    assert resumed_ids == ids[1:]  # 从断点继续，无重复


def test_list_runs_with_status_filter(client):
    _create(client)
    listing = client.get("/api/v1/agent-runs").json()
    assert listing["total"] >= 1
    assert all(r["status"] == "completed" for r in listing["runs"])
    listing = client.get("/api/v1/agent-runs?status=failed").json()
    assert listing["total"] == 0


def test_resume_wait_completes_failed_run(client):
    run_id = _create(client).json()["run_id"]
    # 对已完成 run 的 resume 是无操作（终态守卫）；failed 恢复语义由
    # test_agent_runtime.py 覆盖（含重试与跳过已完成节点）
    resp = client.post(f"/api/v1/agent-runs/{run_id}/resume?wait=true")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_cancel_endpoint(client):
    run_id = _create(client).json()["run_id"]
    resp = client.post(f"/api/v1/agent-runs/{run_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == run_id


def test_artifacts_include_run_plan(client):
    """US-2.9：run 至少产出 run_plan 工作区产物（supervisor 节点 emit）。"""
    run_id = _create(client).json()["run_id"]
    resp = client.get(f"/api/v1/agent-runs/{run_id}/artifacts")
    assert resp.status_code == 200
    artifacts = resp.json()["artifacts"]
    assert any(a["artifact_type"] == "run_plan" for a in artifacts)


def test_run_detail_includes_step_outputs(client):
    run_id = _create(client).json()["run_id"]
    detail = client.get(f"/api/v1/agent-runs/{run_id}").json()
    assert "steps" in detail
    assert detail["steps"], "run 详情应包含节点"
    supervisor = next(s for s in detail["steps"] if s["node"] == "supervisor")
    assert supervisor["output_schema"] == "RunPlan"
    assert supervisor["output_json"]["objective"]  # 结构化输出对前端可见
    research = next(s for s in detail["steps"] if s["node"] == "research")
    assert research["output_json"]["claims"]

    slim = client.get(f"/api/v1/agent-runs/{run_id}?include_steps=false").json()
    assert "steps" not in slim


def test_unknown_run_404(client):
    assert client.get("/api/v1/agent-runs/nope").status_code == 404
    with client.stream("GET", "/api/v1/agent-runs/nope/events") as resp:
        assert resp.status_code == 404
    assert client.get("/api/v1/agent-runs/nope/artifacts").status_code == 404


def test_validation_errors(client):
    resp = client.post("/api/v1/agent-runs", json={"objective": ""})
    assert resp.status_code == 422
    resp = client.post(
        "/api/v1/agent-runs",
        json={"objective": "x", "budget": {"max_rounds": 0}},
    )
    assert resp.status_code == 422


def test_create_run_with_strategy_params(client):
    """US-2.8：参数修改产生新 run，strategy 产物携带新参数。"""
    run_id = _create(
        client,
        objective="生成 ma_cross 策略并回测验证 sh.600000",
        strategy_params={"short_period": 10, "long_period": 30},
    ).json()["run_id"]
    detail = client.get(f"/api/v1/agent-runs/{run_id}").json()
    strategy = next(s for s in detail["steps"] if s["node"] == "strategy_engineer")
    assert strategy["output_json"]["signal_parameters"] == {
        "short_period": 10,
        "long_period": 30,
    }
    backtest = next(s for s in detail["steps"] if s["node"] == "backtest_critic")
    assert backtest["output_json"]["metrics"] is not None
