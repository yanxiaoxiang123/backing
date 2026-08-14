"""Arq (Redis-backed) executor — production multi-instance backend.

Activate with ``TASK_BACKEND=arq`` and ``REDIS_URL`` set, install
``requirements-arq.txt``, and run the worker in its own process:

    cd backend && python task_worker.py

Because the worker is a separate process, task execution survives API
restarts and scales horizontally; Redis is the coordination point and the
``jobs`` table remains the source of truth for status/lease/retry state.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.schemas.schemas import JobRecordSchema
from app.services.job_store import job_store
from app.services.tasks.base import TaskExecutor

logger = logging.getLogger(__name__)

_WORKER_FUNCTION = "run_task"


class ArqTaskExecutor(TaskExecutor):
    """Submit jobs to a Redis queue consumed by the Arq worker."""

    def __init__(self) -> None:
        try:
            import arq  # noqa: F401
            import redis  # noqa: F401
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise RuntimeError(
                "TASK_BACKEND=arq requires arq and redis. "
                "Run: pip install -r requirements-arq.txt"
            ) from exc
        if not settings.REDIS_URL:
            raise RuntimeError("TASK_BACKEND=arq requires REDIS_URL to be set")
        self._loop = None
        self._pool = None

    def submit(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        job_key: str | None = None,
    ) -> JobRecordSchema:
        if self._pool is None:
            raise RuntimeError(
                "ArqTaskExecutor not started; call startup() from the FastAPI lifespan"
            )
        job = job_store.create(job_type, payload=payload, job_key=job_key)
        self._loop.run_until_complete(
            self._pool.enqueue_job(_WORKER_FUNCTION, job.id)
        )
        logger.info(
            "task_enqueued", extra={"job_id": job.id, "job_type": job_type, "backend": "arq"}
        )
        return job

    def startup(self) -> None:
        import asyncio

        from arq.connections import RedisSettings, create_pool

        self._loop = asyncio.new_event_loop()
        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        self._pool = self._loop.run_until_complete(create_pool(redis_settings))
        logger.info("task_executor_started", extra={"backend": "arq"})

    def shutdown(self) -> None:
        if self._pool is not None:
            self._loop.run_until_complete(self._pool.aclose())
        if self._loop is not None:
            self._loop.close()
        logger.info("task_executor_stopped", extra={"backend": "arq"})
