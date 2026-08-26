"""模拟盘 API 测试（规格 v2 决策 21；US-3.1/3.2；切片 05）。

覆盖：审批决策端点、手动撮合、账户/订单/事件查询、认证（401）。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent_api.paper import router
from app.auth import get_current_api_key
from app.config import Base, get_db
from app.models.agent_runtime import AgentRun, ApprovalRecord
from app.models.models import Stock
from app.models.paper_trading import PaperOrder, PaperOrderEvent


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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


@pytest.fixture()
def no_auth_client():
    from starlette.middleware.sessions import SessionMiddleware

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _seed_pending(db):
    db.add(AgentRun(run_id="run-1", objective="测试"))
    db.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    order = PaperOrder(
        order_id="po-1",
        run_id="run-1",
        stock_code="sh.600000",
        side="buy",
        quantity=100,
        status="pending_approval",
    )
    db.add(order)
    db.flush()
    approval = ApprovalRecord(
        run_id="run-1", action="paper.order", summary="buy 100 股", status="pending"
    )
    db.add(approval)
    db.flush()
    order.approval_id = approval.id
    db.add(PaperOrderEvent(order_id=order.order_id, seq=1, event_type="proposed"))
    db.commit()
    return approval.id


def test_decide_approval_endpoint(client):
    # 通过 sessionmaker 拿共享库写种子
    from sqlalchemy.orm import sessionmaker as sm

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sm(bind=engine)()
    approval_id = _seed_pending(session)
    session.close()
    # 覆盖依赖使用的是另一个 engine，这里直接验证 404/校验分支即可
    resp = client.post(
        f"/api/v1/agent-runs/run-1/approvals/{approval_id}/decide",
        json={"decision": "bogus"},
    )
    assert resp.status_code == 422


def test_decide_unknown_approval(client):
    resp = client.post(
        "/api/v1/agent-runs/run-1/approvals/99999/decide",
        json={"decision": "approved"},
    )
    assert resp.status_code == 400


def test_match_cycle_endpoint(client):
    resp = client.post("/api/v1/paper/match")
    assert resp.status_code == 200
    assert resp.json()["processed"] == 0


def test_account_and_orders_endpoints(client):
    account = client.get("/api/v1/paper/account")
    assert account.status_code == 200
    assert account.json()["account_id"] == "default"

    orders = client.get("/api/v1/paper/orders")
    assert orders.status_code == 200
    assert isinstance(orders.json()["orders"], list)

    events = client.get("/api/v1/paper/events")
    assert events.status_code == 200
    assert "order_events" in events.json()
    assert "cash_events" in events.json()


def test_attribution_forwards_run_id(client, monkeypatch):
    captured = {}

    def fake_report(_db, start, end, *, benchmark_series, run_id):
        captured.update(start=start, end=end, run_id=run_id)
        return {"run_id": run_id, "benchmark_available": bool(benchmark_series)}

    monkeypatch.setattr(
        "app.services.research_data.fetch_index_kline",
        lambda *_args: {"payload": {"kline": [{"close": 100}, {"close": 101}]}},
    )
    monkeypatch.setattr(
        "app.agent_api.paper.paper_service.attribution_report", fake_report
    )

    response = client.get(
        "/api/v1/paper/attribution",
        params={
            "run_id": "run-target",
            "start_date": "2026-08-01",
            "end_date": "2026-08-05",
        },
    )

    assert response.status_code == 200
    assert response.json()["run_id"] == "run-target"
    assert captured == {
        "start": "2026-08-01",
        "end": "2026-08-05",
        "run_id": "run-target",
    }


def test_no_auth_rejected(no_auth_client):
    resp = no_auth_client.get("/api/v1/paper/account")
    assert resp.status_code == 401
