"""模拟盘确定性撮合规则测试（规格 v2 决策 21-22；US-3.1/3.2）。

纯函数：T+1、整手、零股清仓、一字板不成交、限价约束、费用明细、
一次性撮合窗口（TTL）。
"""

import pytest

from app.agent_runtime.paper.rules import (
    Bar,
    available_to_sell,
    compute_fees,
    match_order,
    price_limit_pct,
    validate_order,
    window_expired,
)


def _bar(open_, high, low, close, date="2026-08-14"):
    return Bar(date=date, open=open_, high=high, low=low, close=close)


class TestPriceLimit:
    def test_main_board_10(self):
        assert price_limit_pct("sh.600000") == 0.10
        assert price_limit_pct("sz.000001") == 0.10

    def test_growth_board_20(self):
        assert price_limit_pct("sz.300750") == 0.20
        assert price_limit_pct("sh.688981") == 0.20

    def test_st_5(self):
        assert price_limit_pct("sh.600000", stock_name="ST海航") == 0.05
        assert price_limit_pct("sz.300750", stock_name="*ST某某") == 0.05


class TestFees:
    def test_buy_fees(self):
        fees = compute_fees("buy", 10_000.0)
        assert fees.commission == 5.0  # 最低佣金 5 元
        assert fees.stamp_tax == 0.0  # 印花税仅卖出
        assert fees.transfer_fee == pytest.approx(0.1, abs=1e-6)  # 0.001%

    def test_sell_fees(self):
        fees = compute_fees("sell", 10_000.0)
        assert fees.commission == 5.0
        assert fees.stamp_tax == 5.0  # 0.05%
        assert fees.transfer_fee == pytest.approx(0.1, abs=1e-6)
        assert fees.total == pytest.approx(10.1, abs=1e-6)

    def test_commission_rate_above_min(self):
        fees = compute_fees("buy", 1_000_000.0)
        assert fees.commission == pytest.approx(250.0, abs=1e-6)  # 0.025%


class TestValidateOrder:
    def test_buy_must_be_lot_multiple(self):
        assert validate_order("buy", 150) is not None
        assert validate_order("buy", 200) is None

    def test_sell_positive(self):
        assert validate_order("sell", 0) is not None
        assert validate_order("sell", 1) is None  # 零股清仓允许


class TestTPlusOne:
    def test_available_excludes_bought_today(self):
        assert available_to_sell(1000, 400) == 600
        assert available_to_sell(1000, 0) == 1000
        assert available_to_sell(0, 0) == 0


class TestMatchOrder:
    def test_buy_fills_at_open(self):
        decision = match_order(
            side="buy",
            quantity=100,
            limit_price=None,
            bar=_bar(open_=10.5, high=10.8, low=10.4, close=10.6),
            prev_close=10.0,
            limit_pct=0.10,
        )
        assert decision.fill is True
        assert decision.fill_price == 10.5
        assert decision.fees is not None

    def test_buy_rejected_above_limit_price(self):
        decision = match_order(
            side="buy",
            quantity=100,
            limit_price=10.2,
            bar=_bar(open_=10.5, high=10.8, low=10.4, close=10.6),
            prev_close=10.0,
            limit_pct=0.10,
        )
        assert decision.fill is False
        assert "限价" in decision.reason

    def test_sell_rejected_below_limit_price(self):
        decision = match_order(
            side="sell",
            quantity=100,
            limit_price=10.5,
            bar=_bar(open_=10.2, high=10.6, low=10.1, close=10.4),
            prev_close=10.0,
            limit_pct=0.10,
        )
        assert decision.fill is False
        assert "限价" in decision.reason

    def test_buy_no_fill_at_one_word_limit_up(self):
        # 一字涨停：开=高=低=涨停价(10.0*1.1=11.0)
        decision = match_order(
            side="buy",
            quantity=100,
            limit_price=None,
            bar=_bar(open_=11.0, high=11.0, low=11.0, close=11.0),
            prev_close=10.0,
            limit_pct=0.10,
        )
        assert decision.fill is False
        assert "一字涨停" in decision.reason

    def test_sell_no_fill_at_one_word_limit_down(self):
        decision = match_order(
            side="sell",
            quantity=100,
            limit_price=None,
            bar=_bar(open_=9.0, high=9.0, low=9.0, close=9.0),
            prev_close=10.0,
            limit_pct=0.10,
        )
        assert decision.fill is False
        assert "一字跌停" in decision.reason

    def test_sell_fills_at_open_within_limit(self):
        decision = match_order(
            side="sell",
            quantity=200,
            limit_price=None,
            bar=_bar(open_=10.5, high=10.6, low=10.3, close=10.4),
            prev_close=10.0,
            limit_pct=0.10,
        )
        assert decision.fill is True
        assert decision.fill_price == 10.5
        assert decision.fees.stamp_tax > 0


class TestWindowTtl:
    def test_expired_when_trade_date_not_after_approval(self):
        assert window_expired("2026-08-14", "2026-08-14") is True
        assert window_expired("2026-08-14", "2026-08-13") is True

    def test_valid_when_next_day(self):
        assert window_expired("2026-08-14", "2026-08-17") is False
