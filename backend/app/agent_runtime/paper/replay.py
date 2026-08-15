"""模拟盘事件重放（规格 v2 决策 23；US-3.5）。

从 append-only 事件（资金流水 + 成交）重建账户状态：现金、持仓
（数量/移动平均成本）。纯函数，无 IO；用于审计与一致性校验。
"""

from __future__ import annotations

from typing import Any


def replay_account(
    initial_cash: float,
    cash_events: list[dict[str, Any]],
    fills: list[dict[str, Any]],
) -> dict[str, Any]:
    """重建 {cash, positions: {stock_code: {quantity, avg_cost}}}。

    - initial_cash：账户初始资金（初始入金不写入 cash_events，避免重复计入）
    - cash_events: [{"event_type", "amount"}]，amount 为净现金变动
      （买入为负、卖出为正、费用单独或并入交易净额）
    - fills: [{"stock_code", "side", "price", "quantity"}]，用于重建持仓
    """
    cash = initial_cash
    for ev in cash_events:
        cash = round(cash + float(ev["amount"]), 4)

    positions: dict[str, dict[str, float]] = {}
    for fill in fills:
        code = fill["stock_code"]
        qty = int(fill["quantity"])
        if qty <= 0:
            continue
        pos = positions.setdefault(code, {"quantity": 0, "avg_cost": 0.0})
        if fill["side"] == "buy":
            total_cost = pos["avg_cost"] * pos["quantity"] + float(fill["price"]) * qty
            pos["quantity"] += qty
            pos["avg_cost"] = (
                round(total_cost / pos["quantity"], 4) if pos["quantity"] else 0.0
            )
        else:  # sell
            pos["quantity"] -= qty
            if pos["quantity"] <= 0:
                positions.pop(code, None)

    return {"cash": cash, "positions": positions}
