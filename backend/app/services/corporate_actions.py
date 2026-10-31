"""Snapshot-backed action coverage and explicitly retrospective chart adjustments."""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.market_data import MarketMetadataBatch
from app.services.market_data import as_date, digest, load_bars, naive_utc, number, utcnow
from app.services.corporate_action_ledger import normalize_dividends


def store_metadata_batch(db: Session, code: str, kind: str, rows: list[dict], *,
                          start: date, end: date, provider: str,
                          observed_at: datetime | None = None) -> MarketMetadataBatch:
    if kind not in {"adjustment_factor", "dividend"} or start > end:
        raise ValueError("Invalid metadata kind or coverage")
    normalized = sorted(rows, key=digest)
    for row in normalized:
        if row.get("code", code) != code:
            raise ValueError("Metadata response contains another security")
        if row.get("dividOperateDate") and not start <= as_date(row["dividOperateDate"]) <= end:
            raise ValueError("Metadata event outside requested coverage")
    checksum = digest(normalized)
    observation = naive_utc(observed_at or utcnow())
    batch_id = digest({"code": code, "kind": kind, "start": start, "end": end,
                       "provider": provider, "observed_at": observation, "checksum": checksum})
    batch = db.get(MarketMetadataBatch, batch_id)
    if batch is None:
        batch = MarketMetadataBatch(batch_id=batch_id, stock_code=code, kind=kind,
                                    start_date=start, end_date=end, provider=provider,
                                    observed_at=observation, checksum=checksum, payload=normalized)
        db.add(batch)
        db.flush()
    return batch


def metadata_snapshot(db: Session, code: str, kind: str, start: date, end: date, *,
                       observed_before: datetime | None = None) -> tuple[list[dict], list[str]]:
    """Use the latest complete response for each date; revisions can remove events."""
    query = db.query(MarketMetadataBatch).filter(
        MarketMetadataBatch.stock_code == code, MarketMetadataBatch.kind == kind,
        MarketMetadataBatch.start_date <= end, MarketMetadataBatch.end_date >= start)
    if observed_before:
        query = query.filter(MarketMetadataBatch.observed_at <= naive_utc(observed_before))
    batches = query.order_by(MarketMetadataBatch.observed_at.desc(), MarketMetadataBatch.batch_id.desc()).all()
    coverage = []
    selected = {}
    used = set()
    for batch in batches:
        left, right = max(start, batch.start_date), min(end, batch.end_date)
        uncovered = [(left, right)]
        for covered_left, covered_right in coverage:
            next_ranges = []
            for a, b in uncovered:
                if a < covered_left:
                    next_ranges.append((a, min(b, covered_left - timedelta(days=1))))
                if b > covered_right:
                    next_ranges.append((max(a, covered_right + timedelta(days=1)), b))
            uncovered = [(a, b) for a, b in next_ranges if a <= b]
        if not uncovered:
            continue
        used.add(batch.batch_id)
        for row in batch.payload:
            if not row.get("dividOperateDate"):
                continue
            effective = as_date(row["dividOperateDate"])
            if any(a <= effective <= b for a, b in uncovered):
                selected[digest(row)] = row
        coverage.extend(uncovered)
    merged = start
    for left, right in sorted(coverage):
        if left > merged:
            break
        merged = max(merged, right + timedelta(days=1))
    if merged <= end:
        raise ValueError(f"{kind} coverage missing for {code} from {merged}; sync metadata first")
    return sorted(selected.values(), key=lambda row: row["dividOperateDate"]), sorted(used)


def adjusted_history(db: Session, code: str, start: date, end: date, *, mode: str,
                      observed_before: datetime | None = None):
    """BaoStock cumulative backward factors; chart-only, never execution prices.

    This is a retrospective provider view. Missing historical publication times
    prevent claiming that these adjustments were known at the historical bar.
    """
    if mode not in {"qfq", "hfq"}:
        raise ValueError("Adjusted chart mode must be qfq or hfq")
    frame, provenance = load_bars(db, code, start, end, observed_before=observed_before)
    # A full factor history establishes the initial factor of 1 before the
    # first ex-date, instead of assuming an arbitrary truncated factor baseline.
    factors, batch_ids = metadata_snapshot(db, code, "adjustment_factor", date(1990, 1, 1), end,
                                            observed_before=observed_before)
    values = {}
    for row in factors:
        day = as_date(row["dividOperateDate"])
        value = number(row["backAdjustFactor"])
        if value <= 0:
            raise ValueError("Adjustment factor must be positive")
        if day in values and values[day] != value:
            raise ValueError("Conflicting adjustment factors for one ex-date")
        values[day] = value
    anchor = float(values[max(values)]) if values else 1.0
    if not frame.empty:
        multipliers = []
        for day in frame["date"]:
            previous = [event_day for event_day in values if event_day <= day]
            cumulative = float(values[max(previous)]) if previous else 1.0
            multipliers.append(cumulative / anchor if mode == "qfq" else cumulative)
        for key in ("open", "high", "low", "close"):
            frame[key] = frame[key] * multipliers
    provenance.update(adjustment=mode, factor_batch_ids=batch_ids,
                      adjustment_as_of=naive_utc(observed_before or utcnow()).isoformat(),
                      retrospective=True, execution_eligible=False, volume_adjusted=False,
                      limitations=["historical_factor_publication_unverified", "not_total_return_accounting"])
    return frame, provenance


def execution_actions(db: Session, code: str, start: date, end: date, *,
                       observed_before: datetime | None = None) -> tuple[list[dict], dict]:
    dividends, dividend_batches = metadata_snapshot(db, code, "dividend", start, end,
                                                    observed_before=observed_before)
    factors, factor_batches = metadata_snapshot(db, code, "adjustment_factor", start, end,
                                                observed_before=observed_before)
    actions = normalize_dividends(dividends)
    unsupported = {as_date(row["dividOperateDate"]) for row in factors} - {action.ex_date for action in actions}
    if unsupported:
        raise ValueError("Ex-date has no supported dividend/share-distribution evidence: "
                         + ",".join(str(day) for day in sorted(unsupported)))
    return [action.snapshot() for action in actions], {
        "dividend_batch_ids": dividend_batches, "factor_batch_ids": factor_batches,
        "event_evidence": "retrospective_implemented_distribution",
        "limitations": ["dividend_tax_is_flat_research_assumption", "fractional_allocations_fail_closed",
                        "rights_issues_require_separate_adapter"],
    }
