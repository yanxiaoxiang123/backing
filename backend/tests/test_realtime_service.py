from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.config import settings
from app.services.realtime_service import FetchResult, RealtimeService
from app.services.tasks.metrics import task_metrics


@pytest.fixture
def fresh_service():
    original_servers = settings.MOOTDX_SERVERS
    original_timeout = settings.MOOTDX_TIMEOUT_S
    settings.MOOTDX_SERVERS = "10.0.0.1:7709,10.0.0.2:7709"
    settings.MOOTDX_TIMEOUT_S = 0.25
    RealtimeService._selected_server = None
    RealtimeService._unhealthy_until.clear()
    RealtimeService._discard_client(unhealthy=False)
    RealtimeService._bars_cache.clear()
    RealtimeService._snapshot_cache.clear()
    RealtimeService._failover_count = 0
    RealtimeService._request_count = 0
    RealtimeService._last_failure_reason.clear()
    task_metrics._counters.clear()
    yield RealtimeService()
    RealtimeService._discard_client(unhealthy=False)
    RealtimeService._selected_server = None
    RealtimeService._unhealthy_until.clear()
    RealtimeService._bars_cache.clear()
    RealtimeService._snapshot_cache.clear()
    RealtimeService._failover_count = 0
    RealtimeService._request_count = 0
    RealtimeService._last_failure_reason.clear()
    task_metrics._counters.clear()
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


class TestFetchResultEnvelope:
    def test_fetch_bars_marks_empty_when_provider_returns_no_rows(self, fresh_service):
        """Probe succeeds (non-empty) but the actual data call yields empty —
        that is a legitimate 'no data' answer, not a provider outage."""
        mock_client = MagicMock()

        def _bars(symbol: str, frequency: int = 9, offset: int = 1):
            # Probe symbol is 000001, offset=1 — return a row so the probe
            # passes. The real call uses the test symbol with offset=750.
            if symbol == "000001" and offset == 1:
                return frame(close=1.0)
            return pd.DataFrame()

        mock_client.bars.side_effect = _bars

        with patch(
            "mootdx.quotes.Quotes.factory", return_value=mock_client
        ):
            result = fresh_service.fetch_bars("600036", "daily")

        assert result.status == "empty"
        assert result.data == []
        assert result.provider == "mootdx"
        assert result.selected_server == ("10.0.0.1", 7709)
        assert result.cache_age_ms == 0

    def test_fetch_bars_marks_unavailable_when_all_servers_fail(self, fresh_service):
        """All servers in cooldown → envelope reports 'unavailable'."""
        with patch(
            "mootdx.quotes.Quotes.factory",
            side_effect=TimeoutError("timed out"),
        ):
            result = fresh_service.fetch_bars("600036", "daily")

        assert result.status == "unavailable"
        assert result.data == []
        assert result.reason == "no_healthy_server"
        assert result.provider == "mootdx"

    def test_fetch_bars_marks_ok_when_data_returns(self, fresh_service):
        mock_client = MagicMock()
        mock_client.bars.return_value = frame(close=12.5)

        with patch(
            "mootdx.quotes.Quotes.factory", return_value=mock_client
        ):
            result = fresh_service.fetch_bars("600036", "daily")

        assert result.status == "ok"
        assert result.data and result.data[0]["close"] == 12.5
        assert result.cache_age_ms == 0


class TestRealtimeShortTermCache:
    def test_repeated_fetch_bars_serves_from_cache(self, fresh_service):
        mock_client = MagicMock()
        mock_client.bars.return_value = frame(close=20.0)
        with patch(
            "mootdx.quotes.Quotes.factory", return_value=mock_client
        ):
            first = fresh_service.fetch_bars("600036", "daily")
            calls_after_first = mock_client.bars.call_count
            # Second call should hit the cache without invoking the client
            second = fresh_service.fetch_bars("600036", "daily")

        assert first.status == "ok"
        assert second.status == "ok"
        assert second.cache_age_ms >= 0
        # Cache hit means the underlying mock is not invoked again
        assert mock_client.bars.call_count == calls_after_first

    def test_fetch_indices_caches_per_symbol(self, fresh_service):
        # Two rows so each index snapshot can compute prev_close.
        two_rows = pd.concat(
            [frame(close=3990.0), frame(close=4000.0)], ignore_index=True
        )
        mock_client = MagicMock()
        mock_client.bars.return_value = two_rows
        mock_client.index.return_value = two_rows
        with patch(
            "mootdx.quotes.Quotes.factory", return_value=mock_client
        ):
            first = fresh_service.fetch_indices()
            calls_after_first = mock_client.index.call_count
            second = fresh_service.fetch_indices()

        assert first.status == "ok"
        assert second.status == "ok"
        assert second.cache_age_ms >= 0
        assert mock_client.index.call_count == calls_after_first


class TestRealtimeMetrics:
    def _counter_value(self, name: str, **tags) -> int:
        for counter in task_metrics.snapshot()["counters"]:
            if counter["name"] != name:
                continue
            if all(counter.get(k) == v for k, v in tags.items()):
                return int(counter["value"])
        return 0

    def test_request_and_failover_counters(self, fresh_service):
        first_client = MagicMock()
        first_client.bars.side_effect = TimeoutError("blip")
        second_client = MagicMock()
        second_client.bars.return_value = frame()

        with patch(
            "mootdx.quotes.Quotes.factory",
            side_effect=[first_client, second_client],
        ):
            fresh_service.fetch_bars("600036", "daily")

        assert (
            self._counter_value("realtime.request", endpoint="bars") >= 1
        )
        assert (
            self._counter_value("realtime.failover", endpoint="connect") >= 1
        )

    def test_provider_unavailable_counter(self, fresh_service):
        with patch(
            "mootdx.quotes.Quotes.factory",
            side_effect=TimeoutError("timed out"),
        ):
            fresh_service.fetch_bars("600036", "daily")

        assert (
            self._counter_value(
                "realtime.provider_unavailable", endpoint="bars"
            )
            >= 1
        )

    def test_provider_health_snapshot(self, fresh_service):
        mock_client = MagicMock()
        mock_client.bars.return_value = frame()
        with patch(
            "mootdx.quotes.Quotes.factory", return_value=mock_client
        ):
            fresh_service.fetch_bars("600036", "daily")

        snapshot = fresh_service.get_provider_health()
        assert snapshot["selected_server"] == ("10.0.0.1", 7709)
        assert snapshot["total_servers"] == 2
        assert snapshot["healthy_count"] == 2
        assert "counters" in snapshot


class TestFetchResultSerialization:
    def test_envelope_is_json_serializable(self):
        result = FetchResult(
            status="ok",
            data=[{"date": "2026-08-14", "close": 10.0}],
            provider="mootdx",
            selected_server=("127.0.0.1", 7709),
        )
        payload = result.to_dict()
        assert payload["status"] == "ok"
        assert payload["provider"] == "mootdx"
        assert payload["selected_server"] == {"host": "127.0.0.1", "port": 7709}
