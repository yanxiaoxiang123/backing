import json
from collections import OrderedDict
from unittest.mock import patch

import pytest

from app.config import settings
from app.services import tencent_realtime
from app.services.cache import market_cache
from app.services.realtime_service import FetchResult, RealtimeService


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit):
        return self.payload[:limit]


@pytest.mark.parametrize("period,key", [("daily", "day"), ("weekly", "week"), ("monthly", "month")])
def test_bars_preserve_unadjusted_ohlcv(period, key):
    assert hasattr(tencent_realtime, "fetch_bars"), "Tencent K-line adapter is missing"
    payload = {"code": 0, "data": {"sz000001": {key: [
        ["2026-10-28", "11.20", "11.31", "11.40", "11.10", "1000"],
        ["2026-10-29", "11.30", "11.54", "11.55", "11.29", "1993504"],
    ]}}}

    def respond(request, **kwargs):
        from urllib.parse import parse_qs, urlparse

        param = parse_qs(urlparse(request.full_url).query)["param"][0]
        assert param == f"sz000001,{key},,,2,"
        return Response(payload)

    with patch.object(tencent_realtime, "urlopen", side_effect=respond):
        result = tencent_realtime.fetch_bars("000001", period, count=2)
    assert result[-1] == {
        "date": "2026-10-29", "symbol": "000001", "open": 11.30,
        "close": 11.54, "high": 11.55, "low": 11.29,
        "volume": 1993504.0, "amount": 0.0,
    }


@pytest.mark.parametrize("payload", [
    {"code": -1, "data": {}},
    {"code": 0, "data": {}},
    {"code": 0, "data": {"sz000001": {"qfqday": []}}},
    {"code": 0, "data": {"sz000001": {"day": [["2026-10-29", "nan", "1", "2", "1", "1"]]}}},
])
def test_bad_or_adjusted_payload_is_not_an_empty_success(payload):
    assert hasattr(tencent_realtime, "fetch_bars"), "Tencent K-line adapter is missing"
    with patch.object(tencent_realtime, "urlopen", return_value=Response(payload)):
        with pytest.raises(ValueError):
            tencent_realtime.fetch_bars("000001", "daily", count=2)


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(settings, "REALTIME_BARS_PROVIDER", "tencent", raising=False)
    monkeypatch.setattr(RealtimeService, "_bars_cache", OrderedDict())
    monkeypatch.setattr(RealtimeService, "_bars_cache_bytes", 0)
    monkeypatch.setattr(market_cache, "redis_url", "")

    def no_tdx(*args, **kwargs):
        pytest.fail("Tencent K-line requests must not connect to mootdx")

    monkeypatch.setattr(RealtimeService, "get_client", no_tdx)
    return RealtimeService()


def candle(close=11.54):
    return {"date": "2026-10-29", "symbol": "000001", "open": 11.30,
            "close": close, "high": 11.55, "low": 11.29,
            "volume": 1993504.0, "amount": 0.0}


def test_full_and_tail_use_https_and_merge_cache(service, monkeypatch):
    assert hasattr(tencent_realtime, "fetch_bars"), "Tencent K-line adapter is missing"

    def fetch(symbol, period, *, count, timeout):
        return [candle(11.54 if count > 2 else 11.55)]

    monkeypatch.setattr(tencent_realtime, "fetch_bars", fetch)
    full = service.fetch_bars("000001")
    tail = service.fetch_bars_tail("000001")
    assert full.provider == tail.provider == "tencent"
    assert full.status == tail.status == "ok"
    assert full.data[0]["close"] == 11.54
    assert tail.data[0]["close"] == 11.55
    assert service.fetch_bars("000001").data[0]["close"] == 11.55


def test_outage_preserves_stale_and_does_not_use_tdx_cache(service, monkeypatch):
    import time

    assert hasattr(tencent_realtime, "fetch_bars"), "Tencent K-line adapter is missing"
    service._cache_put_bars("000001", "daily", FetchResult(status="ok", data=[candle(1)]))
    monkeypatch.setattr(tencent_realtime, "fetch_bars", lambda *a, **k: [candle()])
    assert service.fetch_bars("000001").data[0]["close"] == 11.54
    for key, (result, _, size) in list(service._bars_cache.items()):
        service._bars_cache[key] = (result, time.time() - 120, size)

    def outage(*args, **kwargs):
        raise TimeoutError("provider unreachable")

    monkeypatch.setattr(tencent_realtime, "fetch_bars", outage)
    stale = service.fetch_bars("000001")
    assert stale.stale is True
    assert stale.provider == "tencent"
    assert stale.data[0]["close"] == 11.54
    assert service.fetch_bars("600000").status == "unavailable"


def test_explicit_empty_history_remains_empty(service, monkeypatch):
    assert hasattr(tencent_realtime, "fetch_bars"), "Tencent K-line adapter is missing"
    monkeypatch.setattr(tencent_realtime, "fetch_bars", lambda *a, **k: [])
    result = service.fetch_bars("000001")
    assert result.status == "empty"
    assert result.data == []
    assert result.provider == "tencent"
