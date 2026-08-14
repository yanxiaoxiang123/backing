from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.config import settings
from app.services.realtime_service import RealtimeService


@pytest.fixture
def fresh_service():
    original_servers = settings.MOOTDX_SERVERS
    original_timeout = settings.MOOTDX_TIMEOUT_S
    settings.MOOTDX_SERVERS = "10.0.0.1:7709,10.0.0.2:7709"
    settings.MOOTDX_TIMEOUT_S = 0.25
    RealtimeService._selected_server = None
    RealtimeService._unhealthy_until.clear()
    RealtimeService._discard_client(unhealthy=False)
    yield RealtimeService()
    RealtimeService._discard_client(unhealthy=False)
    RealtimeService._selected_server = None
    RealtimeService._unhealthy_until.clear()
    settings.MOOTDX_SERVERS = original_servers
    settings.MOOTDX_TIMEOUT_S = original_timeout


def frame(close: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "datetime": "2026-08-14 15:00",
                "open": close - 0.1,
                "high": close + 0.1,
                "low": close - 0.2,
                "close": close,
                "vol": 1000,
                "amount": 10000,
            }
        ]
    )


class TestRealtimeClientSelection:
    def test_explicit_server_avoids_mootdx_bestip_scan(self, fresh_service):
        mock_client = MagicMock()
        mock_client.bars.return_value = frame()

        with patch("mootdx.quotes.Quotes.factory", return_value=mock_client) as factory:
            client = fresh_service.get_client()

        assert client is mock_client
        factory.assert_called_once_with(
            market="std",
            server=("10.0.0.1", 7709),
            timeout=0.25,
            auto_retry=False,
            raise_exception=True,
        )

    def test_falls_back_when_first_server_times_out(self, fresh_service):
        second_client = MagicMock()
        second_client.bars.return_value = frame()

        with patch(
            "mootdx.quotes.Quotes.factory",
            side_effect=[TimeoutError("timed out"), second_client],
        ) as factory:
            client = fresh_service.get_client()

        assert client is second_client
        assert factory.call_count == 2
        assert RealtimeService._selected_server == ("10.0.0.2", 7709)

    def test_returns_none_when_all_servers_fail(self, fresh_service):
        with patch(
            "mootdx.quotes.Quotes.factory", side_effect=TimeoutError("timed out")
        ):
            assert fresh_service.get_client() is None


class TestRealtimeBars:
    def test_runtime_failure_reconnects_to_next_server(self, fresh_service):
        first_client = MagicMock()
        first_client.bars.side_effect = [frame(), TimeoutError("connection lost")]
        second_client = MagicMock()
        second_client.bars.return_value = frame(11.0)

        with patch(
            "mootdx.quotes.Quotes.factory",
            side_effect=[first_client, second_client],
        ):
            result = fresh_service.bars("600036", offset=10)

        assert result.iloc[-1]["close"] == 11.0
        assert RealtimeService._selected_server == ("10.0.0.2", 7709)

    def test_returns_empty_frame_when_client_init_fails(self, fresh_service):
        with patch(
            "mootdx.quotes.Quotes.factory", side_effect=ConnectionError("offline")
        ):
            assert fresh_service.bars("600036").empty

    def test_normalises_mootdx_columns(self, fresh_service):
        mock_client = MagicMock()
        mock_client.bars.return_value = frame(38.46)
        with patch("mootdx.quotes.Quotes.factory", return_value=mock_client):
            result = fresh_service.normalise_bars("600036", offset=1)

        assert result == [
            {
                "date": "2026-08-14",
                "open": pytest.approx(38.36),
                "high": pytest.approx(38.56),
                "low": pytest.approx(38.26),
                "close": 38.46,
                "volume": 1000.0,
                "amount": 10000.0,
                "symbol": "600036",
            }
        ]


class TestRealtimeHTTPHandlerGracefulDegradation:
    def test_get_realtime_bars_returns_empty_data_on_failure(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.realtime import router as realtime_router
        from app.auth import get_current_api_key

        app = FastAPI()
        app.include_router(realtime_router, prefix="/api/v1")
        app.dependency_overrides[get_current_api_key] = lambda: "test"

        with patch("app.api.realtime.realtime_service") as service:
            service.normalise_bars.side_effect = ValueError("provider failed")
            response = TestClient(app).get("/api/v1/realtime/600036?period=daily")

        assert response.status_code == 200
        assert response.json() == {"success": True, "code": "600036", "data": []}
