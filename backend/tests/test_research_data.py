from datetime import date, datetime, timedelta

import pytest

from app.services.market_data import store_bars, store_calendar, store_session_statuses
from app.services.market_research_prices import load_research_bars
from app.services.backtest_executor import BacktestExecutor
from app.services.indicator_service import IndicatorService
from test_backtest_executor import build_session, seed_market_data


def test_raw_research_does_not_mix_legacy_prices_and_partial_raw_history():
    with build_session() as db:
        seed_market_data(db)
        day = date(2024, 1, 1)
        row = {"date": day, "open": 20, "high": 21, "low": 19, "close": 20,
               "volume": 100000}
        store_bars(db, "sh.600000", [row], provider="test")
        store_calendar(db, "sh", [{"date": day + timedelta(days=i), "is_open": True}
                                   for i in range(12)], provider="test")
        with pytest.raises(ValueError, match="11 missing sessions"):
            load_research_bars(db, "sh.600000", day, date(2024, 1, 12))
        frame = load_research_bars(db, "sh.600000", day, date(2024, 1, 12), require_complete=False)
        assert len(frame) == 1 and frame.iloc[0]["close"] == 20
        assert frame.attrs["provenance"]["adjustment"] == "raw"
        legacy = load_research_bars(db, "sh.600000", day, date(2024, 1, 12), source="legacy")
        assert len(legacy) == 12 and legacy.iloc[0]["close"] == 10
        assert legacy.attrs["provenance"]["adjustment"] == "legacy_unknown"


def test_raw_calendar_suspensions_and_snapshot_survive_replay():
    with build_session() as db:
        seed_market_data(db)
        start, end = date(2024, 1, 1), date(2024, 1, 12)
        rows = load_research_bars(db, "sh.600000", start, end, source="legacy").to_dict(orient="records")
        rows.pop(6)
        store_calendar(db, "sh", [{"date": start + timedelta(days=i), "is_open": True}
                                   for i in range(12)], provider="test")
        batch = store_bars(db, "sh.600000", rows, provider="test")
        store_session_statuses(db, [{"stock_code": "sh.600000", "date": date(2024, 1, 7),
                                    "suspended": True}], provider="test")
        result = BacktestExecutor(db).execute("ma_cross", "sh.600000", start, end,
                                             parameters={"short_period": 2, "long_period": 3})
        assert len(result.portfolio_values) == 12
        assert result.execution_metadata["engine_version"] == "daily-next-open-v2"
        assert result.execution_metadata["data_provenance"]["batch_ids"] == [batch.batch_id]
        saved = BacktestExecutor(db).persist(result)
        assert BacktestExecutor(db).replay(saved.id)["reproduced"]


def test_indicators_invalidate_when_an_interior_raw_price_is_revised():
    with build_session() as db:
        seed_market_data(db)
        start, end = date(2024, 1, 1), date(2024, 1, 12)
        rows = load_research_bars(db, "sh.600000", start, end, source="legacy").to_dict(orient="records")
        store_bars(db, "sh.600000", rows, provider="test", observed_at=datetime(2024, 2, 1))
        indicators = IndicatorService()
        original = indicators.get_kline_with_indicators(db, "sh.600000")
        revised = dict(rows[5], close=rows[5]["low"])
        store_bars(db, "sh.600000", [revised], provider="test", observed_at=datetime(2024, 2, 2))
        current = indicators.get_kline_with_indicators(db, "sh.600000")
        assert current[-1]["close"] == original[-1]["close"]
        assert current[-1]["ma10"] != original[-1]["ma10"]
        assert current[-1]["adjustment"] == "raw"


def test_legacy_prices_cannot_be_queried_with_observation_cutoff():
    with build_session() as db:
        seed_market_data(db)
        with pytest.raises(ValueError, match="no observation timestamps"):
            load_research_bars(db, "sh.600000", date(2024, 1, 1), date(2024, 1, 12),
                               observed_before=datetime(2024, 2, 1))
