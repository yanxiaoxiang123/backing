"""Repeatable data synchronization command for OS schedulers.

Defaults to configured watchlist, never silently starts a full-market download.
Exit status 2 means requested history is still incomplete or provider failed.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import SessionLocal, settings
from app.models.models import DailyKline, Stock, WatchlistItem
from app.services.baostock_service import baostock_service
from app.services.market_data import archive_legacy, utcnow
from app.services.market_data_sync import completed_end, sync_calendar, sync_history, sync_securities, sync_metadata
from app.services.data_quality import coverage_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Synchronize every known stock")
    parser.add_argument("--codes", nargs="+", help="Canonical exchange-prefixed codes")
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--quality-only", action="store_true")
    parser.add_argument("--legacy", action="store_true", help="Use old unversioned adjusted-price sync")
    parser.add_argument("--archive-legacy", action="store_true", help="Preserve old candles with unknown adjustment label")
    parser.add_argument("--calendar-only", action="store_true")
    parser.add_argument("--securities", action="store_true", help="Refresh master including delisted securities")
    parser.add_argument("--metadata", action="store_true", help="Fetch corporate actions and adjustment factors")
    parser.add_argument("--metadata-only", action="store_true", help="Fetch action coverage independently of price ingestion")
    parser.add_argument("--report-file", type=Path, help="Atomically persist progress and final report")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be positive")
    if args.all and args.codes:
        parser.error("Use either --all or --codes")
    if args.metadata_only and args.legacy:
        parser.error("--metadata-only cannot use legacy prices")
    with SessionLocal() as db:
        if args.quality_only:
            print(json.dumps(coverage_report(db), ensure_ascii=True))
            return 0
        if args.archive_legacy:
            print(json.dumps(archive_legacy(db)))
            return 0
        if args.securities:
            print(json.dumps({"securities_updated": sync_securities(db)}))
        if args.calendar_only:
            end = completed_end()
            print(json.dumps({"calendar_rows": sync_calendar(db, end - timedelta(days=args.days), end, refresh=True)}))
            return 0
        codes = args.codes
        if not args.all and not codes:
            codes = list(dict.fromkeys([
                *[row[0] for row in db.query(WatchlistItem.stock_code).all()],
                *settings.watchlist_stocks,
            ]))
            if not codes:
                parser.error("No watchlist configured; supply --codes or --all")
        if codes:
            existing = {row[0] for row in db.query(Stock.code).filter(Stock.code.in_(codes))}
            if set(codes) - existing:
                parser.error("Unknown stock codes: " + ",".join(sorted(set(codes) - existing)))
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        start = today - timedelta(days=args.days)
        if args.metadata_only:
            selected = codes or [row[0] for row in db.query(Stock.code)]
            report = {"metadata_only": True, "requested": len(selected), "completed": 0,
                      "failed": 0, "errors": [], "batches": []}
            for code in selected:
                try:
                    report["batches"].append(sync_metadata(db, code, start, completed_end()))
                    report["completed"] += 1
                except Exception as exc:
                    db.rollback()
                    report["failed"] += 1
                    report["errors"].append({"stock_code": code, "error": str(exc)[:500]})
            report["success"] = report["failed"] == 0
            if args.report_file:
                args.report_file.parent.mkdir(parents=True, exist_ok=True)
                temporary = args.report_file.with_suffix(".tmp")
                temporary.write_text(json.dumps(report, default=str), encoding="utf-8")
                temporary.replace(args.report_file)
            print(json.dumps(report, ensure_ascii=True))
            return 0 if report["success"] else 2
        if not args.legacy:
            end = completed_end()
            selected = codes or [row[0] for row in db.query(Stock.code)]
            def progress(done, total, report):
                if args.report_file:
                    args.report_file.parent.mkdir(parents=True, exist_ok=True)
                    temporary = args.report_file.with_suffix(".tmp")
                    temporary.write_text(json.dumps({**report, "processed": done}, default=str), encoding="utf-8")
                    temporary.replace(args.report_file)
                if done % 25 == 0 or done == total:
                    print(json.dumps({"processed": done, "total": total, "failed": report["failed"]}), flush=True)
            startup = {"phase": "calendar", "requested": len(selected), "completed": 0, "failed": 0,
                       "started_at": utcnow().isoformat()}
            progress(0, len(selected), startup)
            try:
                sync_calendar(db, start, end)
            except Exception as exc:
                db.rollback()
                startup.update(success=False, startup_error=str(exc)[:500], finished_at=utcnow().isoformat())
                progress(0, len(selected), startup)
                print(json.dumps(startup, ensure_ascii=True))
                return 2
            result = sync_history(db, selected, start, end, metadata=args.metadata, progress=progress)
            progress(result["processed"], len(selected), result)
            print(json.dumps(result, ensure_ascii=True))
            return 0 if result["success"] else 2
        count, message = baostock_service.sync_kline_data(
            db, stock_codes=codes, start_date=start.isoformat(),
            end_date=today.isoformat(),
        )
        report = coverage_report(db)
        selected = codes or [row[0] for row in db.query(Stock.code)]
        available = {row[0] for row in db.query(DailyKline.stock_code).filter(
            DailyKline.stock_code.in_(selected), DailyKline.date >= start,
        ).distinct()}
        missing = sorted(set(selected) - available)
        summary = {key: value for key, value in report.items() if key != "items"}
        print(json.dumps({"inserted": count, "message": message, "missing_history": missing,
                          "quality": summary}, ensure_ascii=True))
        # sync_kline_data currently encodes provider failures in its summary.
        return 2 if missing or "failed: 0" not in message else 0


if __name__ == "__main__":
    raise SystemExit(main())
