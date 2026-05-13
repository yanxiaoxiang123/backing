from datetime import date
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.models import BacktestResult
from app.services.backtest_executor import BacktestExecutor


class BacktestEngine:
    """Backward-compatible wrapper around the shared backtest executor."""

    def __init__(self, db: Session):
        self.db = db
        self.executor = BacktestExecutor(db)

    def run_backtest(
        self,
        stock_code: str,
        strategy_type: str = "ma_cross",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        initial_capital: float = 100000,
        parameters: Optional[Dict] = None,
    ) -> Optional[BacktestResult]:
        if start_date is None or end_date is None:
            raise ValueError("start_date and end_date are required")

        execution = self.executor.execute(
            strategy_name=strategy_type,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            parameters=parameters,
        )
        return self.executor.persist(execution)
