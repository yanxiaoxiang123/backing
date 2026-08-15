"""模拟盘事件重放测试（规格 v2 决策 23；US-3.5）。

从 append-only 事件重建账户现金与持仓，与写入时状态一致。
"""

import pytest

from app.agent_runtime.paper.replay import replay_account


def test_replay_empty_account():
    state = replay_account(initial_cash=1_000_000.0, cash_events=[], fills=[])
    assert state["cash"] == 1_000_000.0
    assert state["positions"] == {}


def test_replay_buy_then_sell():
    # 初始资金由 initial_cash 注入，事件不含入金
    cash_events = [
        # 买入 1000 股 @10.5 = 10500 + 佣金5 + 过户0.105 → 净 -10505.11
        {"event_type": "buy", "amount": -10505.11, "order_id": "o1"},
        # 卖出 400 股 @11.0 = 4400 - 佣金5 - 印花2.2 - 过户0.044 → 净 +4392.76
        {"event_type": "sell", "amount": 4392.76, "order_id": "o2"},
    ]
    fills = [
        {
            "stock_code": "sh.600000",
            "side": "buy",
            "price": 10.5,
            "quantity": 1000,
            "commission": 5.0,
            "stamp_tax": 0.0,
            "transfer_fee": 0.105,
        },
        {
            "stock_code": "sh.600000",
            "side": "sell",
            "price": 11.0,
            "quantity": 400,
            "commission": 5.0,
            "stamp_tax": 2.2,
            "transfer_fee": 0.044,
        },
    ]
    state = replay_account(
        initial_cash=1_000_000.0, cash_events=cash_events, fills=fills
    )
    assert state["cash"] == pytest.approx(1_000_000.0 - 10505.11 + 4392.76, abs=1e-4)
    pos = state["positions"]["sh.600000"]
    assert pos["quantity"] == 600
    assert pos["avg_cost"] == pytest.approx(10.5, abs=1e-4)  # 移动平均成本不变


def test_replay_full_liquidation_removes_position():
    cash_events = [
        {"event_type": "buy", "amount": -10505.11, "order_id": "o1"},
        {"event_type": "sell", "amount": 10489.645, "order_id": "o2"},
    ]
    fills = [
        {
            "stock_code": "sz.000001",
            "side": "buy",
            "price": 10.5,
            "quantity": 1000,
            "commission": 5.0,
            "stamp_tax": 0.0,
            "transfer_fee": 0.105,
        },
        {
            "stock_code": "sz.000001",
            "side": "sell",
            "price": 10.5,
            "quantity": 1000,
            "commission": 5.0,
            "stamp_tax": 5.25,
            "transfer_fee": 0.105,
        },
    ]
    state = replay_account(
        initial_cash=1_000_000.0, cash_events=cash_events, fills=fills
    )
    assert "sz.000001" not in state["positions"]
    # 卖出净额 = 10500 - 5 - 5.25 - 0.105 = 10489.645
    assert state["cash"] == pytest.approx(1_000_000.0 - 10505.11 + 10489.645, abs=1e-3)
