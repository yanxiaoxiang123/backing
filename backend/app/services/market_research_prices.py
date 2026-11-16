"""One price-selection policy for charts, signals, optimization and execution."""

from datetime import date, datetime, timedelta
from typing import Literal

import pandas as pd
from sqlalchemy.orm import Session

from app.models.market_data import MarketDataBatch, SecurityObservation
from app.models.models import DailyKline, Stock
from app.services.market_data import load_bars, naive_utc, open_sessions
from app.services.market_data_sync import calendar_quality

PriceSource = Literal["auto", "raw", "legacy"]


def load_research_bars(db: Session, code: str, start: date, end: date, *,
                       source: PriceSource = "auto", require_complete: bool = True,
                       observed_before: datetime | None = None) -> pd.DataFrame:
    if source not in {"auto", "raw", "legacy"} or end < start:
        raise ValueError("Invalid price source or date range")
    batches = db.query(MarketDataBatch.batch_id).filter_by(stock_code=code, adjustment="raw")
    if observed_before:
        batches = batches.filter(MarketDataBatch.observed_at <= naive_utc(observed_before))
    use_raw = source == "raw" or (source == "auto" and batches.first() is not None)
    if use_raw:
        frame, provenance = load_bars(db, code, start, end, observed_before=observed_before)
        stock = db.query(Stock).filter_by(code=code).first()
        begin = max(start, stock.list_date) if stock and stock.list_date else start
        statuses = db.query(SecurityObservation).filter_by(stock_code=code)
        if observed_before:
            statuses = statuses.filter(SecurityObservation.observed_at <= naive_utc(observed_before))
        status = statuses.order_by(SecurityObservation.observed_at.desc(), SecurityObservation.id.desc()).first()
        finish = min(end, status.delisted_on - timedelta(days=1)) if status and status.delisted_on else end
        quality = (calendar_quality(db, code, begin, finish, observed_before=observed_before)
                   if begin <= finish else {"complete": False, "reason": "outside_listing_interval"})
        if require_complete and not quality["complete"]:
            detail = quality.get("reason") or f"{len(quality['missing_sessions'])} missing sessions"
            raise ValueError(f"Raw history incomplete for {code}: {detail}; synchronize history first")
        provenance.update(source="raw", quality=quality,
                          limitations=["corporate_actions_not_applied", "retrospective_observations"])
        if quality.get("calendar_verified"):
            sessions = open_sessions(db, code.split(".")[0], begin, finish)
            if not frame.empty and not set(frame["date"]) <= set(sessions):
                raise ValueError(f"Raw prices on a verified closed session for {code}")
            frame.attrs["session_dates"] = [day.isoformat() for day in sessions]
    else:
        if observed_before is not None:
            raise ValueError("Legacy history has no observation timestamps for the requested cutoff")
        rows = db.query(DailyKline).filter(
            DailyKline.stock_code == code, DailyKline.date >= start, DailyKline.date <= end,
        ).order_by(DailyKline.date).all()
        frame = pd.DataFrame([{"date": row.date, **{
            key: float(getattr(row, key)) if getattr(row, key) is not None else None
            for key in ("open", "high", "low", "close", "volume", "amount")}} for row in rows])
        provenance = {"source": "legacy", "adjustment": "legacy_unknown", "versioned": False,
                      "batch_ids": [], "quality": {"calendar_verified": False, "complete": False},
                      "limitations": ["legacy_adjustment_provenance_unknown", "no_exchange_calendar",
                                      "corporate_actions_not_applied"]}
    frame.attrs["provenance"] = provenance
    return frame
