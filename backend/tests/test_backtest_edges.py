"""回测执行器边界测试：空数据、未知标的/策略、非法资金、无交易。

使用内存 SQLite（单线程测试，无需跨线程共享）。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.strategy  # noqa: F401  (register strategies)
from app.config import Base
from app.models.models import DailyKline, Stock
from app.services.backtest_executor import BacktestExecutor
from datetime import date, timedelta


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)()


def seed(session, stock_code="sh.600000", closes=(10.0, 10.2, 10.5, 10.9, 11.2)):
    session.add(Stock(code=stock_code, name="测试", market="sh"))
    start = date(2024, 1, 1)
    for idx, close in enumerate(closes):
        session.add(
            DailyKline(
                stock_code=stock_code,
                date=start + timedelta(days=idx),
                open=close - 0.1,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=100000 + idx,
                amount=close * 100000,
            )
        )
    session.commit()


class TestValidationEdges:
    def test_unknown_stock_raises_value_error(self, session):
        with pytest.raises(ValueError, match="not found"):
            BacktestExecutor(session).execute(
                strategy_name="ma_cross",
                stock_code="sh.999999",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 5),
            )

    def test_unknown_strategy_raises_value_error(self, session):
        seed(session)
        with pytest.raises(ValueError, match="Strategy"):
            BacktestExecutor(session).execute(
                strategy_name="nope",
                stock_code="sh.600000",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 5),
            )

    def test_empty_kline_raises_value_error(self, session):
        session.add(Stock(code="sh.600001", name="无数据", market="sh"))
        session.commit()
        with pytest.raises(ValueError, match="No kline data"):
            BacktestExecutor(session).execute(
                strategy_name="ma_cross",
                stock_code="sh.600001",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 5),
            )

    def test_zero_initial_capital_raises_value_error(self, session):
        seed(session)
        with pytest.raises(ValueError, match="initial_capital must be positive"):
            BacktestExecutor(session).execute(
                strategy_name="ma_cross",
                stock_code="sh.600000",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 5),
                initial_capital=0,
            )

    def test_negative_initial_capital_raises_value_error(self, session):
        seed(session)
        with pytest.raises(ValueError, match="initial_capital must be positive"):
            BacktestExecutor(session).execute(
                strategy_name="ma_cross",
                stock_code="sh.600000",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 5),
                initial_capital=-100,
            )


class TestExecutionEdges:
    def test_capital_too_small_for_one_lot_no_trades(self, session):
        """资金买不起 1 手（100 股）时不应产生交易，资金不变。"""
        seed(session, closes=(100.0, 100.5, 101.0, 101.5, 102.0))
        result = BacktestExecutor(session).execute(
            strategy_name="ma_cross",
            stock_code="sh.600000",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 5),
            initial_capital=5000,  # 买不起 1 手（100 股 × 100 元）
            parameters={"short_period": 1, "long_period": 2},
        )
        assert result.trades == []
        assert result.final_capital == pytest.approx(5000)
        assert result.metrics.total_trades == 0

    def test_single_bar_series_metrics_are_finite(self, session):
        """只有一根 K 线时指标仍应有限值（不炸）。"""
        seed(session, closes=(10.0,))
        result = BacktestExecutor(session).execute(
            strategy_name="ma_cross",
            stock_code="sh.600000",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 5),
        )
        assert result.trades == []
        assert result.metrics.total_trades == 0
        assert result.metrics.total_return == pytest.approx(0.0)
        assert result.metrics.max_drawdown >= 0

    def test_buy_then_sell_closes_position(self, session):
        # 10→11→12 上升触发买入，11→10 回落触发卖出
        seed(session, closes=(10.0, 11.0, 12.0, 11.0, 10.0))
        result = BacktestExecutor(session).execute(
            strategy_name="ma_cross",
            stock_code="sh.600000",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 5),
            initial_capital=100000,
            parameters={"short_period": 1, "long_period": 2},
        )
        actions = [t.action for t in result.trades]
        assert "buy" in actions
        assert "sell" in actions
        # 买入卖出数量守恒
        buys = [t for t in result.trades if t.action == "buy"]
        sells = [t for t in result.trades if t.action == "sell"]
        assert sum(t.quantity for t in buys) == sum(t.quantity for t in sells)
        assert all(t.quantity % 100 == 0 for t in result.trades)  # 整手

    def test_portfolio_values_match_capital_tracking(self, session):
        # 序列以卖出收尾（收盘即平仓），现金口径与组合市值一致
        seed(session, closes=(10.0, 11.0, 12.0, 11.0, 10.0))
        result = BacktestExecutor(session).execute(
            strategy_name="ma_cross",
            stock_code="sh.600000",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 5),
            initial_capital=100000,
            parameters={"short_period": 1, "long_period": 2},
        )
        assert result.portfolio_values
        assert result.portfolio_values[0].total_value == pytest.approx(100000)
        last = result.portfolio_values[-1]
        assert last.total_value == pytest.approx(result.final_capital)
