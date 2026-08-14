from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.config import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    market = Column(String(20), nullable=False)  # sh, sz
    list_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    klines = relationship("DailyKline", back_populates="stock")
    backtest_trades_list = relationship("BacktestTrade", back_populates="stock")
    backtest_results = relationship("BacktestResult", back_populates="stock")
    watchlist_items = relationship("WatchlistItem", back_populates="stock")


class DailyKline(Base):
    __tablename__ = "daily_klines"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(
        String(20), ForeignKey("stocks.code"), nullable=False, index=True
    )
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    amount = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    stock = relationship("Stock", back_populates="klines")

    __table_args__ = (Index("idx_stock_date", "stock_code", "date", unique=True),)


class WatchlistItem(Base):
    __tablename__ = "user_watchlist"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(
        String(20), ForeignKey("stocks.code"), nullable=False, unique=True, index=True
    )
    added_at = Column(DateTime, server_default=func.now())

    stock = relationship("Stock")

    __table_args__ = (Index("idx_added_at", "added_at"),)


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(50), nullable=False)  # ma_cross, mean_reversion
    parameters = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    backtest_results = relationship("BacktestResult", back_populates="strategy")


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    stock_code = Column(String(20), ForeignKey("stocks.code"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_capital = Column(Float, nullable=False)
    total_return = Column(Float, nullable=False)  # percentage
    annual_return = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    strategy = relationship("Strategy", back_populates="backtest_results")
    stock = relationship("Stock", back_populates="backtest_results")
    trades = relationship("BacktestTrade", back_populates="backtest_result")

    __table_args__ = (
        Index("idx_backtest_stock_created", "stock_code", "created_at"),
    )


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id = Column(Integer, primary_key=True, index=True)
    backtest_result_id = Column(
        Integer, ForeignKey("backtest_results.id"), nullable=False
    )
    stock_code = Column(String(20), ForeignKey("stocks.code"), nullable=False)
    trade_date = Column(Date, nullable=False)
    action = Column(String(10), nullable=False)  # buy, sell
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    backtest_result = relationship("BacktestResult", back_populates="trades")
    stock = relationship("Stock", back_populates="backtest_trades_list")

    __table_args__ = (
        Index("idx_backtest_trades_result_stock", "backtest_result_id", "stock_code"),
    )


class JobDbRecord(Base):
    """Persistent job record for async task tracking."""

    __tablename__ = "jobs"
    __table_args__ = (Index("uq_jobs_job_key", "job_key", unique=True),)

    id = Column(String(36), primary_key=True)
    job_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    message = Column(Text, nullable=False, default="")
    progress = Column(Float, nullable=False, default=0.0)
    payload = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    # Idempotency key: a client submitting the same logical work twice gets
    # the same job back (unique, NULL allowed).
    job_key = Column(String(100), nullable=True)
    # Retry bookkeeping for transient (provider) failures.
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=0)
    # Lease: refreshed by the executing worker's heartbeat; an expired lease
    # on a "running" job means the executor died and the job can be reclaimed.
    lease_until = Column(DateTime, nullable=True)
    # Retries: only jobs with next_retry_at <= now are claimable again.
    next_retry_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
