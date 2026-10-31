from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import hashlib
import json
from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.models import BacktestResult, BacktestTrade, Stock, Strategy
from app.services.market_research_prices import PriceSource, load_research_bars
from app.services.corporate_actions import execution_actions
from app.services.market_data import digest
from app.services.strategy.registry import StrategyRegistry
from app.services.backtest_simulation import (
    BacktestMetricsSummary, ExecutionCosts, PortfolioValue, TradeRecord, daily_metrics, simulate_daily,
)


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
    parameters: Dict[str, Any] = field(default_factory=dict)
    execution_metadata: Dict[str, Any] = field(default_factory=dict)

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
                    "receivable": round(pv.receivable, 4),
                    "pending_shares": pv.pending_shares,
                }
                for pv in self.portfolio_values
            ],
            "parameters": dict(self.parameters),
            "execution_metadata": self.execution_metadata,
        }


class BacktestExecutor:
    def __init__(self, db: Session):
        self.db = db

    def get_stock(self, stock_code: str) -> Optional[Stock]:
        return self.db.query(Stock).filter(Stock.code == stock_code).first()

    def get_kline_data(
        self, stock_code: str, start_date: date, end_date: date, *, price_source: PriceSource = "auto"
    ) -> pd.DataFrame:
        return load_research_bars(self.db, stock_code, start_date, end_date, source=price_source)

    def execute(
        self,
        strategy_name: str,
        stock_code: str,
        start_date: date,
        end_date: date,
        initial_capital: float = 100000,
        parameters: Optional[Dict[str, Any]] = None,
        costs: ExecutionCosts | None = None,
        price_source: PriceSource = "auto",
        corporate_action_mode: Literal["price_only", "verified"] = "price_only",
        dividend_tax_rate: float = 0.0,
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

        df = self.get_kline_data(stock_code, start_date, end_date, price_source=price_source)
        if df.empty:
            raise ValueError(
                f"No kline data found for {stock_code} in the specified date range"
            )
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if corporate_action_mode not in {"price_only", "verified"}:
            raise ValueError("Unknown corporate-action mode")
        actions, action_provenance = [], {}
        if corporate_action_mode == "verified":
            if df.attrs["provenance"]["source"] != "raw":
                raise ValueError("Verified corporate-action execution requires raw prices")
            actions, action_provenance = execution_actions(self.db, stock_code, start_date, end_date)

        effective_parameters = dict(parameters or {})
        strategy = strategy_class(**effective_parameters)
        # Persist the resolved values, including defaults that were omitted
        # from the request, so the history record is independently reproducible.
        effective_parameters = {
            name: definition.default
            for name, definition in strategy.get_parameters().items()
        }
        signal_data = strategy.generate_signals(df.copy())
        if "signal" not in signal_data.columns:
            raise ValueError("Strategy must generate a 'signal' column")

        costs = costs or ExecutionCosts()
        sessions = df.attrs.get("session_dates")
        income = []
        trades, final_capital, portfolio_values = simulate_daily(
            signal_data, initial_capital, costs, session_dates=sessions, corporate_actions=actions,
            dividend_tax_rate=dividend_tax_rate, action_ledger=income)
        metrics = daily_metrics(trades, initial_capital, final_capital, portfolio_values, corporate_income=income)
        input_rows = json.loads(df.to_json(orient="records", date_format="iso", double_precision=15))
        canonical = json.dumps(input_rows, sort_keys=True, separators=(",", ":"))
        execution_metadata = {
            "engine_version": ("daily-next-open-v3" if corporate_action_mode == "verified"
                               else "daily-next-open-v2" if sessions is not None else "daily-next-open-v1"),
            "session_dates": sessions,
            "initial_capital": initial_capital,
            "corporate_action_mode": corporate_action_mode,
            "corporate_actions": actions,
            "corporate_action_provenance": action_provenance,
            "corporate_income": income,
            "dividend_tax_rate": dividend_tax_rate,
            "signal_timing": "previous_completed_bar",
            "fill_timing": "next_bar_open",
            "annualization_sessions": 252,
            "risk_free_rate": 0.0,
            "costs": asdict(costs),
            "trades": [asdict(trade) | {"date": trade.date.isoformat()} for trade in trades],
            "input_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "input_bars": input_rows,
            "signals": [None if pd.isna(value) else int(value) for value in signal_data["signal"]],
            "data_provenance": df.attrs.get("provenance", {}),
            "limitations": [*df.attrs.get("provenance", {}).get("limitations", []),
                            "locked_bars_blocked_conservatively", "daily_all_or_nothing_exits"],
        }
        if corporate_action_mode == "verified":
            execution_metadata["limitations"].remove("corporate_actions_not_applied")
            execution_metadata["limitations"].extend(action_provenance["limitations"])
        execution_metadata["snapshot_sha256"] = digest(execution_metadata)

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
            parameters=effective_parameters,
            execution_metadata=execution_metadata,
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
            parameters=dict(execution.parameters),
            execution_metadata=execution.execution_metadata,
            portfolio_values=[
                {
                    "date": pv.date.isoformat() if hasattr(pv.date, "isoformat") else str(pv.date),
                    "total_value": round(pv.total_value, 2),
                    "cash": round(pv.cash, 2),
                    "position_value": round(pv.position_value, 2),
                    "position": pv.position,
                    "receivable": round(pv.receivable, 4),
                    "pending_shares": pv.pending_shares,
                }
                for pv in execution.portfolio_values
            ],
        )
        try:
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
        except Exception:
            self.db.rollback()
            raise

    def replay(self, result_id: int) -> dict:
        """Replay a saved execution without fetching today's mutable market data."""
        saved = self.db.get(BacktestResult, result_id)
        if saved is None:
            raise ValueError("Backtest result not found")
        metadata = saved.execution_metadata or {}
        if metadata.get("engine_version") not in {"daily-next-open-v1", "daily-next-open-v2", "daily-next-open-v3"}:
            raise ValueError("Historical result lacks a supported execution snapshot")
        canonical = json.dumps(metadata["input_bars"], sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(canonical.encode()).hexdigest() != metadata["input_sha256"]:
            raise ValueError("Snapshot checksum mismatch")
        if "snapshot_sha256" in metadata and digest({
                key: value for key, value in metadata.items() if key != "snapshot_sha256"}) != metadata["snapshot_sha256"]:
            raise ValueError("Execution snapshot checksum mismatch")
        frame = pd.DataFrame(metadata["input_bars"])
        frame["signal"] = metadata["signals"]
        income = []
        trades, value, curve = simulate_daily(
            frame, float(saved.initial_capital), ExecutionCosts(**metadata["costs"]),
            session_dates=metadata.get("session_dates"),
            corporate_actions=metadata.get("corporate_actions"),
            dividend_tax_rate=metadata.get("dividend_tax_rate", 0), action_ledger=income,
        )
        metrics = daily_metrics(trades, float(saved.initial_capital), value, curve, corporate_income=income)
        replayed_trades = [asdict(trade) | {"date": trade.date.isoformat()} for trade in trades]
        curve_matches = len(curve) == len(saved.portfolio_values or []) and all(
            round(point.total_value, 2) == stored["total_value"]
            for point, stored in zip(curve, saved.portfolio_values or [])
        )
        reproduced = (round(value, 2) == float(saved.final_capital)
                      and replayed_trades == metadata.get("trades") and curve_matches
                      and income == metadata.get("corporate_income", []))
        return {"result_id": result_id, "reproduced": reproduced,
                "final_capital": round(value, 2), "metrics": asdict(metrics),
                "input_sha256": metadata["input_sha256"]}

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
            parameters={},
        )
        self.db.add(strategy)
        # Keep strategy creation in the same transaction as its backtest
        # result; a failed snapshot must not leave an orphan strategy row.
        self.db.flush()
        self.db.refresh(strategy)
        return strategy

    def _simulate_trades(
        self, signal_data: pd.DataFrame, initial_capital: float
    ) -> tuple[List[TradeRecord], float, List[PortfolioValue]]:
        return simulate_daily(signal_data, initial_capital)

    def _calculate_metrics(
        self,
        trades: List[TradeRecord],
        initial_capital: float,
        final_capital: float,
        start_date: date,
        end_date: date,
        portfolio_values: List[PortfolioValue],
    ) -> BacktestMetricsSummary:
        return daily_metrics(trades, initial_capital, final_capital, portfolio_values)
