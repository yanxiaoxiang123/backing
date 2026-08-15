from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

import pandas as pd

from app.config import settings
from app.services.tasks.metrics import task_metrics

logger = logging.getLogger(__name__)

Server = tuple[str, int]

# Statuses exposed by ``FetchResult``.
STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_UNAVAILABLE = "unavailable"

# Endpoint tags used for both internal counters and the public health snapshot.
ENDPOINT_BARS = "bars"
ENDPOINT_QUOTES = "quotes"
ENDPOINT_INDICES = "indices"

# Short-term cache TTL for the realtime endpoints. Smaller than the WS poll
# cadence (10s) so the client always sees fresh data when it polls, but large
# enough to dedupe concurrent calls from a single Dashboard render.
_CACHE_TTL_S = 2.0


@dataclass(frozen=True)
class FetchResult:
    """Structured envelope around a realtime data fetch.

    Distinguishes ``ok`` (real data returned) from ``empty`` (provider reachable
    but no rows, e.g. closed market) and ``unavailable`` (no healthy server).
    Callers use ``status`` to decide between graceful-degrade (200 + empty
    data) and a structured 503.
    """

    status: str
    data: list[dict[str, Any]] = field(default_factory=list)
    provider: str = "mootdx"
    reason: str | None = None
    selected_server: Server | None = None
    served_at: float = field(default_factory=time.time)
    cache_age_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot for the HTTP layer."""
        server: dict[str, Any] | None
        if self.selected_server is None:
            server = None
        else:
            host, port = self.selected_server
            server = {"host": host, "port": port}
        return {
            "status": self.status,
            "data": self.data,
            "provider": self.provider,
            "reason": self.reason,
            "selected_server": server,
            "served_at": self.served_at,
            "cache_age_ms": self.cache_age_ms,
        }


class RealtimeService:
    """Thread-safe mootdx market-data adapter with server failover."""

    _local = threading.local()
    _selection_lock = threading.Lock()
    _selected_server: Server | None = None
    _unhealthy_until: ClassVar[dict[Server, float]] = {}
    _unhealthy_ttl_s = 60.0

    # Short-term caches keyed by (endpoint, key). Values are (FetchResult, ts).
    _bars_cache: ClassVar[dict[tuple[str, str, str], tuple[FetchResult, float]]] = {}
    _snapshot_cache: ClassVar[dict[str, tuple[FetchResult, float]]] = {}

    # Aggregated counters mirrored into ``task_metrics`` for the /jobs/metrics
    # endpoint.
    _request_count: int = 0
    _failover_count: int = 0
    _cache_hit_count: int = 0
    _provider_unavailable_count: int = 0
    _last_failure_reason: ClassVar[dict[str, str]] = {}

    @classmethod
    def _server_candidates(cls) -> list[Server]:
        candidates: list[Server] = []
        for raw in settings.MOOTDX_SERVERS.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                host, port = raw.rsplit(":", 1)
                candidate = (host.strip(), int(port))
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid MOOTDX_SERVERS entry: %s", raw)
                continue
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates

    @classmethod
    def _connect(cls, server: Server):
        """Connect to one explicit server and verify that it serves K-line data."""
        from mootdx.quotes import Quotes

        client = Quotes.factory(
            market="std",
            server=server,
            timeout=settings.MOOTDX_TIMEOUT_S,
            auto_retry=False,
            raise_exception=True,
        )
        try:
            probe = client.bars(symbol="000001", frequency=9, offset=1)
            if probe is None or probe.empty:
                raise ConnectionError("server returned no probe data")
        except Exception:
            client.close()
            raise
        return client

    @classmethod
    def get_client(cls):
        """Return a per-thread client backed by one process-wide selected server."""
        cached = getattr(cls._local, "client", None)
        if cached is not None:
            return cached

        with cls._selection_lock:
            cached = getattr(cls._local, "client", None)
            if cached is not None:
                return cached

            candidates = cls._server_candidates()
            if cls._selected_server in candidates:
                candidates.remove(cls._selected_server)
                candidates.insert(0, cls._selected_server)

            now = time.monotonic()
            available = [
                server
                for server in candidates
                if cls._unhealthy_until.get(server, 0) <= now
            ]
            if not available:
                cls._unhealthy_until.clear()
                available = candidates

            for server in available:
                try:
                    client = cls._connect(server)
                except Exception as exc:
                    cls._unhealthy_until[server] = now + cls._unhealthy_ttl_s
                    logger.warning("mootdx server %s:%s unavailable: %s", *server, exc)
                    cls._failover_count += 1
                    task_metrics.inc("realtime.failover", endpoint="connect")
                    continue

                cls._selected_server = server
                cls._local.client = client
                cls._local.server = server
                logger.info("mootdx connected to %s:%s", *server)
                return client

            logger.error("No usable mootdx server found")
            return None

    @classmethod
    def _discard_client(cls, *, unhealthy: bool = True) -> None:
        client = getattr(cls._local, "client", None)
        server = getattr(cls._local, "server", None)
        if client is not None:
            try:
                client.close()
            except Exception:
                logger.debug("Failed to close mootdx client", exc_info=True)
        cls._local.client = None
        cls._local.server = None
        if unhealthy and server:
            cls._unhealthy_until[server] = time.monotonic() + cls._unhealthy_ttl_s
            if cls._selected_server == server:
                cls._selected_server = None

    def _fetch_frame(self, method: str, **kwargs: Any) -> pd.DataFrame:
        """Call a mootdx DataFrame method once, then fail over and retry once."""
        for attempt in range(2):
            client = self.get_client()
            if client is None:
                return pd.DataFrame()
            try:
                frame = getattr(client, method)(**kwargs)
                return frame if frame is not None else pd.DataFrame()
            except Exception as exc:
                logger.warning(
                    "mootdx %s failed (attempt %s) for %s: %s",
                    method,
                    attempt + 1,
                    kwargs.get("symbol", "unknown"),
                    exc,
                )
                self._discard_client()
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Envelope + cache helpers
    # ------------------------------------------------------------------

    def _bump_request(self, endpoint: str, **tags: str) -> None:
        cls = type(self)
        cls._request_count += 1
        task_metrics.inc("realtime.request", endpoint=endpoint, **tags)

    def _record_failover(self, endpoint: str) -> None:
        cls = type(self)
        cls._failover_count += 1
        task_metrics.inc("realtime.failover", endpoint=endpoint)

    def _record_cache_hit(self, endpoint: str) -> None:
        cls = type(self)
        cls._cache_hit_count += 1
        task_metrics.inc("realtime.cache_hit", endpoint=endpoint)

    def _record_unavailable(self, endpoint: str, reason: str) -> None:
        cls = type(self)
        cls._provider_unavailable_count += 1
        cls._last_failure_reason[endpoint] = reason
        task_metrics.inc("realtime.provider_unavailable", endpoint=endpoint)
        logger.warning("realtime provider unavailable for %s: %s", endpoint, reason)

    def _cache_age_ms(self, stored_at: float) -> int:
        return max(0, int((time.time() - stored_at) * 1000))

    def _cache_get_bars(self, symbol: str, period: str) -> FetchResult | None:
        key = (ENDPOINT_BARS, symbol, period)
        entry = self._bars_cache.get(key)
        if entry is None:
            return None
        result, stored_at = entry
        if time.time() - stored_at > _CACHE_TTL_S:
            self._bars_cache.pop(key, None)
            return None
        return FetchResult(
            status=result.status,
            data=result.data,
            provider=result.provider,
            reason=result.reason,
            selected_server=result.selected_server,
            served_at=result.served_at,
            cache_age_ms=self._cache_age_ms(stored_at),
        )

    def _cache_put_bars(self, symbol: str, period: str, result: FetchResult) -> None:
        self._bars_cache[(ENDPOINT_BARS, symbol, period)] = (result, time.time())

    def _cache_get_snapshot(self, endpoint: str) -> FetchResult | None:
        entry = self._snapshot_cache.get(endpoint)
        if entry is None:
            return None
        result, stored_at = entry
        if time.time() - stored_at > _CACHE_TTL_S:
            self._snapshot_cache.pop(endpoint, None)
            return None
        return FetchResult(
            status=result.status,
            data=result.data,
            provider=result.provider,
            reason=result.reason,
            selected_server=result.selected_server,
            served_at=result.served_at,
            cache_age_ms=self._cache_age_ms(stored_at),
        )

    def _cache_put_snapshot(self, endpoint: str, result: FetchResult) -> None:
        self._snapshot_cache[endpoint] = (result, time.time())

    # ------------------------------------------------------------------
    # Public envelope-returning methods
    # ------------------------------------------------------------------

    def fetch_bars(self, symbol: str, period: str = "daily") -> FetchResult:
        """Fetch bars wrapped in a ``FetchResult`` with status and metadata."""
        cached = self._cache_get_bars(symbol, period)
        if cached is not None:
            self._record_cache_hit(ENDPOINT_BARS)
            return cached

        self._bump_request(ENDPOINT_BARS, period=period)
        freq_map = {"daily": 9, "weekly": 5, "monthly": 6}
        frequency = freq_map.get(period, 9)

        selected_before = type(self)._selected_server
        df = self._fetch_frame("bars", symbol=symbol, frequency=frequency, offset=750)
        selected_after = type(self)._selected_server

        if selected_before is not None and selected_after != selected_before:
            self._record_failover(ENDPOINT_BARS)

        if df.empty:
            client = self.get_client()
            if client is None:
                result = FetchResult(
                    status=STATUS_UNAVAILABLE,
                    data=[],
                    reason="no_healthy_server",
                    selected_server=None,
                )
                self._record_unavailable(ENDPOINT_BARS, result.reason or "")
            else:
                result = FetchResult(
                    status=STATUS_EMPTY,
                    data=[],
                    selected_server=type(self)._selected_server,
                )
        else:
            records = self._normalise_frame(df, symbol)
            result = FetchResult(
                status=STATUS_OK,
                data=records,
                selected_server=type(self)._selected_server,
            )

        self._cache_put_bars(symbol, period, result)
        return result

    def fetch_quotes(self, symbols: list[str]) -> FetchResult:
        """Fetch latest quotes for ``symbols`` (each is a single call)."""
        cached = self._cache_get_snapshot(ENDPOINT_QUOTES)
        if cached is not None:
            self._record_cache_hit(ENDPOINT_QUOTES)
            return cached

        self._bump_request(ENDPOINT_QUOTES)
        selected_before = type(self)._selected_server
        results: list[dict[str, Any]] = []
        for symbol in symbols:
            df = self._fetch_frame("bars", symbol=symbol, frequency=9, offset=2)
            if len(df) < 2:
                continue
            today, yesterday = df.iloc[-1], df.iloc[-2]
            close = float(today.get("close", 0))
            prev_close = float(yesterday.get("close", close))
            change = close - prev_close
            results.append(
                {
                    "symbol": symbol,
                    "open": float(today.get("open", 0)),
                    "high": float(today.get("high", 0)),
                    "low": float(today.get("low", 0)),
                    "close": close,
                    "volume": float(today.get("vol", today.get("volume", 0))),
                    "amount": float(today.get("amount", 0)),
                    "change": change,
                    "change_percent": (change / prev_close * 100) if prev_close else 0,
                    "prev_close": prev_close,
                }
            )

        if selected_before is not None and type(self)._selected_server != selected_before:
            self._record_failover(ENDPOINT_QUOTES)

        if not results and self.get_client() is None:
            result = FetchResult(
                status=STATUS_UNAVAILABLE,
                data=[],
                reason="no_healthy_server",
                selected_server=None,
            )
            self._record_unavailable(ENDPOINT_QUOTES, result.reason or "")
        elif not results:
            result = FetchResult(
                status=STATUS_EMPTY,
                data=[],
                selected_server=type(self)._selected_server,
            )
        else:
            result = FetchResult(
                status=STATUS_OK,
                data=results,
                selected_server=type(self)._selected_server,
            )

        self._cache_put_snapshot(ENDPOINT_QUOTES, result)
        return result

    def fetch_indices(self) -> FetchResult:
        """Fetch snapshots for the major indices wrapped in ``FetchResult``."""
        cached = self._cache_get_snapshot(ENDPOINT_INDICES)
        if cached is not None:
            self._record_cache_hit(ENDPOINT_INDICES)
            return cached

        self._bump_request(ENDPOINT_INDICES)
        selected_before = type(self)._selected_server

        index_codes = ["000001", "399001", "000300", "399006", "000688"]
        index_names = {
            "000001": "上证指数",
            "399001": "深证成指",
            "000300": "沪深300",
            "399006": "创业板指",
            "000688": "科创50",
        }
        results: list[dict[str, Any]] = []
        for code in index_codes:
            df = self._fetch_frame("index", symbol=code, frequency=9, offset=2)
            if len(df) < 2:
                continue
            today, yesterday = df.iloc[-1], df.iloc[-2]
            close = float(today.get("close", 0))
            prev_close = float(yesterday.get("close", close))
            change = close - prev_close
            results.append(
                {
                    "symbol": code,
                    "name": index_names[code],
                    "close": close,
                    "change": change,
                    "change_percent": (change / prev_close * 100) if prev_close else 0,
                    "prev_close": prev_close,
                }
            )

        if selected_before is not None and type(self)._selected_server != selected_before:
            self._record_failover(ENDPOINT_INDICES)

        if not results and self.get_client() is None:
            result = FetchResult(
                status=STATUS_UNAVAILABLE,
                data=[],
                reason="no_healthy_server",
                selected_server=None,
            )
            self._record_unavailable(ENDPOINT_INDICES, result.reason or "")
        elif not results:
            result = FetchResult(
                status=STATUS_EMPTY,
                data=[],
                selected_server=type(self)._selected_server,
            )
        else:
            result = FetchResult(
                status=STATUS_OK,
                data=results,
                selected_server=type(self)._selected_server,
            )

        self._cache_put_snapshot(ENDPOINT_INDICES, result)
        return result

    # ------------------------------------------------------------------
    # Backward-compatible list helpers
    # ------------------------------------------------------------------

    def _normalise_frame(self, df: pd.DataFrame, symbol: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            dt = str(row.get("datetime", ""))
            records.append(
                {
                    "date": dt[:10] if len(dt) >= 10 else dt,
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("vol", row.get("volume", 0))),
                    "amount": float(row.get("amount", 0)),
                    "symbol": symbol,
                }
            )
        return records

    def bars(
        self, symbol: str, frequency: int = 9, offset: int = 750
    ) -> pd.DataFrame:
        """Fetch stock K-lines; frequency 9/5/6 means daily/weekly/monthly."""
        return self._fetch_frame(
            "bars", symbol=symbol, frequency=frequency, offset=offset
        )

    def normalise_bars(
        self, symbol: str, frequency: int = 9, offset: int = 750
    ) -> list[dict[str, Any]]:
        """Convert mootdx bars to the stable HTTP/WebSocket response shape.

        Backward-compatible wrapper: returns ``list[dict]`` like before, while
        internally delegating through the envelope-aware path so caching and
        metrics still apply.
        """
        # Map frequency to period so we can share the envelope cache.
        period = {9: "daily", 5: "weekly", 6: "monthly"}.get(frequency, "daily")
        result = self.fetch_bars(symbol, period)
        # Trim to the requested ``offset`` so callers asking for a 2-bar tail
        # don't accidentally get the full 750-bar cache record.
        return list(result.data[-offset:]) if offset else result.data

    def get_realtime_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Fetch the latest two bars and derive quotes for multiple stocks."""
        return self.fetch_quotes(symbols).data

    def get_index_realtime(self) -> list[dict[str, Any]]:
        """Fetch the main Shanghai/Shenzhen index snapshots."""
        return self.fetch_indices().data

    # ------------------------------------------------------------------
    # Health / observability surface
    # ------------------------------------------------------------------

    def get_provider_health(self) -> dict[str, Any]:
        """Return a JSON-serialisable view of the provider state."""
        cls = type(self)
        now = time.monotonic()
        candidates = self._server_candidates()
        healthy = [
            s for s in candidates if cls._unhealthy_until.get(s, 0) <= now
        ]
        return {
            "provider": "mootdx",
            "selected_server": cls._selected_server,
            "total_servers": len(candidates),
            "healthy_count": len(healthy),
            "cooldown_count": len(candidates) - len(healthy),
            "cooldown_ttl_s": cls._unhealthy_ttl_s,
            "counters": {
                "requests": cls._request_count,
                "failovers": cls._failover_count,
                "cache_hits": cls._cache_hit_count,
                "provider_unavailable": cls._provider_unavailable_count,
            },
            "last_failure_reason": dict(cls._last_failure_reason),
        }


realtime_service = RealtimeService()