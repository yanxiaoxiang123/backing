"""旧端点 adapter 测试（任务 07 验收）。

覆盖：analyze 经统一 runtime 落 run/step/tool 事实、响应形状不变、
LLM 不可用 → 503 语义、既有 test_api_contracts/test_pipeline 不受影响。
"""

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent_api import adapter
from app.agent_runtime.stores import create_stores
from app.api.agent import router as agent_router
from app.auth import get_current_api_key
from app.config import Base, get_db
from app.models.models import DailyKline, Stock


class _FakeResult:
    def __init__(self):
        self.success = True
        self.final_signal = "buy"
        self.final_confidence = 0.8
        self.final_reason = "测试理由"
        self.opinions = [{"conclusion": "看多"}]
        self.stages = [
            {"stage_name": "technical", "meta": {}},
            {"stage_name": "intel", "meta": {"news_items": [{"title": "n1"}]}},
        ]
        self.duration_s = 0.5
        self.error = None


class _FakeOrchestrator:
    """可注入的假编排器（is_available/run）。"""

    def __init__(self, mode: str | None = None, *, available: bool = True, result=None):
        self.mode = mode
        self.available = available
        self.result = result or _FakeResult()

    @property
    def is_available(self) -> bool:
        return self.available

    def run(self, **kwargs):
        return self.result


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    # 预置股票与 K 线，避免 _ensure_stock_kline_data 触发网络同步
    session = sessionmaker(bind=engine)()
    session.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    session.add(
        DailyKline(
            stock_code="sh.600000",
            date=date(2026, 1, 5),
            open=10.0,
            high=10.5,
            low=9.9,
            close=10.2,
            volume=100000,
            amount=1020000,
        )
    )
    session.commit()
    session.close()
    return engine


@pytest.fixture()
def client(engine, monkeypatch):
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(agent_router, prefix="/api/v1")

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

    monkeypatch.setattr(adapter, "AgentOrchestrator", _FakeOrchestrator)
    return TestClient(app), TestingSession


def test_adapter_records_run_step_and_tool_facts(engine, monkeypatch):
    monkeypatch.setattr(adapter, "AgentOrchestrator", _FakeOrchestrator)
    session = sessionmaker(bind=engine)()
    request = SimpleNamespace(
        stock_code="sh.600000", stock_name="浦发银行", mode="standard"
    )
    run_id, final, result = adapter.run_legacy_analysis(session, request)
    assert final["status"] == "completed"
    assert result is not None and result.final_signal == "buy"

    stores = create_stores(session)
    run = stores.runs.get_run(run_id)
    assert run["status"] == "completed"
    steps = stores.steps.list_steps(run_id)
    assert [s["node"] for s in steps] == ["legacy_orchestrator"]
    assert steps[0]["output_schema"] == "legacy.analysis.summary"
    calls = stores.tool_calls.list_tool_calls(run_id)
    assert len(calls) == 1
    assert calls[0]["tool_name"] == "market.kline"
    session.close()


def test_analyze_endpoint_returns_same_shape(client):
    test_client, _ = client
    resp = test_client.post(
        "/api/v1/agent/analyze",
        json={"stock_code": "sh.600000", "stock_name": "浦发银行", "mode": "standard"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["final_signal"] == "buy"
    assert body["final_confidence"] == 0.8
    assert body["news_items"] == [{"title": "n1"}]
    assert body["duration_s"] == 0.5


def test_analyze_endpoint_records_run_facts(client, engine):
    test_client, TestingSession = client
    resp = test_client.post(
        "/api/v1/agent/analyze",
        json={"stock_code": "sh.600000", "mode": "quick"},
    )
    assert resp.status_code == 200

    session = TestingSession()
    runs = create_stores(session).runs.list_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert "legacy agent analysis" in runs[0]["objective"]
    session.close()


def test_analyze_llm_unavailable_returns_503(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr(
        adapter, "AgentOrchestrator", lambda mode=None: _FakeOrchestrator(available=False)
    )
    resp = test_client.post(
        "/api/v1/agent/analyze",
        json={"stock_code": "sh.600000", "mode": "standard"},
    )
    assert resp.status_code == 503
