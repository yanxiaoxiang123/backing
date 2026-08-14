"""信号统计（compute_signal_stats，从 api/strategies.py 拆分而来）测试。"""

from datetime import date

import pytest

from app.services.strategy.signals import compute_signal_stats


def _point(day: int, signal: int, close: float) -> dict:
    return {"date": date(2024, 1, day), "signal": signal, "close": close}


class TestComputeSignalStats:
    def test_less_than_two_points_returns_empty(self):
        assert compute_signal_stats([_point(1, 1, 10.0)]) == {}

    def test_no_closed_trades_returns_empty(self):
        data = [
            _point(1, 1, 10.0),
            _point(2, 1, 11.0),  # 连续买入无卖出
        ]
        assert compute_signal_stats(data) == {}

    def test_buy_sell_pair_produces_stats(self):
        data = [
            _point(1, 1, 10.0),
            _point(2, 0, 10.5),
            _point(3, -1, 11.0),  # +10%
        ]
        stats = compute_signal_stats(data)
        assert stats["total_buy_signals"] == 1
        assert stats["total_sell_signals"] == 1
        assert stats["total_trades"] == 1
        assert stats["win_rate"] == 100.0
        assert stats["avg_return_per_trade"] == pytest.approx(10.0)
        assert stats["max_win"] == pytest.approx(10.0)

    def test_mixed_wins_and_losses(self):
        data = [
            _point(1, 1, 10.0),
            _point(2, -1, 11.0),  # +10%
            _point(3, 1, 12.0),
            _point(4, -1, 9.0),  # -25%
        ]
        stats = compute_signal_stats(data)
        assert stats["total_trades"] == 2
        assert stats["win_rate"] == 50.0
        assert stats["consecutive_wins"] == 1
        assert stats["consecutive_losses"] == 1
        assert stats["max_loss"] == pytest.approx(-25.0)
