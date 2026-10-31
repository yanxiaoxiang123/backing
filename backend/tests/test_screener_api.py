import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.api.screener import router as screener_router
from app.auth import get_current_api_key
from app.config import get_db
from app.error_handlers import register_error_handlers
from app.models.models import Stock


@pytest.fixture()
def client():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(screener_router, prefix="/api/v1")
    app.dependency_overrides[get_current_api_key] = lambda: "test-key"
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app, raise_server_exceptions=False)


def test_screener_endpoint_openapi_marks_deprecated(client):
    schema = client.app.openapi()
    post_op = schema["paths"]["/api/v1/screener"]["post"]
    assert post_op.get("deprecated") is True


def test_screener_endpoint_returns_deprecation_headers(client):
    payload = {
        "conditions": [{"indicator": "rsi", "operator": "lt", "value": 30}],
        "logic": "AND",
        "max_results": 10,
    }

    mock_db = MagicMock()
    mock_query = mock_db.query.return_value
    mock_query.order_by.return_value.all.return_value = []

    client.app.dependency_overrides[get_db] = lambda: mock_db

    resp = client.post("/api/v1/screener", json=payload)
    assert resp.status_code == 200
    assert resp.headers.get("deprecation") == "true"
    assert "Deprecated" in resp.headers.get("warning", "")
    data = resp.json()
    assert data["success"] is True
    assert data["results"] == []


def test_screener_rejects_unsupported_indicator(client):
    payload = {
        "conditions": [{"indicator": "unknown_metric", "operator": "lt", "value": 30}],
        "logic": "AND",
    }
    resp = client.post("/api/v1/screener", json=payload)
    assert resp.status_code == 422


def test_screener_batch_early_exit(client):
    mock_db = MagicMock()
    stocks = [
        Stock(code=f"sh.60000{i}", name=f"Stock{i}", market="sh")
        for i in range(120)
    ]
    mock_query = mock_db.query.return_value
    mock_query.order_by.return_value.all.return_value = stocks
    client.app.dependency_overrides[get_db] = lambda: mock_db

    # Mock realtime_service to return valid bars so conditions match
    mock_bars = [
        {"date": f"2026-01-{i:02d}", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.0 + i * 0.1, "vol": 10000}
        for i in range(1, 31)
    ]
    with patch("app.api.screener.realtime_service.normalise_bars", return_value=mock_bars):
        payload = {
            "conditions": [{"indicator": "price_change", "operator": "gt", "value": 0}],
            "logic": "AND",
            "max_results": 5,
        }
        resp = client.post("/api/v1/screener", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["results"]) == 5
