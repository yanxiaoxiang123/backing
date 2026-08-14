"""Task executor abstraction + job-runner registry.

Runners are plain functions ``fn(job_id: str, payload: dict)`` registered per
``job_type`` via the ``@register_runner("job_type")`` decorator. Both executors
dispatch through the shared lifecycle in ``app/services/tasks/runner.py``.
"""

from __future__ import annotations

import abc
from collections.abc import Callable
from typing import Any

from app.exceptions import (
    ExternalServiceError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.schemas.schemas import JobRecordSchema


class TaskCancelledError(Exception):
    """Raised by a job runner to signal cooperative cancellation."""


class TaskRetryableError(Exception):
    """Raised by a job runner when the failure is transient and should retry."""


# Registry of job runners keyed by job_type.
TASK_RUNNERS: dict[str, Callable[[str, dict[str, Any]], Any]] = {}


def register_runner(job_type: str):
    """Decorator registering a job runner for *job_type*.

    The wrapped function must accept ``(job_id: str, payload: dict)``.
    """

    def decorator(fn):
        if job_type in TASK_RUNNERS:
            raise ValueError(f"Task runner for {job_type!r} already registered")
        TASK_RUNNERS[job_type] = fn
        return fn

    return decorator


def is_retryable_error(exc: Exception) -> bool:
    """Return True when *exc* is a transient failure worth retrying."""
    if isinstance(exc, (TaskRetryableError, ProviderUnavailableError, ProviderTimeoutError)):
        return True
    if isinstance(exc, ExternalServiceError):
        return exc.retryable
    return False


class TaskExecutor(abc.ABC):
    """Submit and run background jobs behind one interface."""

    @abc.abstractmethod
    def submit(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        job_key: str | None = None,
    ) -> JobRecordSchema:
        """Persist a job record (idempotent on *job_key*) and schedule it."""

    @abc.abstractmethod
    def startup(self) -> None:
        """Start background machinery (dispatcher, worker, connections)."""

    @abc.abstractmethod
    def shutdown(self) -> None:
        """Stop background machinery cleanly."""
