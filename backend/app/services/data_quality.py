"""Coverage and OHLCV integrity reporting without calling external providers."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.models import DailyKline, Stock
from app.models.market_data import MarketDailyBar, MarketDataBatch, TradingSession


def coverage_report(db: Session, *, limit: int = 100) -> dict:
    coverage = db.query(
        DailyKline.stock_code.label("code"),
        func.count(DailyKline.id).label("bars"),
        func.min(DailyKline.date).label("first_date"),
        func.max(DailyKline.date).label("last_date"),
    ).group_by(DailyKline.stock_code).subquery()
    total = db.query(func.count(Stock.id)).scalar() or 0
    covered = db.query(func.count()).select_from(coverage).scalar() or 0
    invalid = or_(
        DailyKline.open <= 0, DailyKline.close <= 0, DailyKline.low <= 0,
        DailyKline.high < DailyKline.open, DailyKline.high < DailyKline.close,
        DailyKline.low > DailyKline.open, DailyKline.low > DailyKline.close,
        DailyKline.volume < 0,
        DailyKline.date > datetime.now(ZoneInfo("Asia/Shanghai")).date(),
    )
    anomalies = db.query(func.count(DailyKline.id)).filter(invalid).scalar() or 0
    rows = db.query(Stock.code, Stock.name, coverage.c.bars,
                    coverage.c.first_date, coverage.c.last_date).outerjoin(
                        coverage, Stock.code == coverage.c.code
                    ).order_by(func.coalesce(coverage.c.bars, 0), Stock.code).limit(limit).all()
    return {
        "total_stocks": total, "covered_stocks": covered,
        "missing_stocks": total - covered,
        "coverage_pct": round(covered / total * 100, 2) if total else 0.0,
        "invalid_bars": anomalies,
        "total_bars": db.query(func.count(DailyKline.id)).scalar() or 0,
        "calendar_verified": False,
        "adjustment_provenance": "legacy_unspecified",
        "raw_covered_stocks": db.query(func.count(func.distinct(MarketDataBatch.stock_code))).filter(
            MarketDataBatch.adjustment == "raw",
        ).scalar() or 0,
        "versioned_bars": db.query(func.count()).select_from(MarketDailyBar).scalar() or 0,
        "calendar_rows": db.query(func.count()).select_from(TradingSession).scalar() or 0,
        "items": [{"stock_code": row.code, "name": row.name,
                   "bars": row.bars or 0,
                   "first_date": row.first_date.isoformat() if row.first_date else None,
                   "last_date": row.last_date.isoformat() if row.last_date else None}
                  for row in rows],
    }
