"""Calendar-driven idempotent synchronization and structured completion reports."""

import time
import os
from contextlib import contextmanager
from datetime import date, datetime, time as daytime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.models import Stock
from app.models.market_data import SecurityObservation
from app.services.market_data import (
    as_date, history_gaps, open_sessions, store_action, store_bars,
    store_calendar, store_security, utcnow,
    digest, store_session_statuses,
)
from app.services.market_data_provider import BaostockMarketDataProvider
from app.services.corporate_actions import store_metadata_batch


def completed_end(now: datetime | None = None) -> date:
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    local = current.astimezone(ZoneInfo("Asia/Shanghai"))
    return local.date() if local.time() >= daytime(15, 30) else local.date() - timedelta(days=1)


def sync_calendar(db: Session, start: date, end: date, provider=None, *, refresh: bool = False) -> int:
    if not refresh:
        try:
            for exchange in ("sh", "sz"):
                open_sessions(db, exchange, start, end)
            return 0
        except ValueError:
            pass
    provider = provider or BaostockMarketDataProvider()
    rows = provider.calendar(start, end)
    dates = {as_date(row["date"]) for row in rows}
    if len(rows) != (end - start).days + 1 or dates != {
        start + timedelta(days=offset) for offset in range((end - start).days + 1)
    }:
        raise ValueError("Provider returned an incomplete trading calendar")
    count = 0
    for exchange in ("sh", "sz"):
        count += store_calendar(db, exchange, rows, provider=provider.name)
    db.commit()
    return count


def sync_securities(db: Session, provider=None) -> int:
    provider = provider or BaostockMarketDataProvider()
    rows = provider.securities()
    if not rows:
        raise ValueError("Provider returned an empty security master")
    count = sum(store_security(db, row, provider=provider.name) for row in rows)
    db.commit()
    return count


@contextmanager
def ingestion_lock(db: Session, scope: str = "history", *, wait_timeout_s: float = 0):
    from app.config import BACKEND_DIR

    deadline = time.monotonic() + wait_timeout_s
    if db.bind.dialect.name == "postgresql":
        # Keep a dedicated session-level advisory lock across per-stock commits.
        key = int(digest("backing.market_data.ingestion" if scope == "history" else scope)[:15], 16)
        with db.bind.connect() as connection:
            while not connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar():
                if time.monotonic() >= deadline:
                    raise ValueError("Another market-data ingestion is active for this scope")
                time.sleep(0.1)
            try:
                yield
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        return
    if db.bind.dialect.name != "sqlite":
        raise ValueError("Market ingestion lock supports SQLite and PostgreSQL only")
    lock_dir = BACKEND_DIR / "data" / "sync"
    lock_dir.mkdir(parents=True, exist_ok=True)
    identity = str(db.bind.url) if scope == "history" else str(db.bind.url) + ":" + scope
    lock_path = lock_dir / (digest(identity) + ".lock")
    with Path(lock_path).open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise ValueError("Another market-data ingestion is active for this scope") from exc
                time.sleep(0.1)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def sync_history(db: Session, codes: list[str], start: date, end: date, **kwargs) -> dict:
    return _sync_history(db, codes, start, end, **kwargs)


def _sync_history(db: Session, codes: list[str], start: date, end: date, *,
                 provider=None, rate_limit_s: float = 1.0, metadata: bool = False,
                 progress=None) -> dict:
    if not codes or end < start:
        raise ValueError("Nonempty universe and valid date range required")
    provider = provider or BaostockMarketDataProvider()
    report = {"requested": len(set(codes)), "completed": 0, "failed": 0, "skipped": [], "batches": [],
              "errors": [], "missing_sessions": {}, "started_at": utcnow().isoformat()}
    provider_failures = 0
    for index, code in enumerate(dict.fromkeys(codes)):
        report["processed"] = index + 1
        try:
            # Hold one security at a time: an all-market job must not block
            # interactive requests for unrelated securities for hours.
            with ingestion_lock(db, scope="history:" + code, wait_timeout_s=120):
                stock = db.query(Stock).filter_by(code=code).one_or_none()
                if stock is None:
                    raise ValueError("Security not present in master")
                begin = max(start, stock.list_date) if stock.list_date else start
                status = db.query(SecurityObservation).filter_by(stock_code=code).order_by(
                    SecurityObservation.observed_at.desc(), SecurityObservation.id.desc()).first()
                finish = min(end, status.delisted_on - timedelta(days=1)) if status and status.delisted_on else end
                if begin > finish:
                    report["skipped"].append({"stock_code": code, "reason": "outside_listing_interval"})
                    if progress:
                        progress(index + 1, report["requested"], report)
                    continue
                gaps = history_gaps(db, code, begin, finish)
                if gaps:
                    rows = provider.bars(code, min(gaps), max(gaps))
                    time.sleep(max(0, rate_limit_s))
                    if rows:
                        if any(as_date(row["date"]) < min(gaps) or as_date(row["date"]) > max(gaps) for row in rows):
                            raise ValueError("Provider returned dates outside the requested interval")
                        batch = store_bars(db, code, rows, provider=provider.name)
                        report["batches"].append(batch.batch_id)
                        db.commit()
                    gaps = history_gaps(db, code, begin, finish)
                if gaps and hasattr(provider, "session_statuses"):
                    for day in gaps:
                        statuses = provider.session_statuses(day)
                        # Persist suspended peers too, avoiding repeated universe calls
                        # for the same dates without retaining every traded symbol.
                        evidence = [row for row in statuses
                                    if row["suspended"] or row["stock_code"] == code]
                        if any(as_date(row["date"]) != day for row in evidence):
                            raise ValueError("Provider returned status for the wrong session")
                        store_session_statuses(db, evidence, provider=provider.name)
                        db.commit()
                        time.sleep(max(0, rate_limit_s))
                    gaps = history_gaps(db, code, begin, finish)
                if gaps:
                    report["missing_sessions"][code] = [day.isoformat() for day in gaps]
                    raise ValueError(f"Missing {len(gaps)} verified trading sessions")
                if metadata:
                    sync_metadata(db, code, start, end, provider=provider, rate_limit_s=rate_limit_s)
                report["completed"] += 1
                provider_failures = 0
        except Exception as exc:
            db.rollback()
            report["failed"] += 1
            report["errors"].append({"stock_code": code, "error": str(exc)[:500]})
            provider_failures = provider_failures + 1 if isinstance(exc, (TimeoutError, ConnectionError, RuntimeError)) else 0
            time.sleep(max(0, rate_limit_s))
            if provider_failures >= 3:
                report["aborted"] = "provider_unavailable"
                report["unprocessed"] = report["requested"] - report["processed"]
        if progress:
            progress(index + 1, report["requested"], report)
        if report.get("aborted"):
            break
    report["finished_at"] = utcnow().isoformat()
    report["success"] = report["completed"] + len(report["skipped"]) == report["requested"]
    return report


def sync_metadata(db: Session, code: str, start: date, end: date, *,
                  provider=None, rate_limit_s: float = 1.0) -> dict:
    if end < start:
        raise ValueError("Metadata end precedes start")
    provider = provider or BaostockMarketDataProvider()
    batch_ids = []
    with ingestion_lock(db, scope="metadata:" + code, wait_timeout_s=120):
        factor_start = date(1990, 1, 1)
        factors = provider.factors(code, factor_start, end)
        batch_ids.append(store_metadata_batch(db, code, "adjustment_factor", factors,
                                              start=factor_start, end=end, provider=provider.name).batch_id)
        for row in factors:
            store_action(db, code, "adjustment_factor", row, provider=provider.name,
                         effective_date=as_date(row["dividOperateDate"]))
        db.commit()
        time.sleep(max(0, rate_limit_s))
        for year in range(start.year, end.year + 1):
            covered_end = min(end, date(year, 12, 31))
            rows = provider.dividends(code, year)
            dividends = [row for row in rows if row.get("dividOperateDate")
                         and date(year, 1, 1) <= as_date(row["dividOperateDate"]) <= covered_end]
            batch_ids.append(store_metadata_batch(db, code, "dividend", dividends,
                                                  start=date(year, 1, 1), end=covered_end,
                                                  provider=provider.name).batch_id)
            for row in dividends:
                published = row.get("dividPlanDate")
                announced = (datetime.combine(as_date(published) + timedelta(days=1), daytime.min,
                                              tzinfo=ZoneInfo("Asia/Shanghai")) if published else None)
                store_action(db, code, "dividend", row, provider=provider.name,
                             effective_date=as_date(row["dividOperateDate"]), announced_at=announced)
            db.commit()
            time.sleep(max(0, rate_limit_s))
    return {"stock_code": code, "metadata_batch_ids": batch_ids}


def calendar_quality(db: Session, code: str, start: date, end: date, *,
                     observed_before: datetime | None = None) -> dict:
    try:
        expected = open_sessions(db, code.split(".")[0], start, end)
        gaps = history_gaps(db, code, start, end, observed_before=observed_before)
    except ValueError as exc:
        return {"calendar_verified": False, "reason": str(exc), "complete": False}
    return {"calendar_verified": True, "expected_sessions": len(expected),
            "missing_sessions": [day.isoformat() for day in gaps], "complete": not gaps}
