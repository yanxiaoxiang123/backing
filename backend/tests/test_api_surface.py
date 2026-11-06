"""Route cleanup must preserve the task APIs used by the current frontend."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import screener_agent
from app.auth import get_current_api_key


def test_application_exposes_current_routes_without_retired_endpoints():
    from main import app

    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/dashboard",
        "/api/v1/screener",
        "/api/v1/agent/indices",
        "/api/v1/agent/market/analyze",
    ):
        assert path not in paths

    for path in (
        "/api/v1/screener/submit",
        "/api/v1/screener/history",
        "/api/v1/screener/{job_id}",
        "/api/v1/agent/analyze/submit",
        "/api/v1/agent/analyze",
        "/api/v1/agent/history",
        "/api/v1/agent-chats",
        "/api/v1/dl/predict/submit",
        "/api/v1/dl/backtest/submit",
        "/api/v1/dl/predict",
        "/api/v1/dl/backtest",
    ):
        assert path in paths


@pytest.fixture()
def screener_client(monkeypatch):
    app = FastAPI()
    app.include_router(screener_agent.router, prefix="/api/v1")
    app.dependency_overrides[get_current_api_key] = lambda: "test-key"
    monkeypatch.setattr(screener_agent.limiter, "enabled", False)
    return TestClient(app)


def test_screener_submits_through_shared_task_executor(screener_client, monkeypatch):
    executor = Mock()
    executor.submit.return_value = SimpleNamespace(id="new-screener-job")
    monkeypatch.setattr(screener_agent, "get_task_executor", lambda: executor)

    response = screener_client.post("/api/v1/screener/submit")

    assert response.status_code == 200
    assert response.json() == {"job_id": "new-screener-job"}
    executor.submit.assert_called_once_with(job_type="screener")


def test_retired_synchronous_screener_is_not_available(screener_client):
    response = screener_client.post(
        "/api/v1/screener",
        json={"conditions": [{"indicator": "rsi", "operator": "lt", "value": 30}]},
    )
    assert response.status_code == 404
