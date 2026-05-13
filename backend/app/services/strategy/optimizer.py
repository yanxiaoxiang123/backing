"""
Strategy Parameter Optimizer

Provides grid search and random search optimization for strategy parameters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from itertools import product
import logging

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


@dataclass
class RandomSearchResult:
    """Result of random search optimization."""

    best_params: Dict[str, Any]
    best_score: float
    best_metrics: Dict[str, float]
    all_results: List[OptimizationResult]
    n_iterations: int


def calculate_metrics(
    trades: List[Dict[str, Any]], capital: float, returns: Optional[pd.Series] = None
) -> Dict[str, float]:
    """
    Calculate backtest performance metrics.

    Args:
        trades: List of trade dictionaries with 'action', 'price', 'quantity', 'amount'
        capital: Initial capital
        returns: Optional pre-calculated returns series

    Returns:
        Dictionary containing: sharpe_ratio, total_return, annual_return,
        max_drawdown, win_rate, profit_factor
    """
    if not trades:
        return {
            "sharpe_ratio": 0.0,
            "total_return": 0.0,
            "annual_return": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_trades": 0,
        }

    # Build capital curve
    capital_curve = [capital]
    current_capital = capital

    # Track trades with entry/exit pairs
    closed_trades = []
    open_position = None

    for trade in trades:
        if trade["action"] == "buy":
            open_position = {
                "entry_price": trade["price"],
                "entry_date": trade.get("date"),
                "quantity": trade["quantity"],
            }
        elif trade["action"] == "sell" and open_position is not None:
            profit = (trade["price"] - open_position["entry_price"]) * open_position[
                "quantity"
            ]
            closed_trades.append(
                {
                    "profit": profit,
                    "entry_price": open_position["entry_price"],
                    "exit_price": trade["price"],
                }
            )
            open_position = None

        if trade["action"] == "buy":
            current_capital -= trade["amount"]
        else:
            current_capital += trade["amount"]
        capital_curve.append(current_capital)

    # Add final capital if position still open
    if open_position is not None:
        current_capital = capital_curve[-1]

    final_capital = current_capital

    # Total return
    total_return = (final_capital - capital) / capital * 100 if capital > 0 else 0.0

    # Annual return (assuming ~252 trading days)
    days = len(capital_curve) - 1 if len(capital_curve) > 1 else 1
    annual_return = (
        (pow(final_capital / capital, 252 / days) - 1) * 100
        if capital > 0 and days > 0
        else 0.0
    )

    # Max drawdown
    if len(capital_curve) > 1:
        rolling_max = np.maximum.accumulate(capital_curve)
        drawdown = (np.array(capital_curve) - rolling_max) / rolling_max * 100
        max_drawdown = abs(float(np.min(drawdown))) if len(drawdown) > 0 else 0.0
    else:
        max_drawdown = 0.0

    # Sharpe ratio
    if returns is not None and len(returns) > 1:
        returns_arr = returns.dropna()
        if len(returns_arr) > 0 and returns_arr.std() > 0:
            sharpe_ratio = (returns_arr.mean() / returns_arr.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
    elif closed_trades:
        # Calculate from trade returns
        trade_returns = []
        for closed_trade in closed_trades:
            if closed_trade["entry_price"] > 0:
                ret = (
                    closed_trade["exit_price"] - closed_trade["entry_price"]
                ) / closed_trade["entry_price"]
                trade_returns.append(ret)

        if trade_returns and np.std(trade_returns) > 0:
            sharpe_ratio = (np.mean(trade_returns) / np.std(trade_returns)) * np.sqrt(
                252
            )
        else:
            sharpe_ratio = 0.0
    else:
        sharpe_ratio = 0.0

    # Win rate
    if closed_trades:
        wins = sum(1 for t in closed_trades if t["profit"] > 0)
        win_rate = (wins / len(closed_trades)) * 100
    else:
        win_rate = 0.0

    # Profit factor
    if closed_trades:
        gross_profit = sum(t["profit"] for t in closed_trades if t["profit"] > 0)
        gross_loss = abs(sum(t["profit"] for t in closed_trades if t["profit"] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
    else:
        profit_factor = 0.0

    return {
        "sharpe_ratio": round(float(sharpe_ratio), 4),
        "total_return": round(float(total_return), 4),
        "annual_return": round(float(annual_return), 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "win_rate": round(float(win_rate), 4),
        "profit_factor": round(float(profit_factor), 4),
        "total_trades": len(closed_trades),
    }


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
    # Create strategy instance with params
    strategy_instance = type(strategy)(**params)

    # Generate signals
    signal_data = strategy_instance.generate_signals(data.copy())

    if "signal" not in signal_data.columns:
        raise ValueError("Strategy must generate 'signal' column")

    # Simulate trading
    capital = initial_capital
    position = 0
    trades = []

    for idx, row in signal_data.iterrows():
        if pd.isna(row.get("signal", 0)) or row.get("signal", 0) == 0:
            continue

        trade_signal = row.get("signal", 0)
        trade_date = row.get("date", idx)
        price = row["close"]

        if trade_signal == 1 and position == 0:
            # Buy signal and no position
            shares = int(capital / price / 100) * 100
            if shares > 0:
                cost = shares * price
                position = shares
                capital -= cost

                trades.append(
                    {
                        "date": trade_date,
                        "action": "buy",
                        "price": price,
                        "quantity": shares,
                        "amount": cost,
                    }
                )

        elif trade_signal == -1 and position > 0:
            # Sell signal and have position
            proceeds = position * price
            capital += proceeds

            trades.append(
                {
                    "date": trade_date,
                    "action": "sell",
                    "price": price,
                    "quantity": position,
                    "amount": proceeds,
                }
            )

            position = 0

    # Close position at end if still open
    if position > 0:
        final_price = signal_data.iloc[-1]["close"]
        proceeds = position * final_price
        capital += proceeds

        trades.append(
            {
                "date": signal_data.iloc[-1].get("date", signal_data.index[-1]),
                "action": "sell",
                "price": final_price,
                "quantity": position,
                "amount": proceeds,
            }
        )

    # Calculate metrics
    metrics = calculate_metrics(trades, initial_capital)

    return trades, capital, metrics


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
        pass

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
        for param_name in param_grid.keys():
            if param_name not in strategy_params:
                raise ValueError(
                    f"Parameter '{param_name}' not found in strategy '{strategy_name}'"
                )

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        logger.info(
            f"Starting grid search: {len(combinations)} combinations for strategy '{strategy_name}'"
        )

        all_results: List[OptimizationResult] = []
        best_score = float("-inf") if metric != "max_drawdown" else float("inf")
        best_params = None
        best_metrics = None

        for combo in combinations:
            params = dict(zip(param_names, combo))

            try:
                trades, final_capital, metrics = run_strategy_backtest(
                    strategy, data, params, self.initial_capital
                )

                # For max_drawdown, lower is better (we minimize)
                if metric == "max_drawdown":
                    score = -metrics[metric]  # Negative because we want to minimize
                else:
                    score = metrics[metric]

                result = OptimizationResult(params=params, metrics=metrics, score=score)
                all_results.append(result)

                # Update best
                is_better = (metric != "max_drawdown" and score > best_score) or (
                    metric == "max_drawdown" and score < best_score
                )

                if is_better or best_params is None:
                    best_score = score
                    best_params = params
                    best_metrics = metrics

            except Exception as e:
                logger.warning(f"Failed for params {params}: {e}")
                continue

        # Adjust best_score back to actual metric value
        if metric == "max_drawdown" and best_metrics is not None:
            best_score = best_metrics[metric]

        logger.info(f"Grid search complete. Best {metric}: {best_score:.4f}")

        return GridSearchResult(
            best_params=best_params,
            best_score=best_score,
            best_metrics=best_metrics,
            all_results=all_results,
            total_combinations=len(combinations),
        )


class RandomSearchOptimizer(ParameterOptimizer):
    """
    Random search optimizer for strategy parameters.

    Randomly samples parameter combinations from distributions.
    """

    def __init__(
        self, initial_capital: float = 100000, random_state: Optional[int] = None
    ):
        """
        Initialize random search optimizer.

        Args:
            initial_capital: Initial capital for backtesting
            random_state: Random seed for reproducibility
        """
        self.initial_capital = initial_capital
        self.random_state = random_state
        self._rng = np.random.default_rng(random_state)

    def optimize(
        self, strategy_name: str, data: pd.DataFrame, **kwargs
    ) -> RandomSearchResult:
        param_distributions = kwargs["param_distributions"]
        n_iter = kwargs.get("n_iter", 50)
        metric = kwargs.get("metric", "sharpe_ratio")
        """
        Optimize strategy parameters using random search.

        Args:
            strategy_name: Name of the strategy to optimize
            data: Market data for backtesting
            param_distributions: Dictionary mapping parameter names to scipy.stats distributions
            n_iter: Number of random samples to evaluate
            metric: Metric to optimize ('sharpe_ratio', 'total_return', 'max_drawdown', 'win_rate')

        Returns:
            RandomSearchResult with best parameters, best score, and all results

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

        # Validate param_distributions keys
        for param_name in param_distributions.keys():
            if param_name not in strategy_params:
                raise ValueError(
                    f"Parameter '{param_name}' not found in strategy '{strategy_name}'"
                )

        logger.info(
            f"Starting random search: {n_iter} iterations for strategy '{strategy_name}'"
        )

        all_results: List[OptimizationResult] = []
        best_score = float("-inf") if metric != "max_drawdown" else float("inf")
        best_params = None
        best_metrics = None

        for i in range(n_iter):
            # Sample parameters
            params = {}
            for param_name, distribution in param_distributions.items():
                param_def = strategy_params[param_name]
                value = distribution.rvs(random_state=self._rng.integers(2**31))

                # Clamp to parameter bounds
                if param_def.min_value is not None:
                    value = max(param_def.min_value, value)
                if param_def.max_value is not None:
                    value = min(param_def.max_value, value)

                # Cast to appropriate type
                if param_def.param_type.value == "int":
                    value = int(round(value))
                elif param_def.param_type.value == "float":
                    value = float(value)

                params[param_name] = value

            try:
                trades, final_capital, metrics = run_strategy_backtest(
                    strategy, data, params, self.initial_capital
                )

                # For max_drawdown, lower is better (we minimize)
                if metric == "max_drawdown":
                    score = -metrics[metric]
                else:
                    score = metrics[metric]

                result = OptimizationResult(params=params, metrics=metrics, score=score)
                all_results.append(result)

                # Update best
                is_better = (metric != "max_drawdown" and score > best_score) or (
                    metric == "max_drawdown" and score < best_score
                )

                if is_better or best_params is None:
                    best_score = score
                    best_params = params
                    best_metrics = metrics
                    logger.debug(
                        f"New best at iteration {i + 1}: {metric} = {metrics[metric]:.4f}"
                    )

            except Exception as e:
                logger.warning(f"Failed for params {params}: {e}")
                continue

        # Adjust best_score back to actual metric value
        if metric == "max_drawdown" and best_metrics is not None:
            best_score = best_metrics[metric]

        logger.info(f"Random search complete. Best {metric}: {best_score:.4f}")

        return RandomSearchResult(
            best_params=best_params,
            best_score=best_score,
            best_metrics=best_metrics,
            all_results=all_results,
            n_iterations=n_iter,
        )
