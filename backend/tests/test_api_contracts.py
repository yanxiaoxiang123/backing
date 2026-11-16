"""API 合约测试：真实路由 + 依赖覆盖，验证错误形状、任务端点、取消语义。

不触碰真实数据提供方：仅覆盖不依赖外部服务的端点。
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.services.job_store as job_store_module
from app.api.routes import router as api_router
from app.api.screener_agent import router as screener_agent_router
from app.api.strategies import router as strategies_router
from app.auth import get_current_api_key
from app.config import Base, get_db
from app.error_handlers import register_error_handlers
from app.models.models import DailyKline, Stock
from app.services.job_store import job_store


@pytest.fixture()
def db_session(tmp_path):
    """File-backed temp DB patched into job_store (worker-thread safe)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'contracts_test.db'}",
        connect_args={"timeout": 10},
    )
    Base.metadata.create_all(bind=engine)
    original = job_store_module.SessionLocal
    job_store_module.SessionLocal = sessionmaker(bind=engine)
    yield
    job_store_module.SessionLocal = original


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1", tags=["api"])
    app.include_router(screener_agent_router, prefix="/api/v1")
    app.include_router(strategies_router)
    app.dependency_overrides[get_current_api_key] = lambda: "test-key"
    return TestClient(app, raise_server_exceptions=False)


class TestJobEndpoints:
    def test_job_not_found_404_shape(self, client):
        resp = client.get("/api/v1/jobs/does-not-exist")
        assert resp.status_code == 404
        body = resp.json()["error"]
        assert body["code"] == "not_found"

    def test_job_metrics_endpoint(self, client):
        resp = client.get("/api/v1/jobs/metrics")
        assert resp.status_code == 200
        payload = resp.json()
        assert set(payload.keys()) == {"started_at", "counters", "durations"}

    def test_job_metrics_registered_before_job_id(self, client):
        """/jobs/metrics 必须优先于 /jobs/{job_id} 匹配。"""
        resp = client.get("/api/v1/jobs/metrics")
        assert resp.status_code == 200

    def test_cancel_pending_job(self, client, db_session):
        job = job_store.create("sync_stocks")
        resp = client.post(f"/api/v1/jobs/{job.id}/cancel")
        assert resp.status_code == 200
        assert resp.json() == {"status": "cancelled"}
        record = job_store.get(job.id)
        assert record.status == "failed"
        assert record.error == "Cancelled"

    def test_cancel_is_idempotent(self, client, db_session):
        job = job_store.create("sync_stocks")
        first = client.post(f"/api/v1/jobs/{job.id}/cancel")
        second = client.post(f"/api/v1/jobs/{job.id}/cancel")
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json() == {"status": "cancelled"}

    def test_cancel_completed_job_conflict(self, client, db_session):
        job = job_store.create("sync_stocks")
        job_store.update(job.id, status="completed", progress=1.0)
        resp = client.post(f"/api/v1/jobs/{job.id}/cancel")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "conflict"

    def test_job_status_returns_record(self, client, db_session):
        job = job_store.create("sync_stocks", job_key="k-status")
        resp = client.get(f"/api/v1/jobs/{job.id}")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["id"] == job.id
        assert payload["job_key"] == "k-status"
        assert payload["status"] == "pending"


class TestStrategiesContract:
    def test_list_strategies_returns_13(self, client):
        resp = client.get("/api/v1/strategies")
        assert resp.status_code == 200
        payload = resp.json()
        assert len(payload) == 13
        names = {s["name"] for s in payload}
        assert "ma_cross" in names
        for item in payload:
            assert set(item.keys()) == {"name", "description", "parameters"}

    def test_unknown_strategy_404_shape(self, client):
        resp = client.get("/api/v1/strategies/not-a-strategy")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_validation_error_422_shape(self, client):
        """请求体校验失败 → 422 + validation_error。"""
        resp = client.post(
            "/api/v1/strategies/optimize",
            json={"strategy_name": "ma_cross"},  # 缺必填字段
        )
        assert resp.status_code == 422
        body = resp.json()["error"]
        assert body["code"] == "validation_error"
        assert "detail" in body

    def test_strategy_backtest_is_saved_and_exposed_in_history(self, tmp_path):
        engine = create_engine(f"sqlite:///{tmp_path / 'strategy_backtest.db'}")
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine)
        session = session_factory()
        session.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
        for idx, close in enumerate([10, 10.2, 10.5, 10.9, 11.2, 10.8, 10.4, 10.0]):
            session.add(
                DailyKline(
                    stock_code="sh.600000",
                    date=date(2024, 1, 1) + timedelta(days=idx),
                    open=close - 0.1,
                    high=close + 0.2,
                    low=close - 0.2,
                    close=close,
                    volume=100000,
                    amount=close * 100000,
                )
            )
        session.commit()

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(strategies_router)
        app.include_router(api_router, prefix="/api/v1")
        app.dependency_overrides[get_current_api_key] = lambda: "test-key"
        app.dependency_overrides[get_db] = lambda: session_factory()

        response = TestClient(app).post(
            "/api/v1/strategies/backtest",
            json={
                "strategy_name": "ma_cross",
                "stock_code": "sh.600000",
                "start_date": "2024-01-01",
                "end_date": "2024-01-08",
                "initial_capital": 100000,
                "parameters": {"short_period": 2, "long_period": 3},
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["result_id"] > 0
        assert payload["parameters"] == {"short_period": 2, "long_period": 3}
        history = TestClient(app).get("/api/v1/backtest/results")
        assert history.status_code == 200
        assert history.headers.get("x-total-count") == "1"
        assert history.json()[0]["id"] == payload["result_id"]
        queries = []

        def capture_sql(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        event.listen(engine, "before_cursor_execute", capture_sql)
        try:
            detail = TestClient(app).get(f"/api/v1/backtest/{payload['result_id']}")
        finally:
            event.remove(engine, "before_cursor_execute", capture_sql)

        assert detail.status_code == 200
        data = detail.json()
        assert data["portfolio_values"]
        assert data["strategy_name"] is not None
        # Verify joinedload: exactly 1 SQL query issued to load backtest result, trades, and strategy
        assert len(queries) == 1
        assert "strategies" in queries[0].lower()
        assert "backtest_trades" in queries[0].lower()

        # Verify POST /api/v1/backtest executes directly via BacktestExecutor
        legacy_resp = TestClient(app).post(
            "/api/v1/backtest",
            json={
                "strategy_type": "ma_cross",
                "stock_code": "sh.600000",
                "start_date": "2024-01-01",
                "end_date": "2024-01-08",
                "initial_capital": 100000,
            },
        )
        assert legacy_resp.status_code == 200, legacy_resp.text
        assert legacy_resp.json()["id"] > 0
        assert legacy_resp.json()["stock_code"] == "sh.600000"

    def test_strategy_signal_failure_raises_in_dev_and_falls_back_in_prod(
        self, tmp_path, monkeypatch
    ):
        engine = create_engine(f"sqlite:///{tmp_path / 'strategy_signals.db'}")
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine)
        session = session_factory()
        session.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
        for idx, close in enumerate([10, 10.2, 10.5, 10.9, 11.2, 10.8, 10.4, 10.0]):
            session.add(
                DailyKline(
                    stock_code="sh.600000",
                    date=date(2024, 1, 1) + timedelta(days=idx),
                    open=close - 0.1,
                    high=close + 0.2,
                    low=close - 0.2,
                    close=close,
                    volume=100000,
                    amount=close * 100000,
                )
            )
        session.commit()

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(strategies_router)
        app.dependency_overrides[get_current_api_key] = lambda: "test-key"
        app.dependency_overrides[get_db] = lambda: session_factory()

        req_body = {
            "strategy_name": "ma_cross",
            "stock_code": "sh.600000",
            "start_date": "2024-01-01",
            "end_date": "2024-01-08",
        }

        from app.config import settings
        from app.services.strategy.registry import StrategyRegistry

        strat_cls = StrategyRegistry.get("ma_cross")

        def buggy_generate_signals(self, df):
            raise ValueError("custom strategy bug")

        monkeypatch.setattr(strat_cls, "generate_signals", buggy_generate_signals)

        # 1. In dev environment: raises exception directly, without falling back
        monkeypatch.setattr(settings, "APP_ENV", "development")
        with pytest.raises(ValueError, match="custom strategy bug"):
            TestClient(app, raise_server_exceptions=True).post(
                "/api/v1/strategies/signals", json=req_body
            )

        # 2. In prod environment: falls back to MA cross with ERROR log
        from app.api.strategies import routes as strategies_routes_mod

        error_logs = []
        monkeypatch.setattr(settings, "APP_ENV", "production")
        monkeypatch.setattr(
            strategies_routes_mod.logger,
            "error",
            lambda msg, *args, **kwargs: error_logs.append((msg, args, kwargs)),
        )

        resp = TestClient(app, raise_server_exceptions=True).post(
            "/api/v1/strategies/signals", json=req_body
        )
        assert resp.status_code == 200
        assert len(error_logs) == 1
        assert "Strategy signal generation failed, falling back to MA cross" in error_logs[0][0]
        assert error_logs[0][2].get("exc_info") is True


class TestScreenerHistoryContract:
    def test_history_returns_only_persisted_screener_jobs(self, client, db_session):
        job_store.create("sync_stocks")
        job = job_store.create("screener")
        job_store.update(
            job.id,
            status="completed",
            progress=1.0,
            result={"success": True, "total_scanned": 5200, "results": []},
        )

        response = client.get("/api/v1/screener/history")

        assert response.status_code == 200
        payload = response.json()
        assert [item["id"] for item in payload] == [job.id]
        assert payload[0]["result"]["total_scanned"] == 5200


class TestRealtimeHealthEndpoint:
    def test_health_returns_provider_snapshot(self):
        from fastapi.testclient import TestClient

        from app.api.realtime import router as realtime_router

        app = FastAPI()
        app.include_router(realtime_router, prefix="/api/v1")
        app.dependency_overrides[get_current_api_key] = lambda: "test"

        resp = TestClient(app).get("/api/v1/realtime/health")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["provider"] == "mootdx"
        assert "selected_server" in payload
        assert "healthy_count" in payload
        assert "total_servers" in payload
        assert "counters" in payload


class TestRealtimeUnavailableContract:
    def _build_app(self):
        from fastapi import FastAPI

        from app.api.realtime import router as realtime_router
        from app.auth import get_current_api_key
        from app.error_handlers import register_error_handlers

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(realtime_router, prefix="/api/v1")
        app.dependency_overrides[get_current_api_key] = lambda: "test"
        return app

    def test_bars_returns_503_when_provider_unavailable(self):
        from fastapi.testclient import TestClient

        from app.services.realtime_service import (
            STATUS_UNAVAILABLE,
            FetchResult,
        )

        app = self._build_app()
        with patch("app.api.realtime.realtime_service") as service:
            service.fetch_bars.return_value = FetchResult(
                status=STATUS_UNAVAILABLE, reason="no_healthy_server"
            )
            response = TestClient(app).get("/api/v1/realtime/600036?period=daily")

        assert response.status_code == 503
        body = response.json()["error"]
        assert body["code"] == "provider_unavailable"
        assert body["provider"] == "mootdx"
        assert body["retryable"] is True
        assert body["reason"] == "no_healthy_server"

    def test_bars_returns_200_with_empty_data_on_empty_status(self):
        from fastapi.testclient import TestClient

        from app.services.realtime_service import (
            STATUS_EMPTY,
            FetchResult,
        )

        app = self._build_app()
        with patch("app.api.realtime.realtime_service") as service:
            service.fetch_bars.return_value = FetchResult(status=STATUS_EMPTY)
            response = TestClient(app).get("/api/v1/realtime/600036?period=daily")

        assert response.status_code == 200
        assert response.json() == {"success": True, "code": "600036", "data": []}

    def test_quotes_returns_503_when_provider_unavailable(self):
        from fastapi.testclient import TestClient

        from app.services.realtime_service import (
            STATUS_UNAVAILABLE,
            FetchResult,
        )

        app = self._build_app()
        with patch("app.api.realtime.realtime_service") as service:
            service.fetch_quotes.return_value = FetchResult(
                status=STATUS_UNAVAILABLE, reason="no_healthy_server"
            )
            response = TestClient(app).get(
                "/api/v1/realtime/quotes?codes=600036,000001"
            )

        assert response.status_code == 503
        body = response.json()["error"]
        assert body["code"] == "provider_unavailable"
        assert body["provider"] == "mootdx"

    def test_indices_returns_503_when_provider_unavailable(self):
        from fastapi.testclient import TestClient

        from app.services.realtime_service import (
            STATUS_UNAVAILABLE,
            FetchResult,
        )

        app = self._build_app()
        with patch("app.api.realtime.realtime_service") as service:
            service.fetch_indices.return_value = FetchResult(
                status=STATUS_UNAVAILABLE, reason="no_healthy_server"
            )
            response = TestClient(app).get("/api/v1/realtime/indices")

        assert response.status_code == 503


class TestBacktestHistoryAndStocksPagination:
    def _build_app(self, tmp_path):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.api.routes import router as api_router
        from app.auth import get_current_api_key
        from app.config import Base, get_db
        from app.error_handlers import register_error_handlers
        from app.models.models import BacktestResult, Stock, Strategy

        engine = create_engine(f"sqlite:///{tmp_path / 'pagination_test.db'}")
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine)
        session = session_factory()

        st1 = Strategy(name="双均线策略", strategy_type="ma_cross")
        st2 = Strategy(name="布林带突破", strategy_type="bollinger")
        session.add_all([st1, st2])
        session.commit()

        sk1 = Stock(code="sh.600000", name="浦发银行", market="sh")
        sk2 = Stock(code="sz.000001", name="平安银行", market="sz")
        sk3 = Stock(code="sh.600519", name="贵州茅台", market="sh")
        session.add_all([sk1, sk2, sk3])
        session.commit()

        # Add 3 backtest results
        b1 = BacktestResult(
            strategy_id=st1.id,
            stock_code="sh.600000",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
            initial_capital=100000,
            final_capital=120000,
            total_return=20.0,
            annual_return=20.0,
            total_trades=4,
        )
        b2 = BacktestResult(
            strategy_id=st2.id,
            stock_code="sz.000001",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
            initial_capital=100000,
            final_capital=105000,
            total_return=5.0,
            annual_return=5.0,
            total_trades=2,
        )
        b3 = BacktestResult(
            strategy_id=st1.id,
            stock_code="sz.000001",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
            initial_capital=100000,
            final_capital=115000,
            total_return=15.0,
            annual_return=15.0,
            total_trades=3,
        )
        session.add_all([b1, b2, b3])
        session.commit()

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(api_router, prefix="/api/v1")
        app.dependency_overrides[get_current_api_key] = lambda: "test-key"
        app.dependency_overrides[get_db] = lambda: session_factory()
        return TestClient(app)

    def test_backtest_results_pagination_total_count(self, tmp_path):
        client = self._build_app(tmp_path)
        resp = client.get("/api/v1/backtest/results?skip=0&limit=2")
        assert resp.status_code == 200
        assert resp.headers.get("x-total-count") == "3"
        assert len(resp.json()) == 2

    def test_backtest_results_filter_by_stock_code(self, tmp_path):
        client = self._build_app(tmp_path)
        # Search by bare code "600000"
        resp = client.get("/api/v1/backtest/results?stock_code=600000")
        assert resp.status_code == 200
        assert resp.headers.get("x-total-count") == "1"
        data = resp.json()
        assert len(data) == 1
        assert data[0]["stock_code"] == "sh.600000"

    def test_backtest_results_filter_by_strategy_name(self, tmp_path):
        client = self._build_app(tmp_path)
        resp = client.get("/api/v1/backtest/results?strategy_name=均线")
        assert resp.status_code == 200
        assert resp.headers.get("x-total-count") == "2"
        data = resp.json()
        assert len(data) == 2
        for item in data:
            assert "均线" in item["strategy_name"]

    def test_backtest_results_sort_by_return(self, tmp_path):
        client = self._build_app(tmp_path)
        resp = client.get("/api/v1/backtest/results?sort=return")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        returns = [float(item["total_return"]) for item in data]
        assert returns == [20.0, 15.0, 5.0]

    def test_stocks_cursor_preserves_total_count(self, tmp_path):
        client = self._build_app(tmp_path)
        # 3 stocks created, fetch with cursor=1
        resp = client.get("/api/v1/stocks?cursor=1&limit=1")
        assert resp.status_code == 200
        # X-Total-Count must be total count before cursor filter (3)
        assert resp.headers.get("x-total-count") == "3"
