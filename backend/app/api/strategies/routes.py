"""Strategy API endpoints — thin routing over strategy services.

Request/response DTOs live in ``schemas.py``; signal helpers in
``app/services/strategy/signals.py``; long-running optimization is submitted
through the shared task executor (``app/services/tasks``) so it survives
restarts and runs on the configured backend.
"""

import logging
from functools import reduce
from operator import mul
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.strategies.schemas import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    BacktestTradeItem,
    CompareRequest,
    CompareResponse,
    CompareStrategyCurve,
    CompareStrategyMetrics,
    CompareStrategyResult,
    OptimizeRequest,
    OptimizeResponse,
    OptimizeResultItem,
    OptimizeSubmitResponse,
    PortfolioValueItem,
    SignalRequest,
    SignalResponse,
    StrategyDetailResponse,
    StrategyInfo,
)
from app.auth import get_current_api_key
from app.config import SessionLocal, get_db, settings
from app.exceptions import NotFoundError, ValidationError
from app.models.models import Stock
from app.services.backtest_executor import BacktestExecutor
from app.services.job_store import job_store
from app.services.strategy.optimizer import GridSearchOptimizer
from app.services.strategy.registry import StrategyRegistry
from app.services.strategy.signals import (
    compute_signal_stats,
    generate_ma_cross_signals,
    get_kline_data,
)
from app.services.tasks import get_task_executor, register_runner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


# ==================== Helper Functions ====================


def get_strategy_class(strategy_name: str):
    """Get strategy class from registry."""
    strategy_class = StrategyRegistry.get(strategy_name)
    if strategy_class is None:
        available = StrategyRegistry.list_strategies()
        raise NotFoundError(
            detail=(
                f"Strategy '{strategy_name}' not found. "
                f"Available strategies: {available}"
            )
        )
    return strategy_class


def _validate_optimize_request(
    db: Session, request: OptimizeRequest
) -> pd.DataFrame:
    """Shared validation for optimize endpoints (sync + async)."""
    stock = db.query(Stock).filter(Stock.code == request.stock_code).first()
    if not stock:
        raise NotFoundError(detail=f"Stock '{request.stock_code}' not found")

    df = get_kline_data(db, request.stock_code, request.start_date, request.end_date)
    if df.empty:
        raise ValidationError(
            detail=(
                f"No kline data found for {request.stock_code} "
                "in the specified date range"
            )
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
        raise ValidationError(
            detail=f"Invalid metric '{request.metric}'. Valid: {valid_metrics}"
        )

    total_combinations = reduce(
        mul, (len(values) for values in request.param_grid.values()), 1
    )
    if total_combinations > settings.MAX_OPTIMIZE_COMBINATIONS:
        raise ValidationError(
            detail=(
                f"Parameter grid too large: {total_combinations} combinations. "
                f"Limit is {settings.MAX_OPTIMIZE_COMBINATIONS}."
            )
        )

    # Validate param_grid values against strategy parameter bounds
    strategy_class = get_strategy_class(request.strategy_name)
    strategy = strategy_class()
    strategy_params = strategy.get_parameters()
    for param_name, values in request.param_grid.items():
        param_def = strategy_params.get(param_name)
        if param_def is None:
            raise ValidationError(
                detail=(
                    f"Unknown parameter '{param_name}' for strategy "
                    f"'{request.strategy_name}'"
                )
            )
        for val in values:
            if param_def.min_value is not None and val < param_def.min_value:
                raise ValidationError(
                    detail=(
                        f"Parameter '{param_name}': value {val} is below "
                        f"minimum {param_def.min_value}"
                    )
                )
            if param_def.max_value is not None and val > param_def.max_value:
                raise ValidationError(
                    detail=(
                        f"Parameter '{param_name}': value {val} exceeds "
                        f"maximum {param_def.max_value}"
                    )
                )
            if param_def.choices and val not in param_def.choices:
                raise ValidationError(
                    detail=(
                        f"Parameter '{param_name}': value {val} is not in "
                        f"valid choices: {param_def.choices}"
                    )
                )

    return df


def _run_optimize(db: Session, request: OptimizeRequest) -> OptimizeResponse:
    """Execute a parameter grid search (shared by sync + async paths)."""
    df = _validate_optimize_request(db, request)

    optimizer = GridSearchOptimizer(initial_capital=request.initial_capital)

    try:
        result = optimizer.optimize(
            strategy_name=request.strategy_name,
            data=df,
            param_grid=request.param_grid,
            metric=request.metric,
        )
    except ValueError as exc:
        raise ValidationError(detail=str(exc)) from exc

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
    for strategy_class in strategies.values():
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
    """
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.code == request.stock_code).first()
    if not stock:
        raise NotFoundError(detail=f"Stock '{request.stock_code}' not found")

    # Get kline data
    df = get_kline_data(db, request.stock_code, request.start_date, request.end_date)
    if df.empty:
        raise ValidationError(
            detail=(
                f"No kline data found for {request.stock_code} "
                "in the specified date range"
            )
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

    except (ValueError, TypeError, KeyError):
        # Expected strategy-level issues (bad params, missing columns):
        # fall back to the built-in MA cross strategy instead of failing.
        logger.warning(
            "Strategy signal generation failed, falling back to MA cross",
            exc_info=True,
        )
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
    stats = compute_signal_stats(data)

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
            raise NotFoundError(detail=message) from exc
        raise ValidationError(detail=message) from exc

    try:
        persisted = BacktestExecutor(db).persist(execution)
    except Exception as exc:
        logger.exception("Failed to persist strategy backtest")
        raise ValidationError(detail="Backtest completed but could not be saved") from exc

    api_result = execution.to_api_dict()
    return BacktestResponse(
        success=True,
        result_id=persisted.id,
        strategy_name=execution.strategy_name,
        stock_code=execution.stock_code,
        start_date=execution.start_date,
        end_date=execution.end_date,
        initial_capital=execution.initial_capital,
        final_capital=execution.final_capital,
        trades=[BacktestTradeItem(**trade) for trade in api_result["trades"]],
        metrics=BacktestMetrics(**api_result["metrics"]),
        portfolio_values=[PortfolioValueItem(**pv) for pv in api_result["portfolio_values"]],
        parameters=execution.parameters,
    )


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_parameters(
    request: OptimizeRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """
    Optimize strategy parameters using grid search.
    """
    return _run_optimize(db, request)


@register_runner("strategy_optimize")
def run_optimize_job(job_id: str, payload: dict) -> None:
    """Background runner for /strategies/optimize/submit."""
    db = SessionLocal()
    try:
        request = OptimizeRequest(**payload)
        job_store.update(
            job_id, status="running", message="Optimizing strategy parameters"
        )
        response = _run_optimize(db, request)
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message="Optimization completed",
            result=response.model_dump(),
        )
    except Exception as exc:
        logger.exception(
            "Strategy optimization job failed", extra={"job_id": job_id}
        )
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
    _: str = Depends(get_current_api_key),
):
    job = get_task_executor().submit(
        job_type="strategy_optimize",
        payload=request.model_dump(mode="json"),
    )
    return OptimizeSubmitResponse(
        job_id=job.id, status=job.status, message="Optimization queued"
    )


# ==================== Strategy Comparison ====================


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

            # Reuse the executor's end-of-bar equity snapshots so comparison
            # curves include unrealized positions and match formal backtests.
            curve = [
                CompareStrategyCurve(
                    date=(pv.date.isoformat() if hasattr(pv.date, "isoformat") else str(pv.date)),
                    value=round(pv.total_value, 2),
                )
                for pv in execution.portfolio_values
            ]

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
            logger.warning(
                "Strategy '%s' comparison failed: %s", name, exc
            )
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
        curve.append(
            CompareStrategyCurve(date="end", value=round(final_capital, 2))
        )
    return curve
