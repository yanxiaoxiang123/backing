"""Public read-only market gateway tests.

Covers the fixed allowlist, anonymous access, partial provider outages,
conservative staleness metadata, bounded caches/failure caching and the
Tencent minute-series adapter.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.public_market import router as public_market_router
from app.error_handlers import register_error_handlers
from app.limiter import limiter
from app.services import public_market as public_market_module
from app.services.public_market import (
    _parse_intraday_payload,
    public_market_service,
)
from app.services.realtime_service import FetchResult

SHANGHAI = timezone(timedelta(hours=8))


def _market_at(seconds_ago: int = 5) -> str:
    return (datetime.now(SHANGHAI) - timedelta(seconds=seconds_ago)).isoformat(
        timespec="seconds"
    )


def _quote_row(
    symbol: str,
    name: str = "测试",
    close: float = 10.0,
    market_at: str | None = None,
) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "close": close,
        "prev_close": 9.5,
        "open": 9.8,
        "high": 10.2,
        "low": 9.7,
        "volume": 1000.0,
        "amount": 10000.0,
        "change": 0.5,
        "change_percent": 5.26,
        "market_at": market_at or _market_at(),
    }


def _index_row(symbol: str, name: str = "指数", close: float = 3000.0) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "close": close,
        "prev_close": 2990.0,
        "change": 10.0,
        "change_percent": 0.33,
        "market_at": _market_at(),
    }


@pytest.fixture(autouse=True)
def _reset_public_state():
    public_market_service.clear_cache()
    limiter.reset()
    yield
    public_market_service.clear_cache()
    limiter.reset()


@pytest.fixture()
def client():
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(public_market_router)
    register_error_handlers(app)
    return TestClient(app, raise_server_exceptions=False)


def _patch_provider(monkeypatch, *, quotes, indices):
    monkeypatch.setattr(
        public_market_module.realtime_service, "fetch_quotes", quotes
    )
    monkeypatch.setattr(
        public_market_module.realtime_service, "fetch_indices", indices
    )


def test_market_is_anonymous_and_returns_fixed_allowlist(client, monkeypatch):
    now = datetime.now(SHANGHAI).timestamp()

    def fake_quotes(symbols):
        assert symbols == ["600519", "300750", "600036"]
        return FetchResult(
            status="ok",
            data=[
                _quote_row("600519", "贵州茅台", 1500.0),
                _quote_row("sh.600519", "贵州茅台", 1500.0),
                _quote_row("000001", "非公开标的", 10.0),
                _quote_row("300750", "宁德时代", 200.0),
                _quote_row("600036", "招商银行", 40.0),
            ],
            provider="tencent",
            fetched_at=now - 1,
            market_at=_market_at(),
        )

    def fake_indices():
        return FetchResult(
            status="ok",
            data=[
                _index_row("000001", "上证指数"),
                _index_row("399001", "深证成指"),
                _index_row("399006", "创业板指"),
                _index_row("000300", "沪深300"),
            ],
            provider="tencent",
            fetched_at=now - 1,
            market_at=_market_at(),
        )

    _patch_provider(monkeypatch, quotes=fake_quotes, indices=fake_indices)

    response = client.get("/api/v1/public/market")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"indices", "quotes"}
    for section in ("indices", "quotes"):
        envelope = body[section]
        assert set(envelope) == {
            "status",
            "data",
            "provider",
            "market_at",
            "fetched_at",
            "served_at",
            "cache_age_ms",
            "stale",
            "reason",
        }
        assert "selected_server" not in envelope
        assert "cache_source" not in envelope
    assert [row["symbol"] for row in body["quotes"]["data"]] == [
        "sh.600519",
        "sz.300750",
        "sh.600036",
    ]
    assert [row["symbol"] for row in body["indices"]["data"]] == [
        "sh.000001",
        "sz.399001",
        "sz.399006",
    ]


def test_partial_outage_keeps_the_healthy_section(client, monkeypatch):
    def fake_quotes(symbols):
        return FetchResult(
            status="unavailable",
            provider="tencent",
            reason="tencent_unavailable",
        )

    def fake_indices():
        return FetchResult(
            status="ok",
            data=[_index_row("000001", "上证指数")],
            provider="tencent",
            fetched_at=datetime.now(SHANGHAI).timestamp(),
            market_at=_market_at(),
        )

    _patch_provider(monkeypatch, quotes=fake_quotes, indices=fake_indices)

    response = client.get("/api/v1/public/market")

    assert response.status_code == 200
    body = response.json()
    assert body["quotes"]["status"] == "unavailable"
    assert body["quotes"]["data"] == []
    assert body["quotes"]["reason"] == "tencent_unavailable"
    assert body["indices"]["status"] == "ok"
    assert body["indices"]["data"][0]["symbol"] == "sh.000001"


def test_stale_metadata_is_propagated_and_cache_age_grows(client, monkeypatch):
    now = datetime.now(SHANGHAI).timestamp()

    def fake_quotes(symbols):
        return FetchResult(
            status="ok",
            data=[_quote_row("600519", "贵州茅台")],
            provider="tencent",
            fetched_at=now - 30,
            market_at=_market_at(),
            stale=True,
            cache_age_ms=4200,
        )

    def fake_indices():
        return FetchResult(
            status="ok",
            data=[_index_row("000001", "上证指数")],
            provider="tencent",
            fetched_at=now - 30,
            market_at=_market_at(),
        )

    _patch_provider(monkeypatch, quotes=fake_quotes, indices=fake_indices)

    first = client.get("/api/v1/public/market").json()["quotes"]
    second = client.get("/api/v1/public/market").json()["quotes"]

    assert first["stale"] is True
    assert first["cache_age_ms"] >= 4200
    assert second["stale"] is True
    assert second["cache_age_ms"] >= first["cache_age_ms"]


def test_old_market_timestamp_is_reported_stale(client, monkeypatch):
    def fake_quotes(symbols):
        return FetchResult(
            status="ok",
            data=[_quote_row("600519", "贵州茅台", market_at=_market_at(600))],
            provider="tencent",
            fetched_at=datetime.now(SHANGHAI).timestamp(),
            market_at=_market_at(600),
        )

    def fake_indices():
        return FetchResult(
            status="ok",
            data=[_index_row("000001", "上证指数")],
            provider="tencent",
            fetched_at=datetime.now(SHANGHAI).timestamp(),
            market_at=_market_at(5),
        )

    _patch_provider(monkeypatch, quotes=fake_quotes, indices=fake_indices)

    body = client.get("/api/v1/public/market").json()

    assert body["quotes"]["stale"] is True
    assert body["indices"]["stale"] is False


def test_sections_are_cached_and_cache_is_bounded(client, monkeypatch):
    calls = {"quotes": 0, "indices": 0}

    def fake_quotes(symbols):
        calls["quotes"] += 1
        return FetchResult(
            status="ok",
            data=[_quote_row("600519", "贵州茅台")],
            provider="tencent",
            fetched_at=datetime.now(SHANGHAI).timestamp(),
            market_at=_market_at(),
        )

    def fake_indices():
        calls["indices"] += 1
        return FetchResult(
            status="ok",
            data=[_index_row("000001", "上证指数")],
            provider="tencent",
            fetched_at=datetime.now(SHANGHAI).timestamp(),
            market_at=_market_at(),
        )

    _patch_provider(monkeypatch, quotes=fake_quotes, indices=fake_indices)

    assert client.get("/api/v1/public/market").status_code == 200
    assert client.get("/api/v1/public/market").status_code == 200

    assert calls == {"quotes": 1, "indices": 1}
    assert public_market_service.cache_size() <= public_market_module._MAX_CACHE_ENTRIES


def test_provider_failure_is_cached_instead_of_hammering(client, monkeypatch):
    calls = {"quotes": 0}

    def boom(symbols):
        calls["quotes"] += 1
        raise RuntimeError("provider exploded")

    def fake_indices():
        return FetchResult(
            status="ok",
            data=[_index_row("000001", "上证指数")],
            provider="tencent",
            fetched_at=datetime.now(SHANGHAI).timestamp(),
            market_at=_market_at(),
        )

    _patch_provider(monkeypatch, quotes=boom, indices=fake_indices)

    first = client.get("/api/v1/public/market")
    second = client.get("/api/v1/public/market")

    assert first.status_code == 200
    assert first.json()["quotes"]["status"] == "unavailable"
    assert second.json()["quotes"]["status"] == "unavailable"
    assert calls["quotes"] == 1


@pytest.mark.parametrize(
    "code",
    ["sh.600000", "600519", "sz.000001", "sh.600519x", "", "SH.600519"],
)
def test_intraday_rejects_everything_outside_the_canonical_allowlist(client, code):
    response = client.get(
        "/api/v1/public/market/intraday", params={"code": code}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_symbol"


def test_service_also_rejects_disallowed_intraday_code():
    with pytest.raises(ValueError):
        public_market_service.get_intraday("sh.600000")


def test_intraday_endpoint_shape_has_no_internal_metadata(client, monkeypatch):
    def fake_minutes(code):
        return (
            [
                {
                    "time": "2026-10-30T09:30:00+08:00",
                    "price": 1500.0,
                    "volume": 10,
                }
            ],
            "2026-10-30",
            "2026-10-30T09:30:00+08:00",
        )

    monkeypatch.setattr(public_market_module, "fetch_tencent_minutes", fake_minutes)

    response = client.get(
        "/api/v1/public/market/intraday", params={"code": "sh.600519"}
    )

    assert response.status_code == 200
    envelope = response.json()
    assert envelope["code"] == "sh.600519"
    assert envelope["status"] == "ok"
    assert envelope["provider"] == "tencent"
    assert envelope["data"] == [
        {
            "time": "2026-10-30T09:30:00+08:00",
            "price": 1500.0,
            "volume": 10,
        }
    ]
    assert envelope["volume_unit"] == "lots"
    assert envelope["volume_kind"] == "interval"
    assert envelope["trade_date"] == "2026-10-30"
    assert envelope["market_at"] == "2026-10-30T09:30:00+08:00"
    assert "selected_server" not in envelope
    assert "cache_source" not in envelope


def test_intraday_failure_is_cached(client, monkeypatch):
    calls = {"count": 0}

    def boom(code):
        calls["count"] += 1
        raise RuntimeError("minute endpoint down")

    monkeypatch.setattr(public_market_module, "fetch_tencent_minutes", boom)

    first = client.get(
        "/api/v1/public/market/intraday", params={"code": "sh.600519"}
    )
    second = client.get(
        "/api/v1/public/market/intraday", params={"code": "sh.600519"}
    )

    assert first.status_code == 200
    assert first.json()["status"] == "unavailable"
    assert first.json()["reason"] == "tencent_intraday_unavailable"
    assert first.json()["data"] == []
    assert second.json()["status"] == "unavailable"
    assert calls["count"] == 1


def test_intraday_parser_uses_real_minutes_and_interval_volume():
    payload = {
        "code": 0,
        "data": {
            "sh600519": {
                "data": {
                    "date": "20261030",
                    "data": [
                        "0930 100.0 100 10000.0",
                        "0931 101.0 150 15000.0",
                        "0932 102.0 140 14000.0",
                        "0933 103.0 180 18000.0",
                        "1131 104.0 200 20000.0",
                        "1300 105.0 210 21000.0",
                        "1500 106.0 260 26000.0",
                        "1506 107.0 270 27000.0",
                    ],
                }
            }
        },
    }

    points, trade_date, market_at = _parse_intraday_payload(payload, "sh600519")

    assert trade_date == "2026-10-30"
    assert [point["time"] for point in points] == [
        "2026-10-30T09:30:00+08:00",
        "2026-10-30T09:31:00+08:00",
        "2026-10-30T09:32:00+08:00",
        "2026-10-30T09:33:00+08:00",
        "2026-10-30T13:00:00+08:00",
        "2026-10-30T15:00:00+08:00",
    ]
    assert [point["volume"] for point in points] == [100, 50, None, 40, 30, 50]
    assert market_at == "2026-10-30T15:00:00+08:00"


def test_intraday_parser_marks_unattributable_intervals_as_null():
    payload = {
        "code": 0,
        "data": {
            "sh600519": {
                "data": {
                    "date": "20261030",
                    "data": [
                        "0930 100.0 100 10000.0",
                        "0931 101.0",
                        "0932 102.0 140 14000.0",
                        "0933 103.0 160 16000.0",
                    ],
                }
            }
        },
    }

    points, _, _ = _parse_intraday_payload(payload, "sh600519")

    assert [point["volume"] for point in points] == [100, None, None, 20]


@pytest.mark.parametrize(
    "row",
    [
        "0930 nan 100 10000.0",
        "0930 100.0 inf 10000.0",
        "0930 -1 100 10000.0",
        "0930 100.0 -5 10000.0",
        "not-a-minute-row",
        "0930",
        "2460 100.0 100 10000.0",
    ],
)
def test_intraday_parser_rejects_invalid_rows(row):
    payload = {
        "code": 0,
        "data": {"sh600519": {"data": {"date": "20261030", "data": [row]}}},
    }

    with pytest.raises(ValueError):
        _parse_intraday_payload(payload, "sh600519")


def test_intraday_parser_rejects_malformed_envelope():
    with pytest.raises(ValueError):
        _parse_intraday_payload({"code": 1, "data": {}}, "sh600519")
    with pytest.raises(ValueError):
        _parse_intraday_payload(
            {"code": 0, "data": {"sh600519": {"data": {"data": []}}}},
            "sh600519",
        )


def test_public_market_is_rate_limited_per_ip(client, monkeypatch):
    def fake_quotes(symbols):
        return FetchResult(
            status="ok",
            data=[_quote_row("600519", "贵州茅台")],
            provider="tencent",
            fetched_at=datetime.now(SHANGHAI).timestamp(),
            market_at=_market_at(),
        )

    def fake_indices():
        return FetchResult(
            status="ok",
            data=[_index_row("000001", "上证指数")],
            provider="tencent",
            fetched_at=datetime.now(SHANGHAI).timestamp(),
            market_at=_market_at(),
        )

    _patch_provider(monkeypatch, quotes=fake_quotes, indices=fake_indices)

    for _ in range(30):
        assert client.get("/api/v1/public/market").status_code == 200
    assert client.get("/api/v1/public/market").status_code == 429


def test_missing_provider_market_timestamp_is_unknown_not_literal_none(client, monkeypatch):
    row = _quote_row("600519")
    row.pop("market_at")
    _patch_provider(
        monkeypatch,
        quotes=lambda symbols: FetchResult(status="ok", data=[row], provider="mootdx", market_at="None"),
        indices=lambda: FetchResult(status="empty"),
    )
    quote = client.get("/api/v1/public/market").json()["quotes"]
    assert quote["market_at"] is None
    assert quote["stale"] is False
