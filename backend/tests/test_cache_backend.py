import time
from unittest.mock import patch

import pandas as pd

from app.services.cache import CacheBackend
from app.services.realtime_service import RealtimeService


def test_memory_cache_separates_fresh_and_stale_windows():
    cache = CacheBackend("test", max_entries=2)
    cache.set("k", {"value": 1}, fresh_ttl_s=0.01, stale_ttl_s=0.08)

    assert cache.get("k", allow_stale=False)["payload"] == {"value": 1}
    time.sleep(0.02)
    assert cache.get("k", allow_stale=False) is None
    stale = cache.get("k", allow_stale=True)
    assert stale is not None
    assert stale["payload"] == {"value": 1}


def test_memory_cache_is_bounded_and_refresh_lock_is_single_flight():
    cache = CacheBackend("test", max_entries=1)
    cache.set("first", 1, fresh_ttl_s=10, stale_ttl_s=20)
    cache.set("second", 2, fresh_ttl_s=10, stale_ttl_s=20)
    assert cache.get("first") is None
    assert cache.get("second")["payload"] == 2

    with cache.refresh_lock("same") as acquired:
        assert acquired
        with cache.refresh_lock("same") as nested:
            assert not nested


def test_realtime_tail_fetch_uses_two_rows_and_refreshes_full_snapshot():
    service = RealtimeService()
    full = pd.DataFrame(
        [
            {"datetime": "2026-09-09", "open": 1, "high": 2, "low": 1, "close": 1.5, "vol": 10, "amount": 20},
            {"datetime": "2026-09-10", "open": 1.5, "high": 2.5, "low": 1.4, "close": 2, "vol": 12, "amount": 24},
        ]
    )
    with patch.object(service, "_fetch_frame", return_value=full) as fetch:
        service.fetch_bars("600000", "daily")
        service.fetch_bars_tail("600000", "daily")

    assert fetch.call_args_list[0].kwargs["offset"] == 750
    assert fetch.call_args_list[1].kwargs["offset"] == 2
