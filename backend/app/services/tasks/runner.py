"""Shared job lifecycle, used by every executor backend.

Handles: lease acquisition + heartbeat, cooperative cancellation checks,
terminal-state updates, retries for transient (retryable) failures with
exponential backoff, and task metrics emission.

``run_job_once`` is the single entry point executed by thread workers and the
Arq worker alike, so behavior is identical across backends.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.logging_config import job_id_var
from app.services.job_store import job_store
from app.services.tasks.base import TASK_RUNNERS, TaskCancelledError, is_retryable_error
from app.services.tasks.metrics import task_metrics

logger = logging.getLogger(__name__)

TERMINAL = {"completed", "failed", "cancelled"}


def _now() -> datetime:
    """Naive UTC now — the jobs table stores naive datetimes."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_cancelled(status: str, error: str | None) -> bool:
    return status == "failed" and (error or "") == "Cancelled"


class _Heartbeat:
    """Refreshes the job lease while the runner executes."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._loop,
            name=f"heartbeat-{self.job_id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(settings.TASK_HEARTBEAT_INTERVAL_S):
            try:
                job_store.update(
                    self.job_id,
                    lease_until=_now() + timedelta(seconds=settings.TASK_LEASE_SECONDS),
                )
            except Exception:
                logger.exception("heartbeat update failed", extra={"job_id": self.job_id})

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)


def run_job_once(job_id: str) -> str:
    """Execute the registered runner for *job_id* with the full lifecycle.

    Guards against duplicate execution: if another executor holds a fresh
    lease on the job, it returns "skipped". Used by the Arq worker and by
    callers that have NOT already claimed the job.

    Returns one of: "completed" | "failed" | "retry" | "cancelled" |
    "missing" | "skipped".
    """
    job = job_store.get(job_id)
    if job is not None and (
        job.status == "running"
        and job.lease_until is not None
        and job.lease_until > _now()
    ):
        return "skipped"  # another executor holds the lease
    return run_claimed_job(job_id)


def run_claimed_job(job_id: str) -> str:
    """Execute the registered runner for *job_id*.

    Assumes the caller already claimed the job (``job_store.claim_due``),
    i.e. lease/status guards are bypassed. Used by the thread executor's
    dispatcher; also re-checks terminal/cancelled state defensively.

    Returns one of: "completed" | "failed" | "retry" | "cancelled" | "missing".
    """
    token = job_id_var.set(job_id)
    try:
        job = job_store.get(job_id)
        if job is None:
            logger.error("task_job_missing", extra={"job_id": job_id})
            return "missing"
        if job.status in TERMINAL:
            return job.status
        if _is_cancelled(job.status, job.error):
            return "cancelled"

        runner = TASK_RUNNERS.get(job.job_type)
        if runner is None:
            job_store.update(
                job_id,
                status="failed",
                error=f"No runner registered for job type {job.job_type!r}",
                message="Task failed",
            )
            task_metrics.inc("task.failed", job_type=job.job_type)
            return "failed"

        # Acquire / renew lease, then execute.
        job_store.update(
            job_id,
            status="running",
            retry_count=job.retry_count or 0,
            lease_until=_now() + timedelta(seconds=settings.TASK_LEASE_SECONDS),
            message="Running",
        )
        heartbeat = _Heartbeat(job_id)
        heartbeat.start()
        try:
            runner(job_id, job.payload or {})
        finally:
            heartbeat.stop()

        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message="Completed",
            error=None,
        )
        task_metrics.inc("task.completed", job_type=job.job_type)
        return "completed"

    except TaskCancelledError:
        job_store.update(
            job_id, status="failed", error="Cancelled", message="Cancelled by user"
        )
        task_metrics.inc("task.cancelled", job_type=job.job_type)
        return "cancelled"

    except Exception as exc:
        current = job_store.get(job_id)
        retry_count = (current.retry_count or 0) if current else 0
        max_retries = (current.max_retries or 0) if current else settings.TASK_MAX_RETRIES
        if is_retryable_error(exc) and retry_count < max_retries:
            next_retry = _now() + timedelta(
                seconds=settings.TASK_RETRY_BACKOFF_S * (retry_count + 1)
            )
            job_store.update(
                job_id,
                status="pending",
                retry_count=retry_count + 1,
                next_retry_at=next_retry,
                error=str(exc),
                message=(
                    f"Retrying in {settings.TASK_RETRY_BACKOFF_S * (retry_count + 1)}s "
                    f"({retry_count + 1}/{max_retries})"
                ),
            )
            task_metrics.inc("task.retry", job_type=job.job_type)
            logger.warning(
                "task_retry_scheduled",
                extra={
                    "job_id": job_id,
                    "retry_count": retry_count + 1,
                    "error": str(exc),
                },
            )
            return "retry"

        job_store.update(
            job_id, status="failed", error=str(exc), message="Task failed"
        )
        task_metrics.inc("task.failed", job_type=job.job_type)
        logger.error(
            "task_failed",
            exc_info=exc,
            extra={"job_id": job_id, "error": str(exc)},
        )
        return "failed"

    finally:
        job_id_var.reset(token)
