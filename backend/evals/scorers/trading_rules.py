"""A 股成交规则检查：仅对结果中可检查的输入（orders/positions）生效。

规则：T+1（同一交易日买入+卖出违规）、一手 100 股、涨跌停无法成交
（结果声明 limit_up/limit_down 时禁止按涨停价买入/跌停价卖出建议）。
"""

from typing import Any

Check = tuple[bool, str]


def trading_rules_check(case: dict[str, Any], result: dict[str, Any]) -> Check:
    """返回 (passed, detail)；无可检查输入时 passed=True 并注明跳过。"""
    orders = result.get("orders") or []
    positions = result.get("positions") or []
    if not orders and not positions:
        return True, "无 orders/positions 输入，跳过"

    violations: list[str] = []

    # T+1：同一 (code, trade_date) 不可同时 buy 与 sell
    day_actions: dict[tuple[str, str], set[str]] = {}
    for order in orders:
        code = str(order.get("code", ""))
        trade_date = str(order.get("trade_date", ""))
        action = str(order.get("action", ""))
        if not code or not trade_date or action not in {"buy", "sell"}:
            continue
        day_actions.setdefault((code, trade_date), set()).add(action)
    for (code, trade_date), actions in day_actions.items():
        if len(actions) > 1:
            violations.append(f"T+1 违规：{code} 在 {trade_date} 同日买入又卖出")

    # 一手 100 股
    for order in orders:
        shares = order.get("shares")
        if isinstance(shares, (int, float)) and shares > 0 and shares % 100 != 0:
            violations.append(f"手数违规：{order.get('code')} 委托 {shares} 股非 100 的整数倍")

    # 涨跌停无法成交
    risk_markers = set(case.get("risk_markers") or [])
    if "limit_up" in risk_markers:
        for order in orders:
            if order.get("action") == "buy":
                violations.append("涨跌停 case：涨停当日无法按买价成交")
    if "limit_down" in risk_markers:
        for order in orders:
            if order.get("action") == "sell":
                violations.append("涨跌停 case：跌停当日无法按卖价成交")

    if violations:
        return False, "; ".join(violations)
    return True, "A 股成交规则检查通过"
