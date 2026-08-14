"""In-process thread executor (default backend).

Runs a single dispatcher loop that atomically claims due jobs from the
database (``job_store.claim_due``) and executes each in a worker thread.
Because claiming is database-atomic, multiple API instances can safely share
one database: only one instance ever runs a given job, and leases let a
crashed instance's jobs be reclaimed.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.config import settings
from app.schemas.schemas import JobRecordSchema
from app.services.job_store import job_store
from app.services.tasks.base import TaskExecutor
from app.services.tasks.runner import run_claimed_job

logger = logging.getLogger(__name__)


class ThreadTaskExecutor(TaskExecutor):
    """Submit jobs to in-process threads with DB-atomic claiming."""

    def __init__(self, max_workers: int = 8) -> None:
        self._max_workers = max_workers
        self._stop = threading.Event()
        self._dispatcher: threading.Thread | None = None
        self._running: set[str] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # TaskExecutor interface
    # ------------------------------------------------------------------

    def submit(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        job_key: str | None = None,
    ) -> JobRecordSchema:
        job = job_store.create(job_type, payload=payload, job_key=job_key)
        self._dispatch_once()  # start it immediately (dispatcher also sweeps)
        return job

    def startup(self) -> None:
        if self._dispatcher is not None and self._dispatcher.is_alive():
            return
        self._stop.clear()
        self._dispatcher = threading.Thread(
            target=self._dispatch_loop,
            name="task-dispatcher",
            daemon=True,
        )
        self._dispatcher.start()
        logger.info("task_executor_started", extra={"backend": "threads"})

    def shutdown(self) -> None:
        self._stop.set()
        if self._dispatcher is not None:
            self._dispatcher.join(timeout=2)
        logger.info("task_executor_stopped", extra={"backend": "threads"})

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def _dispatch_loop(self) -> None:
        while not self._stop.wait(settings.TASK_SWEEP_INTERVAL_S):
            try:
                self._dispatch_once()
            except Exception:
                logger.exception("task dispatcher iteration failed")

    def _dispatch_once(self) -> int:
        """Claim and start as many due jobs as worker slots allow."""
        claimed = 0
        while claimed < self._max_workers:
            with self._lock:
                if len(self._running) >= self._max_workers:
                    break
            job = job_store.claim_due()
            if job is None:
                break
            with self._lock:
                self._running.add(job.id)
            thread = threading.Thread(
                target=self._run_worker,
                args=(job.id,),
                name=f"task-{job.id[:8]}",
                daemon=False,
            )
            thread.start()
            claimed += 1
        return claimed

    def _run_worker(self, job_id: str) -> None:
        try:
            run_claimed_job(job_id)
        except Exception:
            logger.exception("task worker crashed", extra={"job_id": job_id})
        finally:
            with self._lock:
                self._running.discard(job_id)
