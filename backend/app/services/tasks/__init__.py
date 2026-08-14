"""Background task execution.

Job *state* is persisted in the ``jobs`` table (see ``app/services/job_store.py``);
this package decides where job *execution* runs and standardizes its lifecycle:

* ``ThreadTaskExecutor`` — in-process threads (default; dev & single instance).
* ``ArqTaskExecutor`` — separate Arq worker + Redis (production, multi-instance;
  survives API restarts because the worker is a different process).

Both backends share one lifecycle (``app/services/tasks/runner.py``):
pending → running → completed / failed, with idempotency keys, lease/heartbeat,
retries for transient provider failures, cooperative cancellation, and task
metrics (``app/services/tasks/metrics.py``).

Backends are selected via ``settings.TASK_BACKEND`` ("threads" | "arq").
"""

from __future__ import annotations

from app.config import settings
from app.services.tasks.base import (
    TASK_RUNNERS,
    TaskCancelledError,
    TaskExecutor,
    TaskRetryableError,
    is_retryable_error,
    register_runner,
)
from app.services.tasks.metrics import task_metrics

__all__ = [
    "TASK_RUNNERS",
    "TaskCancelledError",
    "TaskExecutor",
    "TaskRetryableError",
    "get_task_executor",
    "is_retryable_error",
    "register_runner",
    "task_metrics",
]

_executor: TaskExecutor | None = None


def get_task_executor() -> TaskExecutor:
    """Return the process-wide executor for ``settings.TASK_BACKEND``."""
    global _executor
    if _executor is None:
        if settings.TASK_BACKEND == "arq":
            from app.services.tasks.arq import ArqTaskExecutor

            _executor = ArqTaskExecutor()
        else:
            from app.services.tasks.threads import ThreadTaskExecutor

            _executor = ThreadTaskExecutor()
    return _executor


def reset_task_executor() -> None:
    """Drop the cached executor (used by tests)."""
    global _executor
    _executor = None
