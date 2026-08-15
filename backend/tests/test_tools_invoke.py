"""工具直调端点测试（规格决策 2：DSH 插件只调 FastAPI 网关；切片 11）。

覆盖：只读/策略工具可直调、approval 工具 403、未知工具 200+ok:false、
认证 401。
"""

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent_api.tools import router
from app.auth import get_current_api_key
from app.config import Base, get_db


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


def test_invoke_market_kline(client, monkeypatch):
    from app.tools import market as market_module

    df = pd.DataFrame(
        {
            "date": ["2026-08-14"],
            "open": [10.0],
            "high": [10.5],
            "low": [9.9],
            "close": [10.3],
            "volume": [100000],
        }
    )
    monkeypatch.setattr(
        market_module.baostock_service, "get_daily_kline", lambda *a, **k: df
    )
    resp = client.post(
        "/api/v1/tools/invoke",
        json={
            "tool": "market.kline",
            "params": {
                "stock_code": "sh.600000",
                "start_date": "2026-08-01",
                "end_date": "2026-08-14",
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["source_id"].startswith("kline:")
    assert body["data"]["rows"] == 1


def test_invoke_paper_tool_forbidden(client):
    resp = client.post(
        "/api/v1/tools/invoke",
        json={
            "tool": "execution.paper.propose_order",
            "params": {"stock_code": "sh.600000", "side": "buy", "quantity": 100},
        },
    )
    assert resp.status_code == 403


def test_invoke_unknown_tool(client):
    resp = client.post("/api/v1/tools/invoke", json={"tool": "no.such", "params": {}})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_invoke_requires_auth():
    from starlette.middleware.sessions import SessionMiddleware

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test")
    app.include_router(router, prefix="/api/v1")
    resp = TestClient(app).post("/api/v1/tools/invoke", json={"tool": "x", "params": {}})
    assert resp.status_code == 401
