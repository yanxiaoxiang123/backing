"""Signal-generation helpers shared by the strategy API.

Extracted from ``app/api/strategies.py`` so the API layer stays thin and the
pure pandas logic is unit-testable without FastAPI dependencies.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models.models import DailyKline
from app.services.strategy.factors import TechnicalFactors


def get_kline_data(
    db: Session, stock_code: str, start_date: date, end_date: date
) -> pd.DataFrame:
    """Fetch kline data from database."""
    klines = (
        db.query(DailyKline)
        .filter(
            DailyKline.stock_code == stock_code,
            DailyKline.date >= start_date,
            DailyKline.date <= end_date,
        )
        .order_by(DailyKline.date)
        .all()
    )

    if not klines:
        return pd.DataFrame()

    data = [
        {
            "date": k.date,
            "open": float(k.open),
            "high": float(k.high),
            "low": float(k.low),
            "close": float(k.close),
            "volume": float(k.volume),
        }
        for k in klines
    ]

    return pd.DataFrame(data)


def generate_ma_cross_signals(df: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    """Generate signals using MA cross strategy."""
    df = df.copy()

    short_period = params.get("short_period", 5)
    long_period = params.get("long_period", 20)

    df["ma_short"] = TechnicalFactors.SMA(df["close"], short_period)
    df["ma_long"] = TechnicalFactors.SMA(df["close"], long_period)

    # Generate signals
    df["signal"] = 0
    df.loc[df["ma_short"] > df["ma_long"], "signal"] = 1
    df.loc[df["ma_short"] < df["ma_long"], "signal"] = -1

    return df


def compute_signal_stats(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute rolling performance statistics from chronological signal data.

    Processes buy (signal=1) / sell (signal=-1) pairs to derive:
    win_rate, avg_holding_days, profit_ratio, etc.
    """
    if len(data) < 2:
        return {}

    entry_price: float | None = None
    entry_date = None
    holding_days: list[int] = []
    returns: list[float] = []
    wins = 0
    losses = 0
    max_win = 0.0
    max_loss = 0.0
    buy_count = 0
    sell_count = 0
    streak = 0
    max_streak_win = 0
    max_streak_loss = 0

    for point in data:
        signal = point.get("signal", 0)
        price = float(point.get("close", 0))
        dt = point.get("date")

        if signal == 1:
            buy_count += 1
            if entry_price is not None:
                # Consecutive buy signals: close previous hypothetical trade flat
                entry_price = price
                entry_date = dt
            else:
                entry_price = price
                entry_date = dt

        elif signal == -1 and entry_price is not None:
            sell_count += 1
            ret = (price - entry_price) / entry_price
            returns.append(ret)

            if entry_date and dt:
                days = (dt - entry_date).days if hasattr(dt, "__sub__") else 0
                holding_days.append(days)

            if ret > 0:
                wins += 1
                max_win = max(max_win, ret)
                streak = streak + 1 if streak >= 0 else 1
            else:
                losses += 1
                max_loss = min(max_loss, ret)
                streak = streak - 1 if streak <= 0 else -1

            max_streak_win = (
                max(max_streak_win, streak) if streak > 0 else max_streak_win
            )
            max_streak_loss = (
                min(max_streak_loss, streak) if streak < 0 else max_streak_loss
            )

            entry_price = None
            entry_date = None

    total_trades = wins + losses
    if total_trades == 0:
        return {}

    win_rate = wins / total_trades * 100
    avg_ret = sum(returns) / len(returns) if returns else 0.0
    sum_gains = sum(r for r in returns if r > 0) or 0.0
    sum_losses = abs(sum(r for r in returns if r < 0)) or 0.0

    return {
        "total_buy_signals": buy_count,
        "total_sell_signals": sell_count,
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "avg_holding_days": round(sum(holding_days) / len(holding_days), 1)
        if holding_days
        else 0.0,
        "avg_return_per_trade": round(avg_ret * 100, 2),
        "profit_ratio": round(sum_gains / sum_losses, 2) if sum_losses > 0 else 0.0,
        "max_win": round(max_win * 100, 2),
        "max_loss": round(max_loss * 100, 2),
        "consecutive_wins": max_streak_win,
        "consecutive_losses": abs(max_streak_loss),
    }
