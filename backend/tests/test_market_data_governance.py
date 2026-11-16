from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.models.market_data import MarketDataBatch
from app.models.models import DailyKline, Stock
from app.services.market_data import (
    actions_at, archive_legacy, history_gaps, load_bars, next_session,
    open_sessions, securities_at, store_action, store_bars, store_calendar, store_security,
    store_session_statuses, session_statuses,
)
from app.services.market_data_sync import completed_end, sync_calendar, sync_history


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(Stock(code="sh.600000", name="A", market="sh"))
        session.commit()
        yield session
    engine.dispose()


def bar(day=date(2024, 1, 2), close=10):
    return {"date": day, "open": 10, "high": 15, "low": 8, "close": close,
            "volume": 10000, "amount": 100000}


def test_revised_prices_keep_old_observation_replayable(db):
    a = store_bars(db, "sh.600000", [bar()], provider="test", observed_at=datetime(2024, 1, 3))
    b = store_bars(db, "sh.600000", [bar(close=11)], provider="test", observed_at=datetime(2024, 1, 5))
    db.commit()
    assert a.batch_id != b.batch_id
    frame, metadata = load_bars(db, "sh.600000", date(2024, 1, 1), date(2024, 1, 8),
                                observed_before=datetime(2024, 1, 4))
    assert frame.iloc[0]["close"] == 10
    assert metadata["batch_ids"] == [a.batch_id]
    latest, _ = load_bars(db, "sh.600000", date(2024, 1, 1), date(2024, 1, 8))
    assert latest.iloc[0]["close"] == 11


def test_identical_download_is_idempotent_and_adjustments_never_mix(db):
    a = store_bars(db, "sh.600000", [bar()], provider="test")
    b = store_bars(db, "sh.600000", [bar()], provider="test")
    assert a.batch_id == b.batch_id
    store_bars(db, "sh.600000", [bar(close=9)], provider="test", adjustment="qfq")
    db.commit()
    assert db.query(MarketDataBatch).count() == 2
    frame, _ = load_bars(db, "sh.600000", date(2024, 1, 1), date(2024, 1, 8))
    assert frame.iloc[0]["close"] == 10


def test_calendar_detects_interior_history_holes_and_holidays(db):
    start = date(2024, 1, 1)
    store_calendar(db, "sh", [{"date": start + timedelta(days=i), "is_open": i in (1, 2, 3)}
                               for i in range(5)], provider="test")
    store_bars(db, "sh.600000", [bar(start + timedelta(days=1)), bar(start + timedelta(days=3))], provider="test")
    assert history_gaps(db, "sh.600000", start, start + timedelta(days=4)) == [date(2024, 1, 3)]
    assert next_session(db, "sh", start) == date(2024, 1, 2)
    with pytest.raises(ValueError, match="Calendar missing"):
        next_session(db, "sh", date(2024, 1, 5))
    with pytest.raises(ValueError, match="does not cover"):
        open_sessions(db, "sh", start, date(2024, 1, 6))


def test_security_history_does_not_invent_past_knowledge(db):
    store_security(db, {"stock_code": "sh.600000", "name": "A", "status": "listed",
                        "listed_on": "2020-01-01"}, provider="test", observed_at=datetime(2024, 1, 2))
    store_security(db, {"stock_code": "sh.600000", "name": "A2", "status": "delisted",
                        "listed_on": "2020-01-01", "delisted_on": "2024-02-01"},
                   provider="test", observed_at=datetime(2024, 2, 2))
    assert securities_at(db, datetime(2024, 1, 1)) == []
    assert securities_at(db, datetime(2024, 1, 3))[0]["name"] == "A"
    assert securities_at(db, datetime(2024, 2, 3)) == []


def test_missing_publication_time_cannot_support_historical_actions(db):
    store_action(db, "sh.600000", "adjustment_factor", {"factor": 0.9}, provider="test",
                 effective_date=date(2024, 1, 2), observed_at=datetime(2024, 1, 1))
    assert actions_at(db, "sh.600000", datetime(2024, 1, 3)) == []
    store_action(db, "sh.600000", "dividend", {"cash": 0.1}, provider="test",
                 effective_date=date(2024, 1, 2), announced_at=datetime(2024, 1, 1),
                 observed_at=datetime(2024, 1, 4))
    assert actions_at(db, "sh.600000", datetime(2024, 1, 3)) == []
    assert len(actions_at(db, "sh.600000", datetime(2024, 1, 5))) == 1


def test_legacy_archival_preserves_rows_and_never_labels_them_raw(db):
    db.add(DailyKline(stock_code="sh.600000", **bar()))
    db.commit()
    report = archive_legacy(db)
    assert report["original_rows_preserved"]
    assert db.query(DailyKline).count() == 1
    assert db.query(MarketDataBatch).one().adjustment == "legacy_unknown"
    frame, _ = load_bars(db, "sh.600000", date(2024, 1, 1), date(2024, 1, 3))
    assert frame.empty


def test_sync_empty_provider_does_not_claim_complete(db):
    class Provider:
        name = "test"

        def bars(self, *args):
            return []

    store_calendar(db, "sh", [{"date": "2024-01-02", "is_open": True}], provider="test")
    result = sync_history(db, ["sh.600000"], date(2024, 1, 2), date(2024, 1, 2),
                          provider=Provider(), rate_limit_s=0)
    assert not result["success"]
    assert result["failed"] == 1
    assert result["missing_sessions"]["sh.600000"] == ["2024-01-02"]


def test_sync_repairs_internal_gap_without_rewriting_old_batch(db):
    class Provider:
        name = "test"

        def bars(self, code, start, end):
            assert start == end == date(2024, 1, 3)
            return [bar(start)]

    start = date(2024, 1, 2)
    store_calendar(db, "sh", [{"date": start + timedelta(days=i), "is_open": True} for i in range(3)], provider="test")
    old = store_bars(db, "sh.600000", [bar(start), bar(start + timedelta(days=2))], provider="test")
    db.commit()
    result = sync_history(db, ["sh.600000"], start, start + timedelta(days=2),
                          provider=Provider(), rate_limit_s=0)
    assert result["success"]
    assert db.get(MarketDataBatch, old.batch_id).row_count == 2
    assert history_gaps(db, "sh.600000", start, start + timedelta(days=2)) == []


def test_calendar_provider_cannot_substitute_sparse_trading_days_for_daily_coverage(db):
    class Provider:
        name = "test"

        def calendar(self, *args):
            return [{"date": "2024-01-02", "is_open": True}]

    with pytest.raises(ValueError, match="incomplete"):
        sync_calendar(db, date(2024, 1, 1), date(2024, 1, 3), Provider())


def test_verified_calendar_is_reused_without_a_network_call(db):
    class Provider:
        name = "must-not-be-called"

        def calendar(self, *args):
            raise AssertionError("Verified calendar should not be fetched again")

    day = date(2024, 1, 2)
    for exchange in ("sh", "sz"):
        store_calendar(db, exchange, [{"date": day, "is_open": True}], provider="fixture")
    assert sync_calendar(db, day, day, Provider()) == 0


def test_repeated_provider_failure_stops_without_claiming_unattempted_symbols_complete(db):
    class Provider:
        name = "offline"

        def bars(self, *args):
            raise TimeoutError("provider login timed out")

    codes = ["sh.600000", "sh.600001", "sh.600002", "sh.600003"]
    db.add_all(Stock(code=code, name=code, market="sh") for code in codes[1:])
    day = date(2024, 1, 2)
    store_calendar(db, "sh", [{"date": day, "is_open": True}], provider="fixture")
    db.commit()
    report = sync_history(db, codes, day, day, provider=Provider(), rate_limit_s=0)
    assert report["aborted"] == "provider_unavailable"
    assert report["failed"] == report["processed"] == 3
    assert report["unprocessed"] == 1
    assert not report["success"]


def test_incomplete_current_daily_bar_is_not_downloaded():
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Shanghai")
    assert completed_end(datetime(2024, 1, 2, 14, tzinfo=tz)) == date(2024, 1, 1)
    assert completed_end(datetime(2024, 1, 2, 17, tzinfo=tz)) == date(2024, 1, 2)


def test_suspension_evidence_is_temporal_and_reversible_without_inventing_candles(db):
    day = date(2024, 1, 2)
    store_calendar(db, "sh", [{"date": day, "is_open": True}], provider="test")
    row = {"stock_code": "sh.600000", "date": day, "suspended": True}
    assert store_session_statuses(db, [row], provider="test", observed_at=datetime(2024, 1, 3)) == 1
    assert history_gaps(db, "sh.600000", day, day, observed_before=datetime(2024, 1, 2)) == [day]
    assert history_gaps(db, "sh.600000", day, day) == []
    row["suspended"] = False
    store_session_statuses(db, [row], provider="test", observed_at=datetime(2024, 1, 4))
    assert history_gaps(db, "sh.600000", day, day) == [day]
    row["suspended"] = True
    store_session_statuses(db, [row], provider="test", observed_at=datetime(2024, 1, 5))
    assert history_gaps(db, "sh.600000", day, day) == []
    assert store_session_statuses(db, [row], provider="test", observed_at=datetime(2024, 1, 6)) == 0
    assert load_bars(db, "sh.600000", day, day)[0].empty


def test_conflicting_simultaneous_status_does_not_establish_suspension(db):
    day, observed = date(2024, 1, 2), datetime(2024, 1, 3)
    for provider, suspended in [("first", True), ("second", False)]:
        store_session_statuses(db, [{"stock_code": "sh.600000", "date": day, "suspended": suspended}],
                               provider=provider, observed_at=observed)
    assert session_statuses(db, "sh.600000", day, day) == {day: False}


@pytest.mark.parametrize("status,complete", [(True, True), (False, False), (None, False)])
def test_sync_only_excuses_explicit_suspension(db, status, complete):
    day = date(2024, 1, 2)

    class Provider:
        name = "test"

        def bars(self, *args):
            return []

        def session_statuses(self, requested_day):
            assert requested_day == day
            return ([{"stock_code": "sh.600000", "date": day, "suspended": status}]
                    if status is not None else [])

    store_calendar(db, "sh", [{"date": day, "is_open": True}], provider="test")
    report = sync_history(db, ["sh.600000"], day, day, provider=Provider(), rate_limit_s=0)
    assert report["success"] is complete
    assert load_bars(db, "sh.600000", day, day)[0].empty
