"""Durable task integration for calendar-aware raw data ingestion."""

from datetime import date

from app.config import SessionLocal
from app.services.job_store import job_store
from app.services.market_data_sync import sync_calendar, sync_history
from app.services.tasks import TaskCancelledError, register_runner


@register_runner("market_history_sync")
def run_market_history_sync(job_id: str, payload: dict) -> None:
    def progress(done: int, total: int, report: dict) -> None:
        current = job_store.get(job_id)
        if current is None or current.status == "cancelled":
            raise TaskCancelledError("Market-data synchronization cancelled")
        job_store.update(job_id, progress=done / total,
                         message=f"Downloaded {done}/{total} securities",
                         result={key: value for key, value in report.items() if key != "batches"})

    with SessionLocal() as db:
        start, end = date.fromisoformat(payload["start_date"]), date.fromisoformat(payload["end_date"])
        sync_calendar(db, start, end)
        report = sync_history(db, payload["codes"], start, end,
                              metadata=bool(payload.get("metadata")), progress=progress)
        job_store.update(job_id, status="completed" if report["success"] else "failed",
                         progress=report["processed"] / report["requested"], result=report,
                         error=None if report["success"] else "Incomplete historical market data",
                         message=f"Complete {report['completed']}; failed {report['failed']}")
