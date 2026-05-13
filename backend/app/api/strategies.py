from functools import reduce
from operator import mul
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import date
from pydantic import BaseModel
import pandas as pd

from app.config import get_db, settings, SessionLocal
from app.auth import get_current_api_key
from app.models.models import Stock, DailyKline
from app.services.backtest_executor import BacktestExecutor
from app.services.job_store import job_store
from app.services.strategy.registry import StrategyRegistry
from app.services.strategy.factors import TechnicalFactors
from app.services.strategy.optimizer import GridSearchOptimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


# ==================== Request/Response Models ====================


class StrategyInfo(BaseModel):
    """Strategy information model."""

    name: str
    description: str
    parameters: Dict[str, Any]


class StrategyDetailResponse(BaseModel):
    """Detailed strategy information response."""

    name: str
    description: str
    parameters: Dict[str, Any]


class SignalRequest(BaseModel):
    """Request model for generating trading signals."""

    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    parameters: Optional[Dict[str, Any]] = {}


class SignalDataPoint(BaseModel):
    """Single signal data point."""

    date: date
    close: float
    signal: int
    # Optional auxiliary indicators
    ma_short: Optional[float] = None
    ma_long: Optional[float] = None
    volume: Optional[float] = None
    pred_close_5d: Optional[float] = None
    pred_return_5d: Optional[float] = None
    confidence: Optional[float] = None


class SignalResponse(BaseModel):
    """Response model for signal generation."""

    success: bool
    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    data: List[Dict[str, Any]]
    stats: Optional[Dict[str, Any]] = None


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
    parameters: Optional[Dict[str, Any]] = {}


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


class BacktestResponse(BaseModel):
    """Response model for backtest results."""

    success: bool
    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    trades: List[BacktestTradeItem]
    metrics: BacktestMetrics


class OptimizeRequest(BaseModel):
    """Request model for parameter optimization."""

    strategy_name: str
    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float = 100000
    param_grid: Dict[str, List[Any]]
    metric: str = "sharpe_ratio"


class OptimizeResultItem(BaseModel):
    """Single optimization result."""

    params: Dict[str, Any]
    metrics: Dict[str, float]
    score: float


class OptimizeResponse(BaseModel):
    """Response model for optimization results."""

    success: bool
    strategy_name: str
    stock_code: str
    metric: str
    best_params: Dict[str, Any]
    best_score: float
    best_metrics: Dict[str, float]
    total_combinations: int
    all_results: List[OptimizeResultItem]


class OptimizeSubmitResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ==================== Helper Functions ====================


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
            "open": k.open,
            "high": k.high,
            "low": k.low,
            "close": k.close,
            "volume": k.volume,
        }
        for k in klines
    ]

    return pd.DataFrame(data)


def get_strategy_class(strategy_name: str):
    """Get strategy class from registry."""
    strategy_class = StrategyRegistry.get(strategy_name)
    if strategy_class is None:
        available = StrategyRegistry.list_strategies()
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{strategy_name}' not found. Available strategies: {available}",
        )
    return strategy_class


def generate_ma_cross_signals(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
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


def _compute_signal_stats(data: List[Dict[str, Any]]) -> Dict[str, Any]:
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


# ==================== API Endpoints ====================


@router.get("", response_model=List[StrategyInfo])
def list_strategies(_: str = Depends(get_current_api_key)):
    """
    Get all available strategies.

    Returns:
        List of all registered strategies with their names, descriptions, and parameters.
    """
    strategies = StrategyRegistry.get_all()

    result = []
    for name, strategy_class in strategies.items():
        strategy = strategy_class()
        params = strategy.get_parameters()

        # Convert parameters to dictionary
        params_dict = {
            param_name: param.to_dict() for param_name, param in params.items()
        }

        result.append(
            StrategyInfo(
                name=strategy.get_name(),
                description=strategy.get_description(),
                parameters=params_dict,
            )
        )

    return result


@router.get("/{strategy_name}", response_model=StrategyDetailResponse)
def get_strategy(strategy_name: str, _: str = Depends(get_current_api_key)):
    """
    Get detailed information about a specific strategy.

    Args:
        strategy_name: Name of the strategy to retrieve.

    Returns:
        Detailed strategy information including name, description, and parameters.
    """
    strategy_class = get_strategy_class(strategy_name)
    strategy = strategy_class()
    params = strategy.get_parameters()

    params_dict = {param_name: param.to_dict() for param_name, param in params.items()}

    return StrategyDetailResponse(
        name=strategy.get_name(),
        description=strategy.get_description(),
        parameters=params_dict,
    )


@router.post("/signals", response_model=SignalResponse)
def generate_signals(
    request: SignalRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """
    Generate trading signals for a strategy.

    Args:
        request: Signal request containing strategy name, stock code, date range, and parameters.

    Returns:
        Trading signals with date, close price, signal value, and auxiliary indicators.
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.code == request.stock_code).first()
    if not stock:
        raise HTTPException(
            status_code=404, detail=f"Stock '{request.stock_code}' not found"
        )

    # Get kline data
    df = get_kline_data(db, request.stock_code, request.start_date, request.end_date)
    if df.empty:
        raise HTTPException(
            status_code=400,
            detail=f"No kline data found for {request.stock_code} in the specified date range",
        )

    # Try to get strategy from registry first
    try:
        strategy_class = get_strategy_class(request.strategy_name)
        strategy = strategy_class()

        # Apply custom parameters if provided
        if request.parameters:
            for key, value in request.parameters.items():
                setattr(strategy, key, value)

        # Generate signals using strategy
        signal_data = strategy.generate_signals(df.copy())

    except Exception:
        # Fall back to built-in MA cross strategy
        params = request.parameters or {}
        signal_data = generate_ma_cross_signals(df, params)

    # Prepare response data
    data = []
    for _, row in signal_data.iterrows():
        if pd.isna(row.get("signal", 0)) or row.get("signal", 0) == 0:
            continue

        record = {
            "date": row["date"].date() if hasattr(row["date"], "date") else row["date"],
            "close": float(row["close"]),
            "signal": int(row["signal"]),
        }

        # Add auxiliary indicators if available
        if "ma_short" in row and not pd.isna(row.get("ma_short")):
            record["ma_short"] = float(row["ma_short"])
        if "ma_long" in row and not pd.isna(row.get("ma_long")):
            record["ma_long"] = float(row["ma_long"])
        if "volume" in row:
            record["volume"] = float(row["volume"])
        if "pred_close_5d" in row and not pd.isna(row.get("pred_close_5d")):
            record["pred_close_5d"] = float(row["pred_close_5d"])
        if "pred_return_5d" in row and not pd.isna(row.get("pred_return_5d")):
            record["pred_return_5d"] = float(row["pred_return_5d"])
        if "confidence" in row and not pd.isna(row.get("confidence")):
            record["confidence"] = float(row["confidence"])

        data.append(record)

    # Compute rolling signal statistics
    stats = _compute_signal_stats(data)

    return SignalResponse(
        success=True,
        strategy_name=request.strategy_name,
        stock_code=request.stock_code,
        start_date=request.start_date,
        end_date=request.end_date,
        data=data,
        stats=stats,
    )


@router.post("/backtest", response_model=BacktestResponse)
def run_backtest(
    request: BacktestRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """
    Run backtest for a strategy.

    Args:
        request: Backtest request containing strategy name, stock code, date range,
                 initial capital, and parameters.

    Returns:
        Backtest results including trades and performance metrics.
    """
    try:
        execution = BacktestExecutor(db).execute(
            strategy_name=request.strategy_name,
            stock_code=request.stock_code,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            parameters=request.parameters or {},
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=400, detail=message)

    return BacktestResponse(
        success=True,
        strategy_name=execution.strategy_name,
        stock_code=execution.stock_code,
        start_date=execution.start_date,
        end_date=execution.end_date,
        initial_capital=execution.initial_capital,
        final_capital=execution.final_capital,
        trades=[
            BacktestTradeItem(**trade) for trade in execution.to_api_dict()["trades"]
        ],
        metrics=BacktestMetrics(**execution.to_api_dict()["metrics"]),
    )


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_parameters(
    request: OptimizeRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """
    Optimize strategy parameters using grid search.

    Args:
        request: Optimization request containing strategy name, stock code, date range,
                 parameter grid to search, and optimization metric.

    Returns:
        Optimization results including best parameters, best score, and all results.
    """
    stock = db.query(Stock).filter(Stock.code == request.stock_code).first()
    if not stock:
        raise HTTPException(
            status_code=404, detail=f"Stock '{request.stock_code}' not found"
        )

    df = get_kline_data(db, request.stock_code, request.start_date, request.end_date)
    if df.empty:
        raise HTTPException(
            status_code=400,
            detail=f"No kline data found for {request.stock_code} in the specified date range",
        )

    get_strategy_class(request.strategy_name)

    valid_metrics = [
        "sharpe_ratio",
        "total_return",
        "max_drawdown",
        "win_rate",
        "profit_factor",
    ]
    if request.metric not in valid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric '{request.metric}'. Valid: {valid_metrics}",
        )

    total_combinations = reduce(
        mul, (len(values) for values in request.param_grid.values()), 1
    )
    if total_combinations > settings.MAX_OPTIMIZE_COMBINATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Parameter grid too large: {total_combinations} combinations. "
                f"Limit is {settings.MAX_OPTIMIZE_COMBINATIONS}."
            ),
        )

    # Validate param_grid values against strategy parameter bounds
    strategy_class = get_strategy_class(request.strategy_name)
    strategy = strategy_class()
    strategy_params = strategy.get_parameters()
    for param_name, values in request.param_grid.items():
        param_def = strategy_params.get(param_name)
        if param_def is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown parameter '{param_name}' for strategy '{request.strategy_name}'",
            )
        for val in values:
            if param_def.min_value is not None and val < param_def.min_value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Parameter '{param_name}': value {val} is below minimum {param_def.min_value}",
                )
            if param_def.max_value is not None and val > param_def.max_value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Parameter '{param_name}': value {val} exceeds maximum {param_def.max_value}",
                )
            if param_def.choices and val not in param_def.choices:
                raise HTTPException(
                    status_code=400,
                    detail=f"Parameter '{param_name}': value {val} is not in valid choices: {param_def.choices}",
                )

    optimizer = GridSearchOptimizer(initial_capital=request.initial_capital)

    try:
        result = optimizer.optimize(
            strategy_name=request.strategy_name,
            data=df,
            param_grid=request.param_grid,
            metric=request.metric,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Prepare response
    all_results = [
        OptimizeResultItem(params=r.params, metrics=r.metrics, score=r.score)
        for r in result.all_results
    ]

    return OptimizeResponse(
        success=True,
        strategy_name=request.strategy_name,
        stock_code=request.stock_code,
        metric=request.metric,
        best_params=result.best_params,
        best_score=result.best_score,
        best_metrics=result.best_metrics,
        total_combinations=result.total_combinations,
        all_results=all_results,
    )


def _run_optimize_job(job_id: str, request_data: Dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        request = OptimizeRequest(**request_data)
        job_store.update(
            job_id, status="running", message="Optimizing strategy parameters"
        )
        response = optimize_parameters(request, db)
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message="Optimization completed",
            result=response.model_dump(),
        )
    except Exception as exc:
        logger.error("Strategy optimization job failed", exc_info=True)
        job_store.update(
            job_id,
            status="failed",
            error=str(exc),
            message="Strategy optimization failed",
        )
    finally:
        db.close()


@router.post("/optimize/submit", response_model=OptimizeSubmitResponse)
def submit_optimize(
    request: OptimizeRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(get_current_api_key),
):
    job = job_store.create(
        job_type="strategy_optimize", payload=request.model_dump(mode="json")
    )
    background_tasks.add_task(
        _run_optimize_job, job.id, request.model_dump(mode="json")
    )
    return OptimizeSubmitResponse(
        job_id=job.id, status=job.status, message="Optimization queued"
    )


# ==================== Strategy Comparison ====================


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
    equity_curve: List[CompareStrategyCurve]
    error: Optional[str] = None


class CompareResponse(BaseModel):
    """Response model for strategy comparison."""

    success: bool
    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float
    results: List[CompareStrategyResult]
    total_strategies: int
    failed_count: int


@router.post("/compare", response_model=CompareResponse)
def compare_strategies(
    request: CompareRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Run all registered strategies on a stock and return comparison results."""
    strategies = StrategyRegistry.get_all()
    results: List[CompareStrategyResult] = []
    failed = 0

    for name, strategy_class in strategies.items():
        try:
            strategy = strategy_class()
            executor = BacktestExecutor(db)
            execution = executor.execute(
                strategy_name=name,
                stock_code=request.stock_code,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
            )

            # Build equity curve from trade-level capital tracking
            curve = _build_equity_curve(
                execution.trades,
                request.initial_capital,
                execution.final_capital,
            )

            results.append(
                CompareStrategyResult(
                    strategy_name=name,
                    description=strategy.get_description(),
                    metrics=CompareStrategyMetrics(
                        strategy_name=name,
                        total_return=execution.metrics.total_return,
                        annual_return=execution.metrics.annual_return,
                        sharpe_ratio=execution.metrics.sharpe_ratio,
                        max_drawdown=execution.metrics.max_drawdown,
                        win_rate=execution.metrics.win_rate,
                        total_trades=execution.metrics.total_trades,
                        profit_factor=execution.metrics.profit_factor,
                    ),
                    equity_curve=curve,
                )
            )
        except Exception as exc:
            logger.warning("Strategy '%s' comparison failed: %s", name, exc)
            failed += 1
            results.append(
                CompareStrategyResult(
                    strategy_name=name,
                    description=str(getattr(strategy_class, "__doc__", "") or ""),
                    metrics=CompareStrategyMetrics(
                        strategy_name=name,
                        total_return=0.0,
                        annual_return=0.0,
                        sharpe_ratio=0.0,
                        max_drawdown=0.0,
                        win_rate=0.0,
                        total_trades=0,
                        profit_factor=0.0,
                    ),
                    equity_curve=[],
                    error=str(exc),
                )
            )

    return CompareResponse(
        success=failed < len(strategies),
        stock_code=request.stock_code,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        results=results,
        total_strategies=len(strategies),
        failed_count=failed,
    )


def _build_equity_curve(
    trades: list,
    initial_capital: float,
    final_capital: float,
) -> List[CompareStrategyCurve]:
    """Build daily equity curve from trade list."""
    curve: List[CompareStrategyCurve] = [
        CompareStrategyCurve(date="start", value=initial_capital)
    ]
    capital = initial_capital

    for trade in trades:
        trade_date = str(getattr(trade, "date", ""))
        if trade.action == "buy":
            capital -= trade.amount
        else:
            capital += trade.amount
        curve.append(
            CompareStrategyCurve(date=trade_date, value=round(capital, 2))
        )

    if not curve or curve[-1].date != "end":
        curve.append(CompareStrategyCurve(date="end", value=round(final_capital, 2)))
    return curve
