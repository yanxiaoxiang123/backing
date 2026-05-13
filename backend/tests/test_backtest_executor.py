from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.models.models import DailyKline, Stock
from app.services.backtest_executor import BacktestExecutor
import app.services.strategy  # noqa: F401


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
