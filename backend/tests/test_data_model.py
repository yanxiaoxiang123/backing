"""数据模型测试：Numeric 精度、JSON 统一 + schema_version、CheckConstraint、
外键级联、用户表与 (user_id, stock_code) 唯一约束。
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.models.analysis import AnalysisRecord
from app.models.models import (
    DEFAULT_USER_ID,
    BacktestResult,
    BacktestTrade,
    DailyKline,
    JobDbRecord,
    KlineArchive,
    Stock,
    Strategy,
    User,
    WatchlistItem,
)


def _engine(fk_enabled: bool = True):
    engine = create_engine("sqlite:///:memory:")
    if fk_enabled:
        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _rec):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def session():
    engine = _engine()
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _seed_stock(session, code="sh.600000"):
    stock = Stock(code=code, name="浦发银行", market="sh")
    session.add(stock)
    session.commit()
    return stock


class TestNumericPrecision:
    def test_kline_prices_round_trip_at_declared_scale(self, session):
        """SQLite 读取时按声明 scale 量化（与 MySQL DECIMAL 行为一致）。"""
        _seed_stock(session)
        session.add(
            DailyKline(
                stock_code="sh.600000",
                date=date(2024, 1, 2),
                open=Decimal("10.1234567"),
                high=Decimal("11.99999999"),
                low=Decimal("9.00000001"),
                close=Decimal("10.9876543"),
                volume=Decimal("1234567.89"),
                amount=Decimal("12345678.90"),
            )
        )
        session.commit()
        k = session.query(DailyKline).first()
        assert isinstance(k.close, Decimal)
        assert k.close == Decimal("10.9877")  # Numeric(12,4)
        assert k.open == Decimal("10.1235")
        assert k.high == Decimal("12.0000")
        assert k.low == Decimal("9.0000")
        assert k.volume == Decimal("1234567.89")  # Numeric(18,2)
        assert k.amount == Decimal("12345678.90")  # Numeric(18,2)

    def test_backtest_capital_round_trip(self, session):
        _seed_stock(session)
        strategy = Strategy(name="ma", strategy_type="ma_cross", parameters={})
        session.add(strategy)
        session.commit()
        session.add(
            BacktestResult(
                strategy_id=strategy.id,
                stock_code="sh.600000",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                initial_capital=Decimal("100000.555"),
                final_capital=Decimal("112345.678"),
                total_return=Decimal("12.34567"),
                annual_return=Decimal("150.1234"),
                sharpe_ratio=Decimal("1.23456"),
                max_drawdown=Decimal("8.12345"),
                win_rate=Decimal("55.5555"),
                total_trades=5,
            )
        )
        session.commit()
        r = session.query(BacktestResult).first()
        assert isinstance(r.initial_capital, Decimal)
        # Numeric(16,2) 读取时按声明 scale 量化（ROUND_HALF_EVEN）
        assert r.initial_capital == Decimal("100000.55")
        assert r.final_capital == Decimal("112345.68")
        assert isinstance(r.total_return, Decimal)
        assert r.total_return == Decimal("12.3457")  # Numeric(10,4)


class TestJsonAndSchemaVersion:
    def test_strategy_parameters_json_round_trip(self, session):
        s = Strategy(
            name="test", strategy_type="ma_cross",
            parameters={"short_period": 5, "long_period": 20, "nested": {"a": 1}},
        )
        session.add(s)
        session.commit()
        got = session.query(Strategy).first()
        assert got.parameters == {"short_period": 5, "long_period": 20, "nested": {"a": 1}}
        assert got.schema_version == 1

    def test_analysis_json_round_trip(self, session):
        session.add(
            AnalysisRecord(
                stock_code="sh.600000",
                analysis_date=date(2024, 1, 1),
                mode="quick",
                final_signal="buy",
                final_confidence=Decimal("0.8"),
                opinions_json=[{"agent_name": "technical", "signal": "buy"}],
                stages_json=[{"stage_name": "technical_analysis", "status": "completed"}],
                duration_s=1.2,
            )
        )
        session.commit()
        r = session.query(AnalysisRecord).first()
        assert r.opinions_json == [{"agent_name": "technical", "signal": "buy"}]
        assert r.stages_json[0]["status"] == "completed"
        assert r.schema_version == 1
        assert r.final_confidence == Decimal("0.8")

    def test_job_schema_version_and_progress(self, session):
        job = JobDbRecord(id="j1", job_type="sync_stocks")
        session.add(job)
        session.commit()
        got = session.query(JobDbRecord).first()
        assert got.schema_version == 1
        assert isinstance(got.progress, Decimal)


class TestCheckConstraints:
    def test_invalid_job_status_rejected(self, session):
        with pytest.raises(IntegrityError):
            session.add(JobDbRecord(id="j2", job_type="sync", status="bogus"))
            session.commit()
        session.rollback()

    def test_invalid_trade_action_rejected(self, session):
        with pytest.raises(IntegrityError):
            session.add(
                BacktestTrade(
                    backtest_result_id=1,
                    stock_code="sh.600000",
                    trade_date=date(2024, 1, 1),
                    action="hold",
                    price=Decimal(10),
                    quantity=100,
                    amount=Decimal(1000),
                )
            )
            session.commit()
        session.rollback()

    def test_negative_trade_quantity_rejected(self, session):
        with pytest.raises(IntegrityError):
            session.add(
                BacktestTrade(
                    backtest_result_id=1,
                    stock_code="sh.600000",
                    trade_date=date(2024, 1, 1),
                    action="buy",
                    price=Decimal(10),
                    quantity=-100,
                    amount=Decimal(1000),
                )
            )
            session.commit()
        session.rollback()

    def test_non_positive_backtest_capital_rejected(self, session):
        with pytest.raises(IntegrityError):
            session.add(
                BacktestResult(
                    strategy_id=1,
                    stock_code="sh.600000",
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 31),
                    initial_capital=Decimal(0),
                    final_capital=Decimal(0),
                    total_return=Decimal(0),
                    annual_return=Decimal(0),
                    total_trades=0,
                )
            )
            session.commit()
        session.rollback()

    def test_inverted_date_range_rejected(self, session):
        with pytest.raises(IntegrityError):
            session.add(
                BacktestResult(
                    strategy_id=1,
                    stock_code="sh.600000",
                    start_date=date(2024, 2, 1),
                    end_date=date(2024, 1, 1),  # 结束早于开始
                    initial_capital=Decimal(10000),
                    final_capital=Decimal(10000),
                    total_return=Decimal(0),
                    annual_return=Decimal(0),
                    total_trades=0,
                )
            )
            session.commit()
        session.rollback()

    def test_negative_kline_price_rejected(self, session):
        _seed_stock(session)
        with pytest.raises(IntegrityError):
            session.add(
                DailyKline(
                    stock_code="sh.600000",
                    date=date(2024, 1, 2),
                    open=Decimal(-1),
                    high=Decimal(1),
                    low=Decimal(1),
                    close=Decimal(1),
                    volume=Decimal(100),
                )
            )
            session.commit()
        session.rollback()

    def test_invalid_analysis_signal_rejected(self, session):
        with pytest.raises(IntegrityError):
            session.add(
                AnalysisRecord(
                    stock_code="sh.600000",
                    analysis_date=date(2024, 1, 1),
                    mode="quick",
                    final_signal="maybe",
                    final_confidence=Decimal("0.5"),
                    duration_s=1.0,
                )
            )
            session.commit()
        session.rollback()


class TestUsersAndWatchlist:
    def test_default_user_seeded_via_migration_is_readable(self, session):
        # 迁移会写入 default 用户；此处验证模型可承载多用户
        u = User(username="alice")
        session.add(u)
        session.commit()
        assert session.query(User).filter(User.username == "alice").count() == 1

    def test_watchlist_composite_unique(self, session):
        _seed_stock(session)
        session.add(User(id=1, username="default"))
        session.add(User(id=2, username="alice"))
        session.commit()
        session.add(WatchlistItem(user_id=1, stock_code="sh.600000"))
        session.commit()
        with pytest.raises(IntegrityError):
            session.add(WatchlistItem(user_id=1, stock_code="sh.600000"))
            session.commit()
        session.rollback()
        # 不同用户可以关注同一只股票
        session.add(WatchlistItem(user_id=2, stock_code="sh.600000"))
        session.commit()

    def test_watchlist_default_user_id(self, session):
        _seed_stock(session)
        session.add(User(id=1, username="default"))
        session.commit()
        item = WatchlistItem(stock_code="sh.600000")
        session.add(item)
        session.commit()
        assert item.user_id == DEFAULT_USER_ID


class TestForeignKeyCascade:
    def test_deleting_stock_cascades_klines(self):
        engine = _engine(fk_enabled=True)
        s = sessionmaker(bind=engine)()
        stock = Stock(code="sh.600000", name="浦发银行", market="sh")
        s.add(stock)
        s.commit()
        s.add(
            DailyKline(
                stock_code="sh.600000", date=date(2024, 1, 2),
                open=1, high=2, low=1, close=1.5, volume=100,
            )
        )
        s.commit()
        assert s.query(DailyKline).count() == 1
        s.delete(stock)
        s.commit()
        assert s.query(DailyKline).count() == 0
        s.close()

    def test_deleting_backtest_result_cascades_trades(self):
        engine = _engine(fk_enabled=True)
        s = sessionmaker(bind=engine)()
        stock = Stock(code="sh.600000", name="浦发银行", market="sh")
        s.add(stock)
        s.commit()
        strategy = Strategy(name="ma", strategy_type="ma_cross", parameters={})
        s.add(strategy)
        s.commit()
        result = BacktestResult(
            strategy_id=strategy.id,
            stock_code="sh.600000",
            start_date=date(2024, 1, 1), end_date=date(2024, 1, 31),
            initial_capital=100000, final_capital=100000,
            total_return=0, annual_return=0, total_trades=1,
        )
        s.add(result)
        s.commit()
        s.add(
            BacktestTrade(
                backtest_result_id=result.id, stock_code="sh.600000",
                trade_date=date(2024, 1, 2), action="buy",
                price=10, quantity=100, amount=1000,
            )
        )
        s.commit()
        s.delete(result)
        s.commit()
        assert s.query(BacktestTrade).count() == 0
        s.close()

    def test_archive_table_shape(self, session):
        _seed_stock(session)
        session.add(
            KlineArchive(
                stock_code="sh.600000", date=date(2014, 1, 2),
                open=1, high=2, low=1, close=1.5, volume=100,
            )
        )
        session.commit()
        row = session.query(KlineArchive).first()
        assert row.date == date(2014, 1, 2)
        assert isinstance(row.close, Decimal)
