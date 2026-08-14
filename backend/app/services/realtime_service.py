from __future__ import annotations

import logging
import threading
import time
from typing import Any, ClassVar

import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

Server = tuple[str, int]


class RealtimeService:
    """Thread-safe mootdx market-data adapter with server failover."""

    _local = threading.local()
    _selection_lock = threading.Lock()
    _selected_server: Server | None = None
    _unhealthy_until: ClassVar[dict[Server, float]] = {}
    _unhealthy_ttl_s = 60.0

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
        """Convert mootdx bars to the stable HTTP/WebSocket response shape."""
        df = self.bars(symbol=symbol, frequency=frequency, offset=offset)
        if df.empty:
            return []

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

    def get_realtime_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Fetch the latest two bars and derive quotes for multiple stocks."""
        results: list[dict[str, Any]] = []
        for symbol in symbols:
            df = self.bars(symbol=symbol, frequency=9, offset=2)
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
        return results

    def get_index_realtime(self) -> list[dict[str, Any]]:
        """Fetch the main Shanghai/Shenzhen index snapshots."""
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
        return results


realtime_service = RealtimeService()
