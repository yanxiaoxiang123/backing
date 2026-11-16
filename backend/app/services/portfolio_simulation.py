"""Shared-cash portfolio execution using prior-close target sizing.

Allocations are explicit ex-ante research inputs. Every order expires after the
next session; neither a suspension nor a cash/volume shortfall queues a later fill.
"""

from dataclasses import asdict
from datetime import date
from math import fsum, isfinite

import numpy as np
import pandas as pd

from app.schemas.portfolio_research import PortfolioResearchRequest
from app.services.backtest_simulation import ExecutionCosts
from app.services.corporate_action_ledger import CorporateActionLedger, EconomicAction


def _frame_rows(frame: pd.DataFrame, sessions: list[date]) -> dict[date, dict]:
    required = {"date", "open", "high", "low", "close", "volume"}
    if frame.empty or not required <= set(frame):
        raise ValueError("Portfolio execution requires dated raw OHLCV")
    dates = pd.to_datetime(frame["date"], errors="raise").dt.date
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Price dates must be unique and increasing")
    if not set(dates) <= set(sessions):
        raise ValueError("Price bar outside execution calendar")
    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values[:, :4] <= 0).any()
            or (values[:, 4] < 0).any()
            or (values[:, 2] > values[:, [0, 3]].min(axis=1)).any()
            or (values[:, 1] < values[:, [0, 3]].max(axis=1)).any()):
        raise ValueError("Invalid OHLCV values")
    return dict(zip(dates, frame.to_dict(orient="records"), strict=True))


def _rebalance_due(day: date, previous: date | None, frequency: str) -> bool:
    if previous is None or frequency == "daily":
        return True
    if frequency == "weekly":
        return day.isocalendar()[:2] != previous.isocalendar()[:2]
    if frequency == "monthly":
        return (day.year, day.month) != (previous.year, previous.month)
    return False


def portfolio_metrics(curve: list[dict], trades: list[dict], initial: float) -> dict:
    equity = np.array([initial, *[row["total_value"] for row in curve]], dtype=float)
    returns = np.diff(equity) / equity[:-1]
    deviation = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    peak = np.maximum.accumulate(equity)
    traded = fsum(row["amount"] for row in trades)
    metrics = {
        "total_return": round((equity[-1] / initial - 1) * 100, 6),
        "annual_return": round(((equity[-1] / initial) ** (252 / len(curve)) - 1) * 100, 6),
        "max_drawdown": round(float(np.max((peak - equity) / peak)) * 100, 6),
        "sharpe_ratio": round(float(np.mean(returns) / deviation * np.sqrt(252)), 6)
        if deviation > 1e-12 else 0.0,
        "volatility": round(deviation * np.sqrt(252) * 100, 6),
        "total_fees": round(fsum(row["fees"] for row in trades), 4),
        "slippage_cost": round(fsum(row["slippage_cost"] for row in trades), 4),
        "gross_turnover": round(traded / float(equity[:-1].mean()), 6),
        "total_trades": len(trades),
    }
    if not all(isfinite(value) for value in metrics.values()):
        raise ValueError("Portfolio performance is outside finite numeric limits")
    return metrics


def simulate_portfolio(
    frames: dict[str, pd.DataFrame], session_dates: list[str], weights: dict[str, float],
    initial_capital: float, *, rebalance: str = "monthly", costs: ExecutionCosts | None = None,
    corporate_actions: dict[str, list[dict]] | None = None, dividend_tax_rate: float = 0,
) -> dict:
    """Size at prior close, execute sells before buys, pro-rate scarce cash.

    Open prices only determine execution/affordability, never target quantities.
    Capacity uses the previous completed session. Daily OHLC lock detection is a
    conservative execution constraint; it is not an exact auction simulator.
    """
    config = PortfolioResearchRequest(
        weights=weights, initial_capital=initial_capital, rebalance=rebalance,
        start_date=session_dates[0] if session_dates else "2000-01-01",
        end_date=session_dates[-1] if session_dates else "2000-01-01",
        dividend_tax_rate=dividend_tax_rate,
    )
    weights = config.weights
    costs = costs or ExecutionCosts()
    sessions = [date.fromisoformat(day) for day in session_dates]
    if len(sessions) < 2 or sessions != sorted(set(sessions)):
        raise ValueError("Portfolio execution needs at least two unique increasing sessions")
    if set(weights) != set(frames):
        raise ValueError("Weights and input securities must match")
    rows = {code: _frame_rows(frame, sessions) for code, frame in frames.items()}
    # A missing row is allowed only when the loader has proved suspension.
    for code, frame in frames.items():
        verified = set(frame.attrs.get("suspended_sessions", []))
        if any(day not in rows[code] and day.isoformat() not in verified for day in sessions):
            raise ValueError(f"Missing unverified session for {code}")
    ledgers = {code: CorporateActionLedger(
        [EconomicAction.from_snapshot(row) for row in (corporate_actions or {}).get(code, [])],
        sessions, dividend_tax_rate) for code in weights}
    positions = dict.fromkeys(weights, 0)
    marks = dict.fromkeys(weights, 0.0)
    previous_volume = dict.fromkeys(weights, 0.0)
    cash = float(initial_capital)
    trades, curve, unfilled = [], [], []
    pending: dict[str, int] = {}
    previous_day = None
    for day in sessions:
        for code, ledger in ledgers.items():
            cash, positions[code], marks[code] = ledger.advance(day, cash, positions[code], marks[code])
        candidates = {"sell": [], "buy": []}
        for code, signed_quantity in pending.items():
            if not signed_quantity:
                continue
            side = "buy" if signed_quantity > 0 else "sell"
            quantity = abs(signed_quantity)
            row = rows[code].get(day)
            if (row is None or row.get("suspended", False) or row["volume"] <= 0
                    or row["high"] <= row["low"]):
                unfilled.append({"date": day.isoformat(), "stock_code": code, "side": side,
                                 "quantity": quantity, "reason": "non_executable_session"})
                continue
            capacity = int(previous_volume[code] * costs.max_participation / costs.lot_size) * costs.lot_size
            filled = min(quantity, capacity, positions[code] if side == "sell" else quantity)
            if filled < quantity:
                unfilled.append({"date": day.isoformat(), "stock_code": code, "side": side,
                                 "quantity": quantity - filled, "reason": "previous_session_capacity"})
            if filled:
                price = round(float(row["open"]) * (1 + costs.slippage_rate * (1 if side == "buy" else -1)), 4)
                if not isfinite(price) or price <= 0:
                    raise ValueError("Execution price must remain finite and positive after rounding")
                candidates[side].append((code, filled, price, float(row["open"])))

        def execute(code: str, quantity: int, price: float, opening: float, side: str) -> None:
            nonlocal cash
            amount = round(quantity * price, 4)
            fees = costs.fees(side, amount)
            cash = round(cash + (amount - fees if side == "sell" else -amount - fees), 4)
            positions[code] += quantity if side == "buy" else -quantity
            trades.append({"date": day.isoformat(), "stock_code": code, "action": side,
                           "quantity": quantity, "price": price, "amount": amount, "fees": fees,
                           "slippage_cost": round(abs(price - opening) * quantity, 4)})

        for code, quantity, price, opening in candidates["sell"]:
            # Refuse a trade whose minimum fee exceeds proceeds plus available cash.
            if quantity * price + cash >= costs.fees("sell", quantity * price):
                execute(code, quantity, price, opening, "sell")
            else:
                unfilled.append({"date": day.isoformat(), "stock_code": code, "side": "sell",
                                 "quantity": quantity, "reason": "fees_exceed_cash_and_proceeds"})
        needed = fsum(quantity * price + costs.fees("buy", quantity * price)
                      for _, quantity, price, _ in candidates["buy"])
        fraction = min(1.0, cash / needed) if needed else 0.0
        for code, requested, price, opening in candidates["buy"]:
            quantity = int(requested * fraction / costs.lot_size) * costs.lot_size
            while quantity and quantity * price + costs.fees("buy", quantity * price) > cash:
                quantity -= costs.lot_size
            if quantity:
                execute(code, quantity, price, opening, "buy")
            if quantity < requested:
                unfilled.append({"date": day.isoformat(), "stock_code": code, "side": "buy",
                                 "quantity": requested - quantity, "reason": "shared_cash"})
        for code, ledger in ledgers.items():
            row = rows[code].get(day)
            if row is not None:
                marks[code] = float(row["close"])
            previous_volume[code] = (float(row["volume"]) if row is not None
                                     and not row.get("suspended", False) else 0.0)
            ledger.capture(day, positions[code], None)
        position_value = fsum((positions[code] + ledgers[code].pending_shares) * marks[code] for code in weights)
        receivable = fsum(ledger.receivable for ledger in ledgers.values())
        total = round(cash + position_value + receivable, 4)
        if not isfinite(total) or total <= 0:
            raise ValueError("Portfolio equity must remain finite and positive")
        curve.append({"date": day.isoformat(), "total_value": total, "cash": cash,
                      "position_value": round(position_value, 4), "receivable": round(receivable, 4),
                      "positions": {code: {"quantity": positions[code], "pending_shares": ledgers[code].pending_shares,
                                           "close": marks[code]} for code in weights}})
        pending = {}
        if _rebalance_due(day, previous_day, rebalance):
            for code, weight in weights.items():
                if not marks[code]:
                    continue
                target = int(total * weight / marks[code] / costs.lot_size) * costs.lot_size
                held = positions[code] + ledgers[code].pending_shares
                delta = target - held
                # Selling a complete odd-lot remainder is permitted; partial reductions use lots.
                if delta < 0:
                    quantity = min(-delta, positions[code])
                    delta = -quantity if target == 0 else -(quantity // costs.lot_size * costs.lot_size)
                pending[code] = delta
        previous_day = day
    return {"initial_capital": initial_capital, "final_capital": curve[-1]["total_value"],
            "trades": trades, "portfolio_values": curve, "unfilled_orders": unfilled,
            "corporate_income": {code: ledger.income for code, ledger in ledgers.items()},
            "metrics": portfolio_metrics(curve, trades, initial_capital),
            "costs": asdict(costs)}


def benchmark_comparison(portfolio: dict, benchmark: dict) -> dict:
    def daily_returns(result):
        equity = np.array([result["initial_capital"], *[row["total_value"] for row in result["portfolio_values"]]])
        return np.diff(equity) / equity[:-1]

    excess = daily_returns(portfolio) - daily_returns(benchmark)
    tracking = float(np.std(excess, ddof=1)) if len(excess) > 1 else 0.0
    return {"benchmark_return": benchmark["metrics"]["total_return"],
            "excess_return": round(portfolio["metrics"]["total_return"] - benchmark["metrics"]["total_return"], 6),
            "tracking_error": round(tracking * np.sqrt(252) * 100, 6),
            "information_ratio": round(float(np.mean(excess) / tracking * np.sqrt(252)), 6)
            if tracking > 1e-12 else 0.0}
