from datetime import date, timedelta

import pandas as pd
import pytest

from app.services.backtest_simulation import ExecutionCosts, daily_metrics, simulate_daily


def bars(signals, opens=None, volumes=None):
    opens = opens or [10.0] * len(signals)
    return pd.DataFrame([
        {"date": date(2024, 1, 2) + timedelta(days=i), "open": price,
         "high": price + 1, "low": price - 1, "close": price,
         "volume": (volumes or [100000] * len(signals))[i], "signal": signal}
        for i, (signal, price) in enumerate(zip(signals, opens))
    ])


def test_signals_execute_at_following_open_and_last_signal_expires():
    trades, _, _ = simulate_daily(bars([1, -1, 1], [10, 12, 11]), 10000)
    assert [trade.date for trade in trades] == [date(2024, 1, 3), date(2024, 1, 4)]
    assert trades[0].price == pytest.approx(12 * 1.0001)
    assert trades[1].price == pytest.approx(11 * 0.9999)


def test_fees_and_slippage_reduce_flat_market_equity_and_never_overdraw():
    trades, value, curve = simulate_daily(bars([1, -1, 0]), 10000)
    assert value < 10000
    assert all(point.cash >= 0 for point in curve)
    assert value == pytest.approx(10000 + trades[1].amount - trades[0].amount
                                  - sum(trade.fees for trade in trades))
    assert daily_metrics(trades, 10000, value, curve).win_rate == 0


def test_capacity_uses_only_previous_volume():
    trades, _, _ = simulate_daily(bars([1, 0], volumes=[1000, 10000000]), 1000000)
    assert trades[0].quantity == 100


@pytest.mark.parametrize("locked", [True, False])
def test_locked_or_suspended_bar_cannot_fill(locked):
    frame = bars([1, 0])
    if locked:
        frame.loc[1, ["open", "high", "low", "close"]] = 10
    else:
        frame.loc[1, "volume"] = 0
    assert simulate_daily(frame, 10000)[0] == []


def test_future_signal_changes_cannot_change_past_positions():
    frame = bars([1, 0, -1, 0, 1])
    original = simulate_daily(frame, 10000)[2]
    frame.loc[3:, "signal"] = -1
    changed = simulate_daily(frame, 10000)[2]
    assert original[:4] == changed[:4]


def test_duplicate_dates_and_nan_prices_fail_instead_of_fabricating_trades():
    frame = bars([1, 0])
    frame.loc[1, "date"] = frame.loc[0, "date"]
    with pytest.raises(ValueError, match="unique"):
        simulate_daily(frame, 10000)
    frame = bars([1, 0])
    frame.loc[1, "open"] = float("nan")
    with pytest.raises(ValueError, match="OHLCV"):
        simulate_daily(frame, 10000)


def test_daily_equity_sharpe_counts_idle_sessions():
    frame = bars([1, 0, -1, 0], [10, 10, 12, 11])
    trades, value, curve = simulate_daily(frame, 10000)
    expected = pd.Series([10000, *[point.total_value for point in curve]]).pct_change().dropna()
    assert daily_metrics(trades, 10000, value, curve).sharpe_ratio == pytest.approx(
        expected.mean() / expected.std() * 252 ** 0.5, abs=0.0001)


def test_cost_configuration_rejects_nan():
    with pytest.raises(ValueError):
        ExecutionCosts(commission_rate=float("nan"))


def test_unexecuted_last_day_signal_is_not_forced_into_a_trade():
    assert simulate_daily(bars([0, 1]), 10000)[0] == []


def test_suspended_calendar_session_expires_pending_order_and_marks_equity():
    frame = bars([1, 0, 0])
    frame.loc[1:, "date"] = [date(2024, 1, 4), date(2024, 1, 5)]
    trades, value, curve = simulate_daily(frame, 10000, session_dates=[
        "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    assert trades == []
    assert len(curve) == 4 and value == 10000
    held = bars([1, 0, 0])
    held.loc[2, "date"] = date(2024, 1, 5)
    _, _, held_curve = simulate_daily(held, 10000, session_dates=[
        "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    assert held_curve[2].position > 0
    assert held_curve[2].total_value == held_curve[1].total_value


def test_execution_calendar_cannot_omit_a_price_bar():
    with pytest.raises(ValueError, match="include every bar"):
        simulate_daily(bars([1, 0]), 10000, session_dates=["2024-01-02"])
