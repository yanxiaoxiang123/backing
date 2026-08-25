from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.realtime import _cache_daily_bars_for_research
from app.config import Base
from app.models.models import DailyKline, Stock


def test_cache_daily_bars_inserts_and_updates_mootdx_snapshot():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    session.commit()

    first = {
        "date": "2026-08-24",
        "open": 10,
        "high": 11,
        "low": 9,
        "close": 10.5,
        "volume": 100,
        "amount": 1000,
    }
    assert _cache_daily_bars_for_research(session, "sh.600000", [first]) == 1

    updated = {**first, "close": 10.8, "volume": 120}
    assert _cache_daily_bars_for_research(session, "sh.600000", [updated]) == 1

    rows = session.query(DailyKline).all()
    assert len(rows) == 1
    assert rows[0].date == date(2026, 8, 24)
    assert float(rows[0].close) == 10.8
    assert float(rows[0].volume) == 120


def test_cache_daily_bars_ignores_invalid_rows_and_unknown_stock():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    assert _cache_daily_bars_for_research(session, "sh.999999", []) == 0
    session.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    session.commit()
    assert (
        _cache_daily_bars_for_research(
            session,
            "sh.600000",
            [{"date": "bad-date", "close": 1}, {"date": "2026-08-24", "close": 0}],
        )
        == 0
    )
    assert session.query(DailyKline).count() == 0
