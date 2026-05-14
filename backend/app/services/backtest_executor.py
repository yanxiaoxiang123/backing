from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.models import BacktestResult, BacktestTrade, DailyKline, Stock, Strategy
from app.services.strategy.registry import StrategyRegistry


@dataclass
class TradeRecord:
    date: date
    action: str
    price: float
    quantity: int
    amount: float


@dataclass
class BacktestMetricsSummary:
    sharpe_ratio: float
    total_return: float
    annual_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int


@dataclass
class PortfolioValue:
    date: date
    total_value: float
    cash: float
    position_value: float
    position: int


@dataclass
class BacktestExecutionResult:
    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    trades: List[TradeRecord]
    metrics: BacktestMetricsSummary
    portfolio_values: List[PortfolioValue]

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            "success": True,
            "strategy_name": self.strategy_name,
            "stock_code": self.stock_code,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": round(self.initial_capital, 2),
            "final_capital": round(self.final_capital, 2),
            "trades": [asdict(trade) for trade in self.trades],
            "metrics": asdict(self.metrics),
            "portfolio_values": [
                {
                    "date": pv.date.isoformat() if hasattr(pv.date, "isoformat") else str(pv.date),
                    "total_value": round(pv.total_value, 2),
                    "cash": round(pv.cash, 2),
                    "position_value": round(pv.position_value, 2),
                    "position": pv.position,
                }
                for pv in self.portfolio_values
            ],
        }


class BacktestExecutor:
    def __init__(self, db: Session):
        self.db = db

    def get_stock(self, stock_code: str) -> Optional[Stock]:
        return self.db.query(Stock).filter(Stock.code == stock_code).first()

    def get_kline_data(
        self, stock_code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        klines = (
            self.db.query(DailyKline)
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

        return pd.DataFrame(
            [
                {
                    "date": k.date,
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "volume": k.volume,
                    "amount": k.amount or 0.0,
                }
                for k in klines
            ]
        )

    def execute(
        self,
        strategy_name: str,
        stock_code: str,
        start_date: date,
        end_date: date,
        initial_capital: float = 100000,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> BacktestExecutionResult:
        stock = self.get_stock(stock_code)
        if not stock:
            raise ValueError(f"Stock '{stock_code}' not found")

        strategy_class = StrategyRegistry.get(strategy_name)
        if strategy_class is None:
            raise ValueError(
                f"Strategy '{strategy_name}' not found. "
                f"Available: {StrategyRegistry.list_strategies()}"
            )

        df = self.get_kline_data(stock_code, start_date, end_date)
        if df.empty:
            raise ValueError(
                f"No kline data found for {stock_code} in the specified date range"
            )

        strategy = strategy_class(**(parameters or {}))
        signal_data = strategy.generate_signals(df.copy())
        if "signal" not in signal_data.columns:
            raise ValueError("Strategy must generate a 'signal' column")

        trades, final_capital, portfolio_values = self._simulate_trades(signal_data, initial_capital)
        metrics = self._calculate_metrics(
            trades=trades,
            initial_capital=initial_capital,
            final_capital=final_capital,
            start_date=start_date,
            end_date=end_date,
        )

        return BacktestExecutionResult(
            strategy_name=strategy_name,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=round(final_capital, 2),
            trades=trades,
            metrics=metrics,
            portfolio_values=portfolio_values,
        )

    def persist(self, execution: BacktestExecutionResult) -> BacktestResult:
        strategy = self._ensure_strategy_record(execution.strategy_name)
        result = BacktestResult(
            strategy_id=strategy.id,
            stock_code=execution.stock_code,
            start_date=execution.start_date,
            end_date=execution.end_date,
            initial_capital=execution.initial_capital,
            final_capital=execution.final_capital,
            total_return=execution.metrics.total_return,
            annual_return=execution.metrics.annual_return,
            sharpe_ratio=execution.metrics.sharpe_ratio,
            max_drawdown=execution.metrics.max_drawdown,
            win_rate=execution.metrics.win_rate,
            total_trades=execution.metrics.total_trades,
        )
        self.db.add(result)
        self.db.flush()

        for trade in execution.trades:
            self.db.add(
                BacktestTrade(
                    backtest_result_id=result.id,
                    stock_code=execution.stock_code,
                    trade_date=trade.date,
                    action=trade.action,
                    price=trade.price,
                    quantity=trade.quantity,
                    amount=trade.amount,
                )
            )

        self.db.commit()
        self.db.refresh(result)
        return result

    def _ensure_strategy_record(self, strategy_name: str) -> Strategy:
        strategy = (
            self.db.query(Strategy)
            .filter(Strategy.strategy_type == strategy_name)
            .first()
        )
        if strategy:
            return strategy

        strategy_class = StrategyRegistry.get(strategy_name)
        if strategy_class is None:
            raise ValueError(f"Strategy '{strategy_name}' not found")

        strategy_instance = strategy_class()
        strategy = Strategy(
            name=strategy_instance.get_name(),
            description=strategy_instance.get_description(),
            strategy_type=strategy_name,
            parameters="{}",
        )
        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)
        return strategy

    def _simulate_trades(
        self, signal_data: pd.DataFrame, initial_capital: float
    ) -> tuple[List[TradeRecord], float, List[PortfolioValue]]:
        capital = initial_capital
        position = 0
        trades: List[TradeRecord] = []
        portfolio_values: List[PortfolioValue] = []

        for idx, row in signal_data.iterrows():
            trade_date = row.get("date", idx)
            if hasattr(trade_date, "date"):
                trade_date = trade_date.date()

            price = float(row["close"])
            signal = row.get("signal", 0)

            # Record portfolio value BEFORE processing the signal
            position_value = position * price
            total_value = capital + position_value
            portfolio_values.append(
                PortfolioValue(
                    date=trade_date,
                    total_value=total_value,
                    cash=capital,
                    position_value=position_value,
                    position=position,
                )
            )

            if pd.isna(signal) or signal == 0:
                continue

            if signal == 1 and position == 0:
                shares = int(capital / price / 100) * 100
                if shares <= 0:
                    continue
                amount = shares * price
                position = shares
                capital -= amount
                trades.append(
                    TradeRecord(
                        date=trade_date,
                        action="buy",
                        price=round(price, 4),
                        quantity=shares,
                        amount=round(amount, 4),
                    )
                )
            elif signal == -1 and position > 0:
                amount = position * price
                capital += amount
                trades.append(
                    TradeRecord(
                        date=trade_date,
                        action="sell",
                        price=round(price, 4),
                        quantity=position,
                        amount=round(amount, 4),
                    )
                )
                position = 0

        return trades, capital, portfolio_values

    def _calculate_metrics(
        self,
        trades: List[TradeRecord],
        initial_capital: float,
        final_capital: float,
        start_date: date,
        end_date: date,
    ) -> BacktestMetricsSummary:
        days = max((end_date - start_date).days, 1)
        total_return = (final_capital - initial_capital) / initial_capital * 100
        annual_return = (pow(final_capital / initial_capital, 365 / days) - 1) * 100

        capital_curve = [initial_capital]
        current_capital = initial_capital
        closed_returns = []
        open_buy: Optional[TradeRecord] = None

        for trade in trades:
            if trade.action == "buy":
                current_capital -= trade.amount
                open_buy = trade
            else:
                current_capital += trade.amount
                if open_buy and open_buy.price > 0:
                    closed_returns.append(
                        (trade.price - open_buy.price) / open_buy.price
                    )
                open_buy = None
            capital_curve.append(current_capital)

        rolling_max = np.maximum.accumulate(capital_curve)
        drawdown = (np.array(capital_curve) - rolling_max) / rolling_max * 100
        max_drawdown = abs(float(np.min(drawdown))) if len(drawdown) > 0 else 0.0

        wins = sum(1 for value in closed_returns if value > 0)
        win_rate = (wins / len(closed_returns) * 100) if closed_returns else 0.0

        if closed_returns and np.std(closed_returns) > 0:
            sharpe_ratio = float(
                np.mean(closed_returns) / np.std(closed_returns) * np.sqrt(252)
            )
        else:
            sharpe_ratio = 0.0

        gross_profit = sum(value for value in closed_returns if value > 0)
        gross_loss = abs(sum(value for value in closed_returns if value < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        return BacktestMetricsSummary(
            sharpe_ratio=round(sharpe_ratio, 4),
            total_return=round(float(total_return), 4),
            annual_return=round(float(annual_return), 4),
            max_drawdown=round(max_drawdown, 4),
            win_rate=round(float(win_rate), 4),
            profit_factor=round(float(profit_factor), 4),
            total_trades=len(trades),
        )
