"""Small, failure-tolerant cache primitives used by market services.

Redis is an optional L2 cache.  The process-local L1 cache remains the first
choice so a Redis outage cannot turn a market-data request into a Redis
timeout.  Values are JSON documents with separate fresh and stale deadlines;
the stale deadline lets callers serve the last good provider response while
showing that it is delayed.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import settings

logger = logging.getLogger(__name__)


class CacheBackend:
    """Bounded L1 cache with optional Redis L2 and short failure cooldown."""

    def __init__(
        self,
        name: str,
        *,
        redis_url: str | None = None,
        max_entries: int = 512,
        redis_timeout_s: float = 0.25,
    ) -> None:
        self.name = name
        self.redis_url = redis_url
        self.max_entries = max_entries
        self.redis_timeout_s = redis_timeout_s
        self._local: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self._redis: Any = None
        self._redis_disabled_until = 0.0
        self._redis_failure_count = 0
        self._hits = 0
        self._misses = 0
        self._stale_hits = 0
        self._sets = 0
        self._locks: dict[str, tuple[str, float]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.redis_url)

    def _client(self) -> Any | None:
        if not self.redis_url or time.monotonic() < self._redis_disabled_until:
            return None
        if self._redis is not None:
            return self._redis
        try:
            import redis

            self._redis = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=self.redis_timeout_s,
                socket_timeout=self.redis_timeout_s,
                health_check_interval=30,
            )
            self._redis.ping()
            return self._redis
        except Exception as exc:  # pragma: no cover - depends on local Redis
            self._mark_redis_failed(exc)
            return None

    def _mark_redis_failed(self, exc: Exception) -> None:
        self._redis_failure_count += 1
        self._redis_disabled_until = time.monotonic() + min(
            60.0, 2.0 * (2 ** min(self._redis_failure_count, 5))
        )
        self._redis = None
        logger.warning("cache %s Redis unavailable; using memory cache: %s", self.name, exc)

    def _key(self, key: str) -> str:
        return f"backing:cache:v1:{self.name}:{key}"

    @staticmethod
    def _usable(record: dict[str, Any], now: float, allow_stale: bool) -> tuple[bool, bool]:
        stale_until = float(record.get("stale_until", 0))
        fresh_until = float(record.get("fresh_until", 0))
        if stale_until <= now:
            return False, False
        stale = fresh_until <= now
        return (not stale or allow_stale), stale

    def get(self, key: str, *, allow_stale: bool = True) -> dict[str, Any] | None:
        now = time.time()
        with self._lock:
            record = self._local.get(key)
            if record is not None:
                usable, stale = self._usable(record, now, allow_stale)
                if usable:
                    self._local.move_to_end(key)
                    self._hits += 1
                    self._stale_hits += int(stale)
                    return dict(record)
                if not (stale and not allow_stale):
                    self._local.pop(key, None)

        client = self._client()
        if client is not None:
            try:
                raw = client.get(self._key(key))
                if raw:
                    record = json.loads(raw)
                    usable, stale = self._usable(record, now, allow_stale)
                    if usable:
                        with self._lock:
                            self._local[key] = record
                            self._trim()
                            self._hits += 1
                            self._stale_hits += int(stale)
                        return dict(record)
            except Exception as exc:  # pragma: no cover - depends on Redis
                self._mark_redis_failed(exc)

        with self._lock:
            self._misses += 1
        return None

    def set(
        self,
        key: str,
        payload: Any,
        *,
        fresh_ttl_s: float,
        stale_ttl_s: float,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        record = {
            "payload": payload,
            "stored_at": now,
            "fresh_until": now + max(0.0, fresh_ttl_s),
            "stale_until": now + max(fresh_ttl_s, stale_ttl_s),
            "metadata": metadata or {},
        }
        with self._lock:
            self._local[key] = record
            self._local.move_to_end(key)
            self._trim()
            self._sets += 1

        client = self._client()
        if client is not None:
            try:
                client.set(
                    self._key(key),
                    json.dumps(record, ensure_ascii=False, default=str),
                    ex=max(1, int(max(fresh_ttl_s, stale_ttl_s))),
                )
            except Exception as exc:  # pragma: no cover - depends on Redis
                self._mark_redis_failed(exc)
        return record

    def delete(self, key: str) -> None:
        with self._lock:
            self._local.pop(key, None)
        client = self._client()
        if client is not None:
            try:
                client.delete(self._key(key))
            except Exception as exc:  # pragma: no cover - depends on Redis
                self._mark_redis_failed(exc)

    def _trim(self) -> None:
        while len(self._local) > self.max_entries:
            self._local.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._local.clear()
            self._locks.clear()

    @contextmanager
    def refresh_lock(self, key: str, *, ttl_s: float = 5.0) -> Iterator[bool]:
        """Best-effort single-flight lock; Redis lock is used when available."""
        token = secrets.token_hex(12)
        lock_key = f"lock:{key}"
        client = self._client()
        acquired = False
        if client is not None:
            try:
                acquired = bool(client.set(self._key(lock_key), token, nx=True, ex=max(1, int(ttl_s))))
            except Exception as exc:  # pragma: no cover
                self._mark_redis_failed(exc)
        else:
            now = time.monotonic()
            with self._lock:
                current = self._locks.get(lock_key)
                if current is None or current[1] <= now:
                    self._locks[lock_key] = (token, now + ttl_s)
                    acquired = True
        try:
            yield acquired
        finally:
            if acquired:
                if client is not None:
                    try:
                        current = client.get(self._key(lock_key))
                        if current == token:
                            client.delete(self._key(lock_key))
                    except Exception as exc:  # pragma: no cover
                        self._mark_redis_failed(exc)
                else:
                    with self._lock:
                        if self._locks.get(lock_key, (None,))[0] == token:
                            self._locks.pop(lock_key, None)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "redis_configured": self.enabled,
                "redis_available": self._redis is not None,
                "memory_entries": len(self._local),
                "hits": self._hits,
                "misses": self._misses,
                "stale_hits": self._stale_hits,
                "sets": self._sets,
                "redis_failures": self._redis_failure_count,
            }

    def close(self) -> None:
        client = self._redis
        self._redis = None
        if client is not None:
            try:
                client.close()
            except Exception:
                logger.debug("failed to close Redis cache %s", self.name, exc_info=True)


market_cache = CacheBackend("market", redis_url=settings.REDIS_URL, max_entries=512)
research_cache = CacheBackend("research", redis_url=settings.REDIS_URL, max_entries=256)
indicator_cache = CacheBackend("indicator", redis_url=settings.REDIS_URL, max_entries=200)


def close_caches() -> None:
    market_cache.close()
    research_cache.close()
    indicator_cache.close()
