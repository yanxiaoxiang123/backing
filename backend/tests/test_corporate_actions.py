from datetime import date, datetime

import pandas as pd
import pytest

from app.services.backtest_simulation import ExecutionCosts, daily_metrics, simulate_daily
from app.services.corporate_action_ledger import EconomicAction, normalize_dividends
from app.services.corporate_actions import adjusted_history, execution_actions, metadata_snapshot, store_metadata_batch
from app.services.market_data import store_bars, store_calendar
from app.services.backtest_executor import BacktestExecutor
from app.services.strategy.registry import StrategyRegistry
from app.models.market_data import MarketDailyBar, MarketMetadataBatch
from test_backtest_executor import build_session, seed_market_data


def event(**changes):
    row = {"code": "sh.600000", "dividOperateDate": "2024-01-05", "dividRegistDate": "2024-01-04",
           "dividPlanDate": "2024-01-02", "dividPayDate": "2024-01-08", "dividStocksPs": "0",
           "dividReserveToStockPs": "", "dividCashPsBeforeTax": "1"}
    return row | changes


def prices():
    return pd.DataFrame([{"date": date(2024, 1, day), "open": price, "close": price,
                          "high": price + 1, "low": price - 1, "volume": 100000,
                          "signal": signal} for day, price, signal in
                         [(2, 10, 1), (3, 10, 0), (4, 10, 0), (5, 9, -1), (8, 9, 0)]])


ZERO_COSTS = ExecutionCosts(commission_rate=0, minimum_commission=0, sell_tax_rate=0,
                            transfer_rate=0, slippage_rate=0)


def test_cash_dividend_accrues_on_exdate_and_only_becomes_spendable_on_paydate():
    ledger = []
    actions = [action.snapshot() for action in normalize_dividends([event()])]
    trades, value, curve = simulate_daily(prices(), 10000, ZERO_COSTS,
                                         corporate_actions=actions, action_ledger=ledger)
    assert trades[0].quantity == 1000
    assert curve[3].cash == 0 and curve[3].receivable == 1000
    assert curve[3].total_value == 10000
    assert curve[4].cash == 10000 and curve[4].receivable == 0
    assert value == 10000
    assert daily_metrics(trades, 10000, value, curve, corporate_income=ledger).win_rate == 0
    _, taxed, _ = simulate_daily(prices(), 10000, ZERO_COSTS,
                                 corporate_actions=actions, dividend_tax_rate=0.2)
    assert taxed == 9800


def test_buying_on_exdate_does_not_receive_previous_holders_dividend():
    frame = prices()
    frame["signal"] = [0, 0, 1, 0, 0]
    _, value, curve = simulate_daily(frame, 10000, ZERO_COSTS,
                                    corporate_actions=[action.snapshot() for action in normalize_dividends([event()])])
    assert value == 10000
    assert all(point.receivable == 0 for point in curve)


def test_bonus_shares_have_value_but_cannot_be_sold_before_listing():
    frame = prices()
    frame.loc[3:, ["open", "close"]] = 5
    frame.loc[3:, "high"], frame.loc[3:, "low"] = 6, 4
    action = EconomicAction("bonus", date(2024, 1, 4), date(2024, 1, 5),
                            bonus_ratio=1, stock_date=date(2024, 1, 8))
    trades, value, curve = simulate_daily(frame, 10000, ZERO_COSTS, corporate_actions=[action.snapshot()])
    assert curve[3].position == 1000 and curve[3].pending_shares == 1000
    assert curve[3].total_value == value == 10000
    assert trades[-1].quantity == 2000 and trades[-1].date == date(2024, 1, 8)


def test_suspended_exdate_uses_reference_valuation_without_a_price_candle():
    frame = prices().drop(index=3)
    action = normalize_dividends([event()])[0]
    _, value, curve = simulate_daily(frame, 10000, ZERO_COSTS, corporate_actions=[action.snapshot()],
                                     session_dates=["2024-01-02", "2024-01-03", "2024-01-04",
                                                    "2024-01-05", "2024-01-08"])
    assert curve[3].total_value == value == 10000
    assert curve[3].receivable == 1000


def test_incomplete_action_terms_fail_closed():
    with pytest.raises(ValueError, match="payment date"):
        normalize_dividends([event(dividPayDate="")])
    with pytest.raises(ValueError, match="announcement"):
        normalize_dividends([event(dividPlanDate="")])
    action = EconomicAction("fractional", date(2024, 1, 4), date(2024, 1, 5),
                            bonus_ratio=0.0001, stock_date=date(2024, 1, 8))
    with pytest.raises(ValueError, match="Fractional"):
        simulate_daily(prices(), 10000, ZERO_COSTS, corporate_actions=[action.snapshot()])


def test_missing_metadata_is_distinct_from_verified_empty_and_revisions_remove_events():
    with build_session() as db:
        start, end = date(2024, 1, 1), date(2024, 1, 10)
        with pytest.raises(ValueError, match="coverage missing"):
            metadata_snapshot(db, "sh.600000", "dividend", start, end)
        store_metadata_batch(db, "sh.600000", "dividend", [event()], start=start, end=end,
                             provider="test", observed_at=datetime(2024, 2, 1))
        store_metadata_batch(db, "sh.600000", "dividend", [], start=start, end=end,
                             provider="test", observed_at=datetime(2024, 2, 2))
        assert metadata_snapshot(db, "sh.600000", "dividend", start, end)[0] == []
        assert len(metadata_snapshot(db, "sh.600000", "dividend", start, end,
                                      observed_before=datetime(2024, 2, 1))[0]) == 1


def test_metadata_coverage_can_merge_years_without_filling_unknown_days():
    with build_session() as db:
        for year in (2023, 2024):
            store_metadata_batch(db, "sh.600000", "dividend", [], start=date(year, 1, 1),
                                 end=date(year, 12, 31), provider="test")
        assert metadata_snapshot(db, "sh.600000", "dividend", date(2023, 12, 29), date(2024, 1, 2))[0] == []
        with pytest.raises(ValueError, match="coverage missing"):
            metadata_snapshot(db, "sh.600000", "dividend", date(2022, 12, 31), date(2024, 1, 2))


def test_adjusted_charts_use_cumulative_factors_and_do_not_change_raw_prices():
    with build_session() as db:
        seed_market_data(db)
        rows = prices().drop(columns="signal").to_dict(orient="records")
        store_bars(db, "sh.600000", rows, provider="test")
        factor = {"code": "sh.600000", "dividOperateDate": "2024-01-05", "backAdjustFactor": "2"}
        store_metadata_batch(db, "sh.600000", "adjustment_factor", [factor], start=date(1990, 1, 1),
                             end=date(2024, 1, 8), provider="test")
        forward, provenance = adjusted_history(db, "sh.600000", date(2024, 1, 2), date(2024, 1, 8), mode="qfq")
        backward, _ = adjusted_history(db, "sh.600000", date(2024, 1, 2), date(2024, 1, 8), mode="hfq")
        assert list(forward["close"]) == [5, 5, 5, 9, 9]
        assert list(backward["close"]) == [10, 10, 10, 18, 18]
        assert provenance["retrospective"] and not provenance["execution_eligible"]
        with pytest.raises(ValueError, match="coverage missing"):
            execution_actions(db, "sh.600000", date(2024, 1, 2), date(2024, 1, 8))


def test_verified_action_snapshot_replays_after_source_data_is_removed(monkeypatch):
    class FixedStrategy:
        def get_parameters(self):
            return {}

        def get_name(self):
            return "fixed"

        def get_description(self):
            return "Deterministic execution fixture"

        def generate_signals(self, frame):
            frame["signal"] = [1, 0, 0, -1, 0]
            return frame

    monkeypatch.setattr(StrategyRegistry, "get", lambda name: FixedStrategy)
    with build_session() as db:
        seed_market_data(db)
        start, end = date(2024, 1, 2), date(2024, 1, 8)
        store_bars(db, "sh.600000", prices().drop(columns="signal").to_dict(orient="records"), provider="test")
        store_calendar(db, "sh", [{"date": date(2024, 1, day), "is_open": day not in (6, 7)}
                                   for day in range(2, 9)], provider="test")
        store_metadata_batch(db, "sh.600000", "dividend", [event()], start=start, end=end, provider="test")
        store_metadata_batch(db, "sh.600000", "adjustment_factor", [], start=start, end=end, provider="test")
        executor = BacktestExecutor(db)
        result = executor.execute("fixed", "sh.600000", start, end, initial_capital=10000,
                                  corporate_action_mode="verified")
        assert result.execution_metadata["engine_version"] == "daily-next-open-v3"
        assert result.execution_metadata["corporate_income"][0]["cash_income"] > 0
        saved = executor.persist(result)
        db.query(MarketDailyBar).delete()
        db.query(MarketMetadataBatch).delete()
        db.commit()
        assert executor.replay(saved.id)["reproduced"]
        metadata = {**saved.execution_metadata, "signals": [0] * 5}
        saved.execution_metadata = metadata
        db.commit()
        with pytest.raises(ValueError, match="snapshot checksum"):
            executor.replay(saved.id)
