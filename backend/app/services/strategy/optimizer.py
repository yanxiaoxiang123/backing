"""
Strategy Parameter Optimizer

Provides grid search optimization for strategy parameters.
"""

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import product
from typing import Any, Dict, List, Tuple

import pandas as pd

from .base import Strategy
from .registry import StrategyRegistry

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of a single optimization run."""

    params: Dict[str, Any]
    metrics: Dict[str, float]
    score: float


@dataclass
class GridSearchResult:
    """Result of grid search optimization."""

    best_params: Dict[str, Any]
    best_score: float
    best_metrics: Dict[str, float]
    all_results: List[OptimizationResult]
    total_combinations: int


def run_strategy_backtest(
    strategy: Strategy,
    data: pd.DataFrame,
    params: Dict[str, Any],
    initial_capital: float = 100000,
) -> Tuple[List[Dict[str, Any]], float, Dict[str, float]]:
    """
    Run backtest for a strategy with given parameters.

    Args:
        strategy: Strategy instance
        data: Market data DataFrame
        params: Strategy parameters
        initial_capital: Initial capital

    Returns:
        Tuple of (trades, final_capital, metrics)
    """
    from dataclasses import asdict

    from app.services.backtest_simulation import daily_metrics, simulate_daily

    signal_data = type(strategy)(**params).generate_signals(data.copy())
    income = []
    trades, capital, curve = simulate_daily(
        signal_data, initial_capital, session_dates=data.attrs.get("session_dates"),
        corporate_actions=data.attrs.get("corporate_actions"),
        dividend_tax_rate=data.attrs.get("dividend_tax_rate", 0), action_ledger=income)
    metrics = daily_metrics(trades, initial_capital, capital, curve, corporate_income=income)
    return [asdict(trade) for trade in trades], capital, asdict(metrics)


class ParameterOptimizer(ABC):
    """Abstract base class for parameter optimizers."""

    @abstractmethod
    def optimize(self, strategy_name: str, data: pd.DataFrame, **kwargs) -> Any:
        """
        Optimize strategy parameters.

        Args:
            strategy_name: Name of the strategy to optimize
            data: Market data for backtesting
            **kwargs: Additional optimizer-specific parameters

        Returns:
            Optimization result object
        """

    def _get_strategy(self, strategy_name: str) -> Strategy:
        """Get strategy instance by name."""
        strategy_class = StrategyRegistry.get(strategy_name)
        if strategy_class is None:
            raise ValueError(
                f"Strategy '{strategy_name}' not found. Available: {StrategyRegistry.list_strategies()}"
            )
        return strategy_class()


class GridSearchOptimizer(ParameterOptimizer):
    """
    Grid search optimizer for strategy parameters.

    Exhaustively searches all parameter combinations from a grid.
    """

    def __init__(self, initial_capital: float = 100000):
        """
        Initialize grid search optimizer.

        Args:
            initial_capital: Initial capital for backtesting
        """
        self.initial_capital = initial_capital

    def optimize(
        self, strategy_name: str, data: pd.DataFrame, **kwargs
    ) -> GridSearchResult:
        param_grid = kwargs["param_grid"]
        metric = kwargs.get("metric", "sharpe_ratio")
        """
        Optimize strategy parameters using grid search.

        Args:
            strategy_name: Name of the strategy to optimize
            data: Market data for backtesting
            param_grid: Dictionary mapping parameter names to lists of candidate values
            metric: Metric to optimize ('sharpe_ratio', 'total_return', 'max_drawdown', 'win_rate')

        Returns:
            GridSearchResult with best parameters, best score, and all results

        Raises:
            ValueError: If strategy not found or metric invalid
        """
        # Validate metric
        valid_metrics = [
            "sharpe_ratio",
            "total_return",
            "max_drawdown",
            "win_rate",
            "profit_factor",
        ]
        if metric not in valid_metrics:
            raise ValueError(f"Invalid metric '{metric}'. Valid: {valid_metrics}")

        # Get strategy
        strategy = self._get_strategy(strategy_name)
        strategy_params = strategy.get_parameters()

        # Validate param_grid keys
        for param_name in param_grid:
            if param_name not in strategy_params:
                raise ValueError(
                    f"Parameter '{param_name}' not found in strategy '{strategy_name}'"
                )

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        total_combinations = math.prod(len(values) for values in param_values)
        if total_combinations == 0:
            raise ValueError("Parameter grid must contain at least one value per parameter")
        combinations = product(*param_values)

        logger.info(
            f"Starting grid search: {total_combinations} combinations for strategy '{strategy_name}'"
        )

        all_results: List[OptimizationResult] = []
        best_score = float("-inf") if metric != "max_drawdown" else float("inf")
        best_params = None
        best_metrics = None

        for combo in combinations:
            params = dict(zip(param_names, combo))

            try:
                _, _, metrics = run_strategy_backtest(
                    strategy, data, params, self.initial_capital
                )

                # For max_drawdown, lower is better (we minimize)
                score = metrics[metric]

                result = OptimizationResult(params=params, metrics=metrics, score=score)
                all_results.append(result)

                # Update best
                is_better = score < best_score if metric == "max_drawdown" else score > best_score

                if is_better or best_params is None:
                    best_score = score
                    best_params = params
                    best_metrics = metrics

            except Exception as e:
                logger.warning(f"Failed for params {params}: {e}")
                continue

        # Adjust best_score back to actual metric value
        if best_params is None or best_metrics is None:
            raise ValueError(
                "No parameter combination completed successfully. "
                "Check strategy parameters and market data types."
            )

        if metric == "max_drawdown" and best_metrics is not None:
            best_score = best_metrics[metric]

        logger.info(f"Grid search complete. Best {metric}: {best_score:.4f}")

        return GridSearchResult(
            best_params=best_params,
            best_score=best_score,
            best_metrics=best_metrics,
            all_results=all_results,
            total_combinations=total_combinations,
        )
