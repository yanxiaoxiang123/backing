"""Shared daily-bar execution. All rates are configurable research assumptions."""

from dataclasses import dataclass
from datetime import date
from math import isfinite

import numpy as np
import pandas as pd

from app.services.corporate_action_ledger import CorporateActionLedger, EconomicAction


@dataclass(frozen=True)
class ExecutionCosts:
    commission_rate: float = 0.00025
    minimum_commission: float = 5.0
    sell_tax_rate: float = 0.0005
    transfer_rate: float = 0.00001
    slippage_rate: float = 0.0001
    # Use the PREVIOUS completed bar, never today's eventual full-day volume.
    max_participation: float = 0.10
    lot_size: int = 100

    def __post_init__(self) -> None:
        rates = (self.commission_rate, self.minimum_commission, self.sell_tax_rate,
                 self.transfer_rate, self.slippage_rate)
        if any(not isfinite(x) or x < 0 for x in rates):
            raise ValueError("Costs must be finite and nonnegative")
        if not 0 < self.max_participation <= 1 or self.lot_size < 1:
            raise ValueError("Invalid participation or lot size")
        if self.slippage_rate >= 1:
            raise ValueError("Slippage must be below one")

    def fees(self, side: str, amount: float) -> float:
        return round(max(self.minimum_commission, amount * self.commission_rate)
                     + amount * self.transfer_rate
                     + (amount * self.sell_tax_rate if side == "sell" else 0), 4)


@dataclass
class TradeRecord:
    date: date
    action: str
    price: float
    quantity: int
    amount: float
    fees: float = 0.0


@dataclass
class PortfolioValue:
    date: date
    total_value: float
    cash: float
    position_value: float
    position: int
    receivable: float = 0.0
    pending_shares: int = 0


@dataclass
class BacktestMetricsSummary:
    sharpe_ratio: float
    total_return: float
    annual_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int


def simulate_daily(
    data: pd.DataFrame, initial_capital: float, costs: ExecutionCosts | None = None,
    *, session_dates: list[str] | None = None,
    corporate_actions: list[dict] | None = None, dividend_tax_rate: float = 0,
    action_ledger: list[dict] | None = None,
) -> tuple[list[TradeRecord], float, list[PortfolioValue]]:
    """Prior close signals execute once at next bar open; residuals expire.

    Locked OHLC bars are conservatively non-executable without historical limit
    prices. This engine does not infer exchange limit rules from adjusted prices.
    Input must have positive OHLC, finite volume and strictly increasing dates.
    """
    costs = costs or ExecutionCosts()
    if not isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial_capital must be finite and positive")
    if data.empty or not {"date", "open", "high", "low", "close", "volume", "signal"} <= set(data):
        raise ValueError("Daily execution requires dated OHLCV and signal data")
    dates = pd.to_datetime(data["date"], errors="raise").dt.date
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Bar dates must be unique and increasing")
    if dates.isna().any():
        raise ValueError("Bar dates must not be missing")
    if not data["signal"].dropna().isin([-1, 0, 1]).all():
        raise ValueError("Signals must be -1, 0 or 1")
    values = data[["open", "high", "low", "close", "volume"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError("Invalid OHLCV values")
    if ((values[:, 2] > values[:, [0, 3]].min(axis=1)).any()
            or (values[:, 1] < values[:, [0, 3]].max(axis=1)).any()):
        raise ValueError("Inconsistent OHLC range")
    cash, position = float(initial_capital), 0
    trades, curve = [], []
    previous_signal, previous_volume = 0, 0.0
    bought_on = None
    rows = dict(zip(dates, (row for _, row in data.iterrows()), strict=True))
    sessions = pd.to_datetime(session_dates).date if session_dates is not None else dates
    if (len(sessions) == 0 or pd.isna(sessions).any()
            or list(sessions) != sorted(set(sessions)) or not set(dates) <= set(sessions)):
        raise ValueError("Execution calendar must be increasing, unique and include every bar")
    last_close = 0.0
    ledger = CorporateActionLedger([EconomicAction.from_snapshot(row) for row in (corporate_actions or [])],
                                   list(sessions), dividend_tax_rate)
    for bar_date in sessions:
        cash, position, last_close = ledger.advance(bar_date, cash, position, last_close)
        row = rows.get(bar_date)
        if row is None:
            # A verified suspended session has a valuation mark, not an invented
            # price candle. Its pending order expires without execution.
            position_value = (position + ledger.pending_shares) * last_close
            curve.append(PortfolioValue(bar_date, cash + position_value + ledger.receivable, cash,
                                        position_value, position, ledger.receivable, ledger.pending_shares))
            ledger.capture(bar_date, position, bought_on)
            previous_signal, previous_volume = 0, 0.0
            continue
        opening, closing = float(row["open"]), float(row["close"])
        # A zero-volume session cannot fill. Locked bars fail closed in both directions.
        executable = (not bool(row.get("suspended", False)) and float(row["volume"]) > 0
                      and float(row["high"]) > float(row["low"]))
        capacity = int(previous_volume * costs.max_participation / costs.lot_size) * costs.lot_size
        if executable and previous_signal == 1 and position == 0 and ledger.pending_shares == 0:
            price = round(opening * (1 + costs.slippage_rate), 4)
            quantity = min(int(cash / price / costs.lot_size) * costs.lot_size, capacity)
            while quantity > 0 and quantity * price + costs.fees("buy", quantity * price) > cash:
                quantity -= costs.lot_size
            if quantity > 0:
                amount = round(quantity * price, 4)
                fees = costs.fees("buy", amount)
                cash = round(cash - amount - fees, 4)
                position, bought_on = quantity, bar_date
                trades.append(TradeRecord(bar_date, "buy", price, quantity, amount, fees))
        elif executable and previous_signal == -1 and position > 0 and bought_on < bar_date:
            # Exit is all-or-nothing in this first daily execution model.
            if position <= capacity:
                price = round(opening * (1 - costs.slippage_rate), 4)
                amount = round(position * price, 4)
                fees = costs.fees("sell", amount)
                cash = round(cash + amount - fees, 4)
                trades.append(TradeRecord(bar_date, "sell", price, position, amount, fees))
                position = 0
        position_value = (position + ledger.pending_shares) * closing
        curve.append(PortfolioValue(bar_date, cash + position_value + ledger.receivable, cash,
                                    position_value, position, ledger.receivable, ledger.pending_shares))
        ledger.capture(bar_date, position, bought_on)
        signal = row["signal"]
        suspended = bool(row.get("suspended", False))
        previous_signal = 0 if suspended or pd.isna(signal) else int(signal)
        previous_volume = 0.0 if suspended else float(row["volume"])
        last_close = closing
    if action_ledger is not None:
        action_ledger.extend(ledger.income)
    return trades, curve[-1].total_value, curve


def daily_metrics(
    trades: list[TradeRecord], initial_capital: float, final_capital: float,
    curve: list[PortfolioValue],
    *, corporate_income: list[dict] | None = None,
) -> BacktestMetricsSummary:
    equity = np.array([initial_capital, *[point.total_value for point in curve]], dtype=float)
    returns = np.diff(equity) / equity[:-1]
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 1e-12 else 0.0
    peak = np.maximum.accumulate(equity)
    drawdown = float(np.max((peak - equity) / peak)) * 100
    profits, entry = [], None
    proceeds, sold = 0.0, 0
    for trade in trades:
        if trade.action == "buy":
            entry = trade
            proceeds, sold = 0.0, 0
        elif entry is not None:
            proceeds += trade.amount - trade.fees
            sold += trade.quantity
            distributions = [row for row in (corporate_income or [])
                             if row["entry_date"] == entry.date.isoformat()]
            target = entry.quantity + sum(row["bonus_shares"] for row in distributions)
            if sold >= target:
                income = sum(row["cash_income"] for row in distributions)
                profits.append(proceeds + income - entry.amount - entry.fees)
                entry = None
    wins = sum(profit > 0 for profit in profits)
    loss = -sum(profit for profit in profits if profit < 0)
    gross = sum(profit for profit in profits if profit > 0)
    return BacktestMetricsSummary(
        sharpe_ratio=round(sharpe, 4),
        total_return=round((final_capital / initial_capital - 1) * 100, 4),
        annual_return=round(((final_capital / initial_capital) ** (252 / max(len(curve), 1)) - 1) * 100, 4),
        max_drawdown=round(drawdown, 4),
        win_rate=round(wins / len(profits) * 100, 4) if profits else 0.0,
        profit_factor=round(gross / loss, 4) if loss else 0.0,
        total_trades=len(trades),
    )
