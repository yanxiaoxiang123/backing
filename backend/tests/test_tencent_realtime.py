"""Contracts for the HTTPS quote adapter, using a captured Tencent response."""

import importlib
import importlib.util

import pytest


QUOTE = (
    'v_sz000001="51~平安银行~000001~11.54~11.31~11.30~1993504~1155837~837667'
    '~11.53~195~11.52~2908~11.51~2420~11.50~2916~11.49~634~11.54~8835'
    '~11.55~18653~11.56~9170~11.57~9099~11.58~13413~~20261029161500'
    '~0.23~2.03~11.55~11.29~11.54/1993504/2283899683~1993504~228390";'
)


def adapter():
    assert importlib.util.find_spec("app.services.tencent_realtime") is not None, (
        "HTTPS quote adapter has not been implemented"
    )
    return importlib.import_module("app.services.tencent_realtime")


def test_quote_preserves_prices_units_and_market_timestamp():
    rows = adapter().parse_quotes(QUOTE)
    quote = rows["sz000001"]
    assert quote["close"] == 11.54
    assert quote["prev_close"] == 11.31
    assert quote["open"] == 11.30
    assert quote["high"] == 11.55
    assert quote["low"] == 11.29
    assert quote["volume"] == 1993504
    assert quote["amount"] == 2283900000
    assert quote["change"] == pytest.approx(0.23)
    assert quote["change_percent"] == 2.03
    assert quote["market_at"] == "2026-10-29T16:15:00+08:00"


def test_explicit_exchange_distinguishes_index_from_stock():
    provider = adapter()
    assert provider.tencent_symbol("sh.000001") == "sh000001"
    assert provider.tencent_symbol("sz.000001") == "sz000001"
    assert provider.tencent_symbol("000001") == "sz000001"
    assert provider.tencent_symbol("600000") == "sh600000"


def test_unrecognised_response_is_not_reported_as_empty_market():
    with pytest.raises(ValueError):
        adapter().parse_quotes("<html>upstream unavailable</html>")


def test_explicit_missing_symbol_response_is_empty():
    assert adapter().parse_quotes('v_sz000001="";') == {}


def test_https_provider_caches_then_serves_stale_on_failure(monkeypatch):
    import time

    from app.config import settings
    from app.services import tencent_realtime
    from app.services.realtime_service import RealtimeService

    monkeypatch.setattr(settings, "REALTIME_SNAPSHOT_PROVIDER", "tencent", raising=False)
    monkeypatch.setattr(RealtimeService, "_snapshot_cache", __import__("collections").OrderedDict())
    monkeypatch.setattr(RealtimeService, "_snapshot_cache_bytes", 0)
    from app.services.cache import market_cache

    monkeypatch.setattr(market_cache, "redis_url", "")
    service = RealtimeService()
    row = {**tencent_realtime.parse_quotes(QUOTE)["sz000001"], "symbol": "000001"}
    monkeypatch.setattr(tencent_realtime, "fetch_quotes", lambda *a, **k: [row])
    first = service.fetch_quotes(["000001"])
    assert first.provider == "tencent"
    assert first.data[0]["close"] == 11.54
    assert first.market_at == "2026-10-29T16:15:00+08:00"

    def unavailable(*args, **kwargs):
        raise TimeoutError("upstream timeout")

    monkeypatch.setattr(tencent_realtime, "fetch_quotes", unavailable)
    assert service.fetch_quotes(["000001"]).stale is False
    key = next(iter(service._snapshot_cache))
    result, _, size = service._snapshot_cache[key]
    service._snapshot_cache[key] = (result, time.time() - 20, size)
    stale = service.fetch_quotes(["000001"])
    assert stale.stale is True
    assert stale.provider == "tencent"
    assert stale.data[0]["close"] == 11.54


def test_https_indices_use_shanghai_index_not_shenzhen_stock(monkeypatch):
    from collections import OrderedDict

    from app.config import settings
    from app.services import tencent_realtime
    from app.services.cache import market_cache
    from app.services.realtime_service import RealtimeService

    monkeypatch.setattr(settings, "REALTIME_SNAPSHOT_PROVIDER", "tencent", raising=False)
    monkeypatch.setattr(RealtimeService, "_snapshot_cache", OrderedDict())
    monkeypatch.setattr(RealtimeService, "_snapshot_cache_bytes", 0)
    monkeypatch.setattr(market_cache, "redis_url", "")

    def fetch(symbols, **kwargs):
        assert symbols == ["sh000001", "sz399001", "sh000300", "sz399006", "sh000688"]
        return [{"symbol": "sh000001", "name": "上证指数", "close": 4000,
                 "prev_close": 3990, "change": 10, "change_percent": 0.25,
                 "market_at": "2026-10-29T15:00:00+08:00"}]

    monkeypatch.setattr(tencent_realtime, "fetch_quotes", fetch)
    result = RealtimeService().fetch_indices()
    assert result.provider == "tencent"
    assert result.data[0]["symbol"] == "000001"
    assert result.data[0]["close"] == 4000
