"""Arq worker entry point — runs background tasks in a separate process.

Usage (production multi-instance):

    export TASK_BACKEND=arq
    export REDIS_URL=redis://localhost:6379/0
    pip install -r requirements-arq.txt
    cd backend && python task_worker.py

The worker shares the exact job lifecycle with the in-process thread backend
(``run_job_once``), so retries, leases, cancellation and metrics behave the
same on both backends.
"""

from __future__ import annotations

import importlib
import logging

from app.config import settings
from app.logging_config import setup_logging
from app.services.job_store import job_store
from app.services.tasks.runner import run_job_once

logger = logging.getLogger(__name__)

# Side effects: register the job runners (sync_*, strategy_optimize,
# agent_analysis, screener) so the worker can dispatch them.
for _runner_module in (
    "app.api.agent",
    "app.api.routes",
    "app.api.screener_agent",
    "app.api.strategies.routes",
):
    importlib.import_module(_runner_module)


async def run_task(ctx, job_id: str) -> str:
    """Execute one job; retryable failures are re-enqueued by Arq."""
    outcome = run_job_once(job_id)
    if outcome == "retry":
        # Re-enqueue so the DB-scheduled retry actually executes.
        await ctx["job"].retry()
    elif outcome == "missing":
        logger.error("task_job_missing_in_worker", extra={"job_id": job_id})
    return outcome


# Arq's own retry counter stays high; the DB retry_count is the real gate.
run_task.max_tries = 100  # type: ignore[attr-defined]


async def startup(ctx) -> None:
    # Reconcile state after an API restart: mark in-flight jobs failed so a
    # fresh worker never picks up half-executed work as "completed".
    stale = job_store.reset_stale_jobs()
    if stale:
        logger.warning("worker_reset_stale_jobs", extra={"count": stale})


async def shutdown(ctx) -> None:
    logger.info("task_worker_shutdown")


def main() -> None:
    """Run the Arq worker until SIGINT/SIGTERM."""
    if settings.TASK_BACKEND != "arq":
        raise SystemExit("TASK_BACKEND must be 'arq' to run the task worker")

    import asyncio

    from arq import create_worker
    from arq.connections import RedisSettings

    setup_logging()
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    async def _run() -> None:
        worker = create_worker(
            redis_settings,
            functions=[run_task],
            on_startup=startup,
            on_shutdown=shutdown,
        )
        await worker.async_run()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
