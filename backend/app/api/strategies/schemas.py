"""Request/response DTOs for the strategy API.

Split out of ``app/api/strategies.py`` so endpoint wiring, orchestration and
payload contracts can evolve independently.
"""

from datetime import date
from typing import Any

from pydantic import BaseModel


class StrategyInfo(BaseModel):
    """Strategy information model."""

    name: str
    description: str
    parameters: dict[str, Any]


class StrategyDetailResponse(BaseModel):
    """Detailed strategy information response."""

    name: str
    description: str
    parameters: dict[str, Any]


class SignalRequest(BaseModel):
    """Request model for generating trading signals."""

    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    parameters: dict[str, Any] | None = {}


class SignalDataPoint(BaseModel):
    """Single signal data point."""

    date: date
    close: float
    signal: int
    # Optional auxiliary indicators
    ma_short: float | None = None
    ma_long: float | None = None
    volume: float | None = None
    pred_close_5d: float | None = None
    pred_return_5d: float | None = None
    confidence: float | None = None


class SignalResponse(BaseModel):
    """Response model for signal generation."""

    success: bool
    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    data: list[dict[str, Any]]
    stats: dict[str, Any] | None = None


class SignalStats(BaseModel):
    """Historical signal performance statistics for the stock/strategy pair."""

    total_buy_signals: int = 0
    total_sell_signals: int = 0
    total_trades: int = 0
    win_rate: float = 0.0
    avg_holding_days: float = 0.0
    avg_return_per_trade: float = 0.0
    profit_ratio: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0


class BacktestRequest(BaseModel):
    """Request model for running backtest."""

    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float = 100000
    parameters: dict[str, Any] | None = {}


class BacktestTradeItem(BaseModel):
    """Single trade in backtest result."""

    date: date
    action: str
    price: float
    quantity: int
    amount: float


class BacktestMetrics(BaseModel):
    """Backtest performance metrics."""

    sharpe_ratio: float
    total_return: float
    annual_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int


class PortfolioValueItem(BaseModel):
    """Single portfolio value snapshot."""

    date: str
    total_value: float
    cash: float
    position_value: float
    position: int


class BacktestResponse(BaseModel):
    """Response model for backtest results."""

    success: bool
    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    trades: list[BacktestTradeItem]
    metrics: BacktestMetrics
    portfolio_values: list[PortfolioValueItem] | None = None


class OptimizeRequest(BaseModel):
    """Request model for parameter optimization."""

    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float = 100000
    param_grid: dict[str, list[Any]]
    metric: str = "sharpe_ratio"


class OptimizeResultItem(BaseModel):
    """Single optimization result."""

    params: dict[str, Any]
    metrics: dict[str, float]
    score: float


class OptimizeResponse(BaseModel):
    """Response model for optimization results."""

    success: bool
    strategy_name: str
    stock_code: str
    metric: str
    best_params: dict[str, Any]
    best_score: float
    best_metrics: dict[str, float]
    total_combinations: int
    all_results: list[OptimizeResultItem]


class OptimizeSubmitResponse(BaseModel):
    job_id: str
    status: str
    message: str


class CompareRequest(BaseModel):
    """Request model for comparing all strategies on a stock."""

    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float = 100000


class CompareStrategyMetrics(BaseModel):
    """Metrics for a single strategy in comparison results."""

    strategy_name: str
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    profit_factor: float


class CompareStrategyCurve(BaseModel):
    """Equity curve data point."""

    date: str
    value: float


class CompareStrategyResult(BaseModel):
    """Single strategy result in comparison."""

    strategy_name: str
    description: str
    metrics: CompareStrategyMetrics
    equity_curve: list[CompareStrategyCurve]
    error: str | None = None


class CompareResponse(BaseModel):
    """Response model for strategy comparison."""

    success: bool
    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float
    results: list[CompareStrategyResult]
    total_strategies: int
    failed_count: int
