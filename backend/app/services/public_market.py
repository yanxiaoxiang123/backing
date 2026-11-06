"""Anonymous read-only public market gateway.

Only a fixed allowlist of representative A-share stocks and indices can be
read here.  The gateway is deliberately small: it normalises the existing
realtime service envelopes, adds conservative staleness metadata, and serves
an actual Tencent minute series for the public stock board.

Provider results are cached in a bounded process-local cache (with a short
failure cache) so anonymous traffic cannot create a provider stampede.  The
HTTP layer adds a per-IP rate limit.  Internal provider state such as the
selected mootdx server is never exposed.
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import settings
from app.services.realtime_service import (
    STATUS_EMPTY,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    FetchResult,
    realtime_service,
)
from app.services.tencent_realtime import tencent_symbol

logger = logging.getLogger(__name__)

SHANGHAI_TZ = timezone(timedelta(hours=8))

# Fixed public allowlists.  Canonical symbols are ``sh.600519`` style.
PUBLIC_STOCKS: tuple[tuple[str, str], ...] = (
    ("sh.600519", "贵州茅台"),
    ("sz.300750", "宁德时代"),
    ("sh.600036", "招商银行"),
)
PUBLIC_INDICES: tuple[tuple[str, str], ...] = (
    ("sh.000001", "上证指数"),
    ("sz.399001", "深证成指"),
    ("sz.399006", "创业板指"),
)
PUBLIC_STOCK_CODES = frozenset(code for code, _ in PUBLIC_STOCKS)
PUBLIC_INDEX_CODES = frozenset(code for code, _ in PUBLIC_INDICES)
PUBLIC_INTRADAY_CODES = PUBLIC_STOCK_CODES

_INDEX_BY_RAW_CODE = {
    code.split(".", 1)[1]: code for code, _ in PUBLIC_INDICES
}

# A quote whose provider timestamp is older than this is reported as stale.
# The frontend also shows the exact market time, so a weekend or overnight
# quote can never look like a live tick.
_QUOTE_STALE_AFTER_S = 120.0

_MARKET_CACHE_TTL_S = 20.0
_MARKET_FAILURE_TTL_S = 10.0
_INTRADAY_CACHE_TTL_S = 30.0
_INTRADAY_FAILURE_TTL_S = 10.0
_MAX_CACHE_ENTRIES = 24

_MAX_INTRADAY_POINTS = 242  # 09:30-11:30 and 13:00-15:00 inclusive
_MAX_RESPONSE_BYTES = 1_048_576
_MINUTE_ENDPOINT = "https://web.ifzq.gtimg.cn/appstock/app/minute/query"

# Inclusive minute-of-day ranges for the A-share continuous sessions.
_SESSION_MINUTES = ((9 * 60 + 30, 11 * 60 + 30), (13 * 60, 15 * 60))


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _number_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _canonical_stock_symbol(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip().lower()
    if value in PUBLIC_STOCK_CODES:
        return value
    raw_code = value.split(".", 1)[-1]
    for canonical in PUBLIC_STOCK_CODES:
        if canonical.endswith("." + raw_code):
            return canonical
    return None


def _canonical_index_symbol(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip().lower()
    if value in PUBLIC_INDEX_CODES:
        return value
    return _INDEX_BY_RAW_CODE.get(value.split(".", 1)[-1])


def _market_at_is_stale(
    market_at: str | None, *, now: datetime | None = None
) -> bool:
    if not market_at:
        return False
    try:
        stamp = datetime.fromisoformat(market_at)
    except ValueError:
        return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=SHANGHAI_TZ)
    current = now or datetime.now(SHANGHAI_TZ)
    return (current - stamp).total_seconds() > _QUOTE_STALE_AFTER_S


def _trade_date_is_stale(
    trade_date: str | None, *, now: datetime | None = None
) -> bool:
    if not trade_date:
        return False
    current = (now or datetime.now(SHANGHAI_TZ)).date()
    try:
        return datetime.strptime(trade_date, "%Y-%m-%d").date() != current
    except ValueError:
        return True


def _min_market_at(rows: list[dict[str, Any]]) -> str | None:
    stamps = [
        row["market_at"]
        for row in rows
        if isinstance(row.get("market_at"), str)
    ]
    return min(stamps) if stamps else None


def _quote_row(row: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    close = _positive_number(row.get("close"))
    if close is None:
        return None
    return {
        "symbol": symbol,
        "name": str(row.get("name") or ""),
        "close": close,
        "prev_close": _number_or_none(row.get("prev_close")),
        "open": _number_or_none(row.get("open")),
        "high": _number_or_none(row.get("high")),
        "low": _number_or_none(row.get("low")),
        "volume": _number_or_none(row.get("volume")),
        "amount": _number_or_none(row.get("amount")),
        "change": _number_or_none(row.get("change")),
        "change_percent": _number_or_none(row.get("change_percent")),
        "market_at": (
            row["market_at"]
            if isinstance(row.get("market_at"), str)
            else None
        ),
    }


def _index_row(row: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    close = _positive_number(row.get("close"))
    if close is None:
        return None
    return {
        "symbol": symbol,
        "name": str(row.get("name") or ""),
        "close": close,
        "prev_close": _number_or_none(row.get("prev_close")),
        "change": _number_or_none(row.get("change")),
        "change_percent": _number_or_none(row.get("change_percent")),
        "market_at": (
            row["market_at"]
            if isinstance(row.get("market_at"), str)
            else None
        ),
    }


def _snapshot_envelope(
    result: FetchResult,
    rows: list[dict[str, Any]],
    *,
    market_at: str | None,
) -> dict[str, Any]:
    try:
        if not market_at:
            market_at = None
        else:
            datetime.fromisoformat(market_at)
    except (TypeError, ValueError):
        market_at = None
    status = result.status
    if status == STATUS_OK and not rows:
        status = STATUS_EMPTY
    if status not in (STATUS_OK, STATUS_EMPTY, STATUS_UNAVAILABLE):
        status = STATUS_UNAVAILABLE

    if status == STATUS_OK:
        data = rows
        stale = bool(result.stale) or _market_at_is_stale(market_at)
    else:
        data = []
        market_at = None
        stale = False

    return {
        "status": status,
        "data": data,
        "provider": result.provider or "unknown",
        "market_at": market_at,
        "fetched_at": result.fetched_at,
        "served_at": time.time(),
        "cache_age_ms": max(0, int(result.cache_age_ms or 0)),
        "stale": stale,
        "reason": result.reason,
    }


def _unavailable_envelope(reason: str) -> dict[str, Any]:
    return {
        "status": STATUS_UNAVAILABLE,
        "data": [],
        "provider": getattr(settings, "REALTIME_SNAPSHOT_PROVIDER", None)
        or "unknown",
        "market_at": None,
        "fetched_at": None,
        "served_at": time.time(),
        "cache_age_ms": 0,
        "stale": False,
        "reason": reason,
    }


def _intraday_envelope(
    code: str,
    *,
    status: str,
    data: list[dict[str, Any]],
    market_at: str | None,
    fetched_at: float | None,
    reason: str | None,
    stale: bool,
    trade_date: str | None,
) -> dict[str, Any]:
    return {
        "code": code,
        "status": status,
        "data": data,
        "provider": "tencent",
        "market_at": market_at,
        "fetched_at": fetched_at,
        "served_at": time.time(),
        "cache_age_ms": 0,
        "stale": stale,
        "reason": reason,
        "volume_unit": "lots",
        "volume_kind": "interval",
        "trade_date": trade_date,
    }


# ---------------------------------------------------------------------------
# Tencent minute-series adapter
# ---------------------------------------------------------------------------


def _bounded_timeout(timeout: float | None = None) -> float:
    if timeout is not None:
        value = float(timeout)
    else:
        try:
            value = float(getattr(settings, "MOOTDX_TIMEOUT_S", 5.0) or 5.0)
        except (TypeError, ValueError):
            value = 5.0
    return min(max(value, 0.5), 5.0)


def _volume_number(value: float) -> int | float:
    return int(value) if value.is_integer() else round(value, 4)


def _parse_intraday_payload(
    payload: Any, tencent_code: str
) -> tuple[list[dict[str, Any]], str, str | None]:
    """Parse a Tencent minute response into strict, bounded public points.

    Rows outside the continuous sessions (call auction, after-hours prints)
    are ignored.  Volume is the interval increment derived from the provider's
    cumulative lot count; when the cumulative count is missing or goes
    backwards the interval is ``None`` rather than an invented number.
    """
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise ValueError("Tencent minute request failed")
    data = payload.get("data")
    entry = data.get(tencent_code) if isinstance(data, dict) else None
    series = entry.get("data") if isinstance(entry, dict) else None
    if not isinstance(series, dict):
        raise ValueError("Missing Tencent minute series")

    raw_date = series.get("date")
    if not isinstance(raw_date, str) or not re.fullmatch(r"\d{8}", raw_date):
        raise ValueError("Missing Tencent minute trade date")
    trade_date = datetime.strptime(raw_date, "%Y%m%d").date().isoformat()

    rows = series.get("data")
    if not isinstance(rows, list):
        raise ValueError("Malformed Tencent minute rows")

    points: list[dict[str, Any]] = []
    previous_cumulative: float | None = None
    volume_known = True
    for row in rows:
        if not isinstance(row, str):
            raise ValueError("Malformed Tencent minute row")
        parts = row.split()
        if len(parts) < 2:
            raise ValueError("Malformed Tencent minute row")
        hhmm = parts[0]
        if not re.fullmatch(r"\d{4}", hhmm):
            raise ValueError("Malformed Tencent minute time")
        hour, minute = int(hhmm[:2]), int(hhmm[2:])
        if hour > 23 or minute > 59:
            raise ValueError("Malformed Tencent minute time")
        minute_of_day = hour * 60 + minute
        if not any(
            start <= minute_of_day <= end for start, end in _SESSION_MINUTES
        ):
            continue

        price = float(parts[1])
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Non-finite Tencent minute price")

        cumulative: float | None = None
        if len(parts) >= 3 and parts[2]:
            cumulative = float(parts[2])
            if not math.isfinite(cumulative) or cumulative < 0:
                raise ValueError("Non-finite Tencent minute volume")

        volume: int | float | None = None
        if cumulative is None:
            # A missing cumulative count makes the following interval
            # unattributable, so it is reported as null rather than merged.
            volume_known = False
        else:
            if previous_cumulative is None:
                volume = _volume_number(cumulative) if volume_known else None
            elif volume_known and cumulative >= previous_cumulative:
                volume = _volume_number(cumulative - previous_cumulative)
            previous_cumulative = cumulative
            volume_known = True

        points.append(
            {
                "time": f"{trade_date}T{hhmm[:2]}:{hhmm[2:]}:00+08:00",
                "price": price,
                "volume": volume,
            }
        )

    if len(points) > _MAX_INTRADAY_POINTS:
        points = points[-_MAX_INTRADAY_POINTS:]
    market_at = points[-1]["time"] if points else None
    return points, trade_date, market_at


def fetch_tencent_minutes(
    code: str, *, timeout: float | None = None
) -> tuple[list[dict[str, Any]], str, str | None]:
    """Fetch one stock's real Tencent minute series (bounded request)."""
    tencent_code = tencent_symbol(code)
    query = urlencode({"code": tencent_code})
    request = Request(
        f"{_MINUTE_ENDPOINT}?{query}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=_bounded_timeout(timeout)) as response:
        raw = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ValueError("Tencent minute response exceeds size limit")
    payload = json.loads(raw.decode("utf-8"))
    return _parse_intraday_payload(payload, tencent_code)


# ---------------------------------------------------------------------------
# Cached public service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CacheEntry:
    payload: dict[str, Any]
    stored_at: float
    ttl_s: float


class PublicMarketService:
    """Thread-safe bounded cache in front of the realtime providers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._key_locks: dict[str, threading.Lock] = {}

    # -- cache primitives -------------------------------------------------

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def cache_size(self) -> int:
        with self._lock:
            return len(self._cache)

    def _key_lock(self, key: str) -> threading.Lock:
        with self._lock:
            return self._key_locks.setdefault(key, threading.Lock())

    def _cache_get(self, key: str, now: float) -> _CacheEntry | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if now - entry.stored_at > entry.ttl_s:
                self._cache.pop(key, None)
                return None
            self._cache.move_to_end(key)
            return entry

    def _cache_put(
        self, key: str, payload: dict[str, Any], *, now: float, ttl_s: float
    ) -> None:
        with self._lock:
            self._cache.pop(key, None)
            self._cache[key] = _CacheEntry(
                payload=payload, stored_at=now, ttl_s=ttl_s
            )
            while len(self._cache) > _MAX_CACHE_ENTRIES:
                self._cache.popitem(last=False)

    @staticmethod
    def _serve(entry: _CacheEntry, now: float) -> dict[str, Any]:
        payload = dict(entry.payload)
        payload["served_at"] = now
        payload["cache_age_ms"] = max(0, int(payload.get("cache_age_ms") or 0)) + max(
            0, int((now - entry.stored_at) * 1000)
        )
        if payload.get("status") == STATUS_OK and _market_at_is_stale(
            payload.get("market_at")
        ):
            payload["stale"] = True
        return payload

    def _section(
        self,
        key: str,
        builder: Callable[[], dict[str, Any]],
        *,
        ttl_s: float,
        failure_ttl_s: float,
    ) -> dict[str, Any]:
        now = time.time()
        entry = self._cache_get(key, now)
        if entry is not None:
            return self._serve(entry, now)

        with self._key_lock(key):
            now = time.time()
            entry = self._cache_get(key, now)
            if entry is not None:
                return self._serve(entry, now)

            try:
                payload = builder()
            except Exception as exc:  # provider isolation
                logger.warning(
                    "public market provider failure for %s: %s", key, exc
                )
                payload = _unavailable_envelope("provider_error")

            stored_at = time.time()
            ttl = (
                failure_ttl_s
                if payload.get("status") == STATUS_UNAVAILABLE
                else ttl_s
            )
            self._cache_put(key, payload, now=stored_at, ttl_s=ttl)
            return self._serve(
                _CacheEntry(payload=payload, stored_at=stored_at, ttl_s=ttl),
                stored_at,
            )

    # -- builders ---------------------------------------------------------

    def _build_quotes(self) -> dict[str, Any]:
        raw_codes = [code.split(".", 1)[1] for code, _ in PUBLIC_STOCKS]
        result = realtime_service.fetch_quotes(raw_codes)
        by_symbol: dict[str, dict[str, Any]] = {}
        for item in result.data or []:
            if not isinstance(item, dict):
                continue
            canonical = _canonical_stock_symbol(item.get("symbol"))
            if canonical is None or canonical in by_symbol:
                continue
            row = _quote_row(item, canonical)
            if row is not None:
                by_symbol[canonical] = row
        rows = [
            by_symbol[code] for code, _ in PUBLIC_STOCKS if code in by_symbol
        ]
        return _snapshot_envelope(
            result, rows, market_at=_min_market_at(rows) or result.market_at
        )

    def _build_indices(self) -> dict[str, Any]:
        result = realtime_service.fetch_indices()
        by_symbol: dict[str, dict[str, Any]] = {}
        for item in result.data or []:
            if not isinstance(item, dict):
                continue
            canonical = _canonical_index_symbol(item.get("symbol"))
            if canonical is None or canonical in by_symbol:
                continue
            row = _index_row(item, canonical)
            if row is not None:
                by_symbol[canonical] = row
        rows = [
            by_symbol[code] for code, _ in PUBLIC_INDICES if code in by_symbol
        ]
        return _snapshot_envelope(
            result, rows, market_at=_min_market_at(rows) or result.market_at
        )

    def _build_intraday(self, code: str) -> dict[str, Any]:
        try:
            points, trade_date, market_at = fetch_tencent_minutes(code)
            fetched_at = time.time()
        except Exception as exc:  # provider isolation
            logger.warning(
                "public intraday provider unavailable for %s: %s", code, exc
            )
            return _intraday_envelope(
                code,
                status=STATUS_UNAVAILABLE,
                data=[],
                market_at=None,
                fetched_at=None,
                reason="tencent_intraday_unavailable",
                stale=False,
                trade_date=None,
            )

        status = STATUS_OK if points else STATUS_EMPTY
        return _intraday_envelope(
            code,
            status=status,
            data=points,
            market_at=market_at,
            fetched_at=fetched_at,
            reason=None,
            stale=bool(points) and _trade_date_is_stale(trade_date),
            trade_date=trade_date,
        )

    # -- public API -------------------------------------------------------

    def get_market(self) -> dict[str, Any]:
        """Return independent index/quote envelopes; one may be unavailable."""
        with ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="public-market"
        ) as pool:
            indices_future = pool.submit(
                self._section,
                "indices",
                self._build_indices,
                ttl_s=_MARKET_CACHE_TTL_S,
                failure_ttl_s=_MARKET_FAILURE_TTL_S,
            )
            quotes_future = pool.submit(
                self._section,
                "quotes",
                self._build_quotes,
                ttl_s=_MARKET_CACHE_TTL_S,
                failure_ttl_s=_MARKET_FAILURE_TTL_S,
            )
            indices = indices_future.result()
            quotes = quotes_future.result()
        return {"indices": indices, "quotes": quotes}

    def get_intraday(self, code: str) -> dict[str, Any]:
        if code not in PUBLIC_INTRADAY_CODES:
            raise ValueError("Unsupported public stock code")
        return self._section(
            f"intraday:{code}",
            lambda: self._build_intraday(code),
            ttl_s=_INTRADAY_CACHE_TTL_S,
            failure_ttl_s=_INTRADAY_FAILURE_TTL_S,
        )


public_market_service = PublicMarketService()
