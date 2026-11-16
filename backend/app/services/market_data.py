"""Versioned observations and exchange-calendar-aware history ingestion."""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models.market_data import (
    CorporateActionObservation, MarketDailyBar, MarketDataBatch,
    SecurityObservation, SecuritySessionObservation, TradingSession,
)
from app.models.models import DailyKline, Stock


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def naive_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     default=str).encode()).hexdigest()


def as_date(value: Any) -> date:
    return value if isinstance(value, date) and not isinstance(value, datetime) else date.fromisoformat(str(value)[:10])


def number(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid numeric market observation") from exc
    if not result.is_finite():
        raise ValueError("Nonfinite market observation")
    return result


def store_bars(db: Session, code: str, rows: list[dict], *, provider: str,
               adjustment: str = "raw", observed_at: datetime | None = None) -> MarketDataBatch:
    if not rows:
        raise ValueError("Provider returned no history; no batch was created")
    if adjustment not in {"raw", "qfq", "hfq", "legacy_unknown"}:
        raise ValueError("Unknown adjustment mode")
    normalized = []
    for row in rows:
        item = {"date": as_date(row["date"])}
        item.update({key: number(row[key]).quantize(Decimal("0.000001")) for key in ("open", "high", "low", "close")})
        item["volume"] = number(row["volume"]).quantize(Decimal("0.01"))
        item["amount"] = number(row["amount"]).quantize(Decimal("0.01")) if row.get("amount") not in (None, "") else None
        item["suspended"] = bool(row.get("suspended", False))
        item["is_st"] = row.get("is_st")
        if (min(item[key] for key in ("open", "high", "low", "close")) <= 0
                or item["high"] < max(item["open"], item["close"])
                or item["low"] > min(item["open"], item["close"])
                or item["volume"] < 0 or (item["amount"] is not None and item["amount"] < 0)):
            raise ValueError("Inconsistent OHLCV observation")
        normalized.append(item)
    normalized.sort(key=lambda row: row["date"])
    if len({row["date"] for row in normalized}) != len(normalized):
        raise ValueError("Duplicate market dates")
    checksum = digest(normalized)
    batch_id = digest({"code": code, "provider": provider, "adjustment": adjustment, "checksum": checksum})
    existing = db.get(MarketDataBatch, batch_id)
    if existing is not None:
        return existing
    batch = MarketDataBatch(batch_id=batch_id, stock_code=code, provider=provider,
                            adjustment=adjustment, start_date=normalized[0]["date"],
                            end_date=normalized[-1]["date"], observed_at=naive_utc(observed_at or utcnow()),
                            checksum=checksum, row_count=len(normalized))
    db.add(batch)
    db.flush()
    db.add_all([MarketDailyBar(batch_id=batch_id, **row) for row in normalized])
    db.flush()
    return batch


def load_bars(db: Session, code: str, start: date, end: date, *, adjustment: str = "raw",
              observed_before: datetime | None = None) -> tuple[pd.DataFrame, dict]:
    query = db.query(MarketDailyBar, MarketDataBatch).join(
        MarketDataBatch, MarketDataBatch.batch_id == MarketDailyBar.batch_id,
    ).filter(MarketDataBatch.stock_code == code, MarketDataBatch.adjustment == adjustment,
             MarketDailyBar.date >= start, MarketDailyBar.date <= end)
    if observed_before:
        query = query.filter(MarketDataBatch.observed_at <= naive_utc(observed_before))
    # Later observations override only the query view, never the original records.
    latest: dict[date, tuple] = {}
    for bar, batch in query.order_by(MarketDataBatch.observed_at, MarketDataBatch.batch_id):
        latest[bar.date] = (bar, batch)
    records, batches = [], set()
    for day in sorted(latest):
        bar, batch = latest[day]
        batches.add(batch.batch_id)
        records.append({"date": day, **{key: float(getattr(bar, key)) for key in
                                        ("open", "high", "low", "close", "volume")},
                        "amount": float(bar.amount) if bar.amount is not None else None,
                        "suspended": bar.suspended, "is_st": bar.is_st})
    return pd.DataFrame(records), {"adjustment": adjustment, "batch_ids": sorted(batches),
                                  "versioned": True, "observed_before": str(observed_before) if observed_before else None}


def store_calendar(db: Session, exchange: str, rows: list[dict], *, provider: str) -> int:
    if exchange not in {"sh", "sz", "bj"} or not rows:
        raise ValueError("An explicit exchange and nonempty calendar are required")
    for row in rows:
        if not isinstance(row["is_open"], bool):
            raise ValueError("Calendar is_open must be a boolean")
        day = as_date(row["date"])
        existing = db.get(TradingSession, (exchange, day))
        if existing is None:
            db.add(TradingSession(exchange=exchange, date=day, is_open=bool(row["is_open"]),
                                 provider=provider, observed_at=utcnow()))
        elif existing.is_open != bool(row["is_open"]):
            raise ValueError(f"Calendar conflict for {exchange} {day}; explicit correction required")
    db.flush()
    return len(rows)


def open_sessions(db: Session, exchange: str, start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("Calendar end precedes start")
    rows = db.query(TradingSession).filter(
        TradingSession.exchange == exchange, TradingSession.date >= start,
        TradingSession.date <= end,
    ).order_by(TradingSession.date).all()
    if len(rows) != (end - start).days + 1:
        raise ValueError(f"Verified calendar does not cover {exchange} {start}..{end}")
    return [row.date for row in rows if row.is_open]


def next_session(db: Session, exchange: str, after: date) -> date:
    # Never skip an unknown day and accidentally treat it as a holiday.
    for offset in range(1, 32):
        day = after + timedelta(days=offset)
        row = db.get(TradingSession, (exchange, day))
        if row is None:
            raise ValueError(f"Calendar missing {exchange} {day}")
        if row.is_open:
            return day
    raise ValueError("No trading session within verified calendar window")


def store_session_statuses(db: Session, rows: list[dict], *, provider: str,
                           observed_at: datetime | None = None) -> int:
    """Append status revisions without turning absent/unknown statuses into evidence."""
    observation = naive_utc(observed_at or utcnow())
    count = 0
    for row in rows:
        if not isinstance(row["suspended"], bool):
            raise ValueError("Session suspended must be an explicit boolean")
        code, day = row["stock_code"], as_date(row["date"])
        checksum = digest({"suspended": row["suspended"]})
        if db.query(SecuritySessionObservation.id).filter_by(
                stock_code=code, date=day, provider=provider, observed_at=observation,
                checksum=checksum).first():
            continue
        latest = db.query(SecuritySessionObservation).filter_by(
            stock_code=code, date=day, provider=provider).order_by(
                SecuritySessionObservation.observed_at.desc(), SecuritySessionObservation.id.desc()).first()
        if latest and latest.checksum == checksum and latest.observed_at <= observation:
            continue
        db.add(SecuritySessionObservation(stock_code=code, date=day,
                                          suspended=row["suspended"], provider=provider,
                                          observed_at=observation, checksum=checksum))
        count += 1
    db.flush()
    return count


def session_statuses(db: Session, code: str, start: date, end: date, *,
                     observed_before: datetime | None = None) -> dict[date, bool]:
    query = db.query(SecuritySessionObservation).filter(
        SecuritySessionObservation.stock_code == code,
        SecuritySessionObservation.date >= start, SecuritySessionObservation.date <= end)
    if observed_before:
        query = query.filter(SecuritySessionObservation.observed_at <= naive_utc(observed_before))
    # Providers disagreeing at the same latest timestamp do not establish suspension.
    latest = {}
    for row in query.order_by(SecuritySessionObservation.observed_at, SecuritySessionObservation.id):
        previous = latest.get(row.date)
        suspended = row.suspended
        if previous and previous[0] == row.observed_at:
            suspended = previous[1] and suspended
        latest[row.date] = (row.observed_at, suspended)
    return {day: value[1] for day, value in latest.items()}


def history_gaps(db: Session, code: str, start: date, end: date, *,
                 observed_before: datetime | None = None) -> list[date]:
    expected = set(open_sessions(db, code.split(".")[0], start, end))
    frame, _ = load_bars(db, code, start, end, observed_before=observed_before)
    observed = set(frame["date"]) if not frame.empty else set()
    suspended = {day for day, value in session_statuses(
        db, code, start, end, observed_before=observed_before).items() if value}
    return sorted(expected - observed - suspended)


def store_security(db: Session, row: dict, *, provider: str,
                   observed_at: datetime | None = None) -> bool:
    checksum = digest(row)
    code = row["stock_code"]
    if db.query(SecurityObservation.id).filter_by(stock_code=code, checksum=checksum).first():
        return False
    observation = naive_utc(observed_at or utcnow())
    db.add(SecurityObservation(stock_code=code, effective_date=as_date(row.get("effective_date", observation.date())),
                               observed_at=observation, name=row["name"],
                               listed_on=as_date(row["listed_on"]) if row.get("listed_on") else None,
                               delisted_on=as_date(row["delisted_on"]) if row.get("delisted_on") else None,
                               status=row["status"], provider=provider, checksum=checksum))
    stock = db.query(Stock).filter_by(code=code).first()
    if stock is None:
        db.add(Stock(code=code, name=row["name"], market=code.split(".")[0],
                     list_date=as_date(row["listed_on"]) if row.get("listed_on") else None))
    else:
        stock.name = row["name"]
        if row.get("listed_on"):
            stock.list_date = as_date(row["listed_on"])
    db.flush()
    return True


def securities_at(db: Session, as_of: datetime, *, effective_on: date | None = None) -> list[dict]:
    point = naive_utc(as_of)
    rows = db.query(SecurityObservation).filter(SecurityObservation.observed_at <= point,
                                               SecurityObservation.effective_date <= (effective_on or point.date()))
    latest = {}
    for row in rows.order_by(SecurityObservation.observed_at, SecurityObservation.id):
        latest[row.stock_code] = row
    day = effective_on or point.date()
    return [{"stock_code": row.stock_code, "name": row.name, "status": row.status}
            for row in latest.values()
            if (row.listed_on is None or row.listed_on <= day)
            and not (row.status == "delisted" and row.delisted_on is None)
            and (row.delisted_on is None or row.delisted_on > day)]


def store_action(db: Session, code: str, kind: str, row: dict, *, provider: str,
                 effective_date: date, announced_at: datetime | None = None,
                 observed_at: datetime | None = None) -> bool:
    checksum = digest({"row": row, "effective_date": effective_date, "announced_at": announced_at})
    if db.query(CorporateActionObservation.id).filter_by(stock_code=code, kind=kind, checksum=checksum).first():
        return False
    db.add(CorporateActionObservation(stock_code=code, kind=kind, effective_date=effective_date,
                                      announced_at=naive_utc(announced_at) if announced_at else None,
                                      observed_at=naive_utc(observed_at or utcnow()), provider=provider,
                                      checksum=checksum, payload=json.loads(json.dumps(row, default=str))))
    db.flush()
    return True


def actions_at(db: Session, code: str, as_of: datetime) -> list[CorporateActionObservation]:
    point = naive_utc(as_of)
    # Historical publication evidence is mandatory; ex-date alone is insufficient.
    return db.query(CorporateActionObservation).filter(
        CorporateActionObservation.stock_code == code,
        CorporateActionObservation.announced_at.is_not(None),
        CorporateActionObservation.announced_at <= point,
        CorporateActionObservation.observed_at <= point,
    ).order_by(CorporateActionObservation.effective_date).all()


def archive_legacy(db: Session) -> dict:
    batches = []
    codes = [row[0] for row in db.query(DailyKline.stock_code).distinct()]
    for code in codes:
        rows = db.query(DailyKline).filter_by(stock_code=code).order_by(DailyKline.date).all()
        batch = store_bars(db, code, [{"date": row.date, **{key: getattr(row, key) for key in
                           ("open", "high", "low", "close", "volume", "amount")}} for row in rows],
                           provider="legacy_database", adjustment="legacy_unknown")
        batches.append(batch.batch_id)
    db.commit()
    return {"batches": batches, "adjustment": "legacy_unknown", "original_rows_preserved": True}
