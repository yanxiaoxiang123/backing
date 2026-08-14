"""Lightweight in-process task metrics.

Counters and durations are kept in memory, emitted as structured JSON log
lines (``task_event`` field) so any log collector can ship them, and exposed
through ``snapshot()`` for the ``GET /api/v1/jobs/metrics`` endpoint.
No Prometheus dependency is required; swap this module for a real metrics
backend later if needed.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger("backing.metrics")


def _key(name: str, tags: dict[str, str]) -> tuple[str, tuple[tuple[str, str], ...]]:
    return (name, tuple(sorted(tags.items())))


class TaskMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self._durations: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def inc(self, name: str, value: int = 1, **tags) -> None:
        """Increment a counter (e.g. ``inc("task.completed", job_type="sync")``)."""
        key = _key(name, tags)
        with self._lock:
            self._counters[key] += value
        logger.info(
            "task_metric",
            extra={"task_event": name, **tags, "value": value},
        )

    def observe(self, name: str, value: float, **tags) -> None:
        """Record a duration (milliseconds)."""
        key = _key(name, tags)
        with self._lock:
            self._durations[key] = value
        logger.info(
            "task_metric",
            extra={"task_event": name, **tags, "value_ms": round(value, 2)},
        )

    def snapshot(self) -> dict:
        """Return a JSON-serializable snapshot for the metrics endpoint."""
        with self._lock:
            return {
                "started_at": self._started_at,
                "counters": [
                    {"name": name, **dict(tags), "value": value}
                    for (name, tags), value in self._counters.items()
                ],
                "durations": [
                    {"name": name, **dict(tags), "value_ms": round(value, 2)}
                    for (name, tags), value in self._durations.items()
                ],
            }


# Process-wide singleton.
task_metrics = TaskMetrics()
