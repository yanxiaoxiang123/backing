from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.strategy  # noqa: F401
from app.config import Base
from app.models.models import DailyKline, Stock
from app.services.backtest_executor import BacktestExecutor
from app.services.strategy.optimizer import GridSearchOptimizer
from app.services.strategy.registry import StrategyRegistry
from app.services.strategy.signals import get_kline_data


def build_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def seed_market_data(session):
    session.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    start = date(2024, 1, 1)
    closes = [10, 10.2, 10.5, 10.9, 11.2, 10.8, 10.4, 10.0, 9.8, 10.3, 10.9, 11.4]
    for idx, close in enumerate(closes):
        session.add(
            DailyKline(
                stock_code="sh.600000",
                date=start + timedelta(days=idx),
                open=close - 0.1,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=100000 + idx * 1000,
                amount=close * 100000,
            )
        )
    session.commit()


def test_backtest_executor_runs_strategy_and_returns_normalized_metrics():
    session = build_session()
    seed_market_data(session)

    result = BacktestExecutor(session).execute(
        strategy_name="ma_cross",
        stock_code="sh.600000",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 12),
        initial_capital=100000,
        parameters={"short_period": 2, "long_period": 3},
    )

    assert result.strategy_name == "ma_cross"
    assert result.stock_code == "sh.600000"
    assert result.final_capital > 0
    assert result.metrics.total_trades >= 0
    assert all(trade.action in {"buy", "sell"} for trade in result.trades)


def test_backtest_executor_persists_reproducible_snapshot():
    session = build_session()
    seed_market_data(session)

    executor = BacktestExecutor(session)
    execution = executor.execute(
        strategy_name="ma_cross",
        stock_code="sh.600000",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 12),
        initial_capital=100000,
        parameters={"short_period": 2, "long_period": 3},
    )
    saved = executor.persist(execution)

    assert saved.id is not None
    assert saved.parameters == {"short_period": 2, "long_period": 3}
    assert saved.portfolio_values
    assert saved.portfolio_values[-1]["total_value"] == execution.final_capital
    assert len(saved.trades) == len(execution.trades)


def test_all_registered_strategies_accept_numeric_database_values():
    session = build_session()
    session.add(Stock(code="sz.000001", name="平安银行", market="sz"))
    start = date(2024, 1, 1)
    for idx in range(180):
        close = 10 + (idx % 30) * 0.08 + ((idx % 7) - 3) * 0.03
        session.add(
            DailyKline(
                stock_code="sz.000001",
                date=start + timedelta(days=idx),
                open=close - 0.05,
                high=close + 0.15,
                low=close - 0.15,
                close=close,
                volume=100000 + (idx % 20) * 5000,
                amount=close * 100000,
            )
        )
    session.commit()

    executor = BacktestExecutor(session)
    for strategy_name in StrategyRegistry.list_strategies():
        result = executor.execute(
            strategy_name=strategy_name,
            stock_code="sz.000001",
            start_date=start,
            end_date=start + timedelta(days=179),
        )
        assert result.strategy_name == strategy_name


def test_optimizer_receives_float_market_data_from_numeric_columns():
    session = build_session()
    seed_market_data(session)
    data = get_kline_data(
        session, "sh.600000", date(2024, 1, 1), date(2024, 1, 12)
    )

    assert all(str(data[column].dtype) == "float64" for column in ["open", "close", "volume"])
    result = GridSearchOptimizer().optimize(
        strategy_name="ma_cross",
        data=data,
        param_grid={"short_period": [2, 3], "long_period": [4, 5]},
        metric="sharpe_ratio",
    )
    assert result.total_combinations == 4
    assert result.best_params is not None
