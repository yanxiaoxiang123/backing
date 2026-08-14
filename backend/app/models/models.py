from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.config import Base

# 单用户模式下的默认用户 id（多用户就绪：user_watchlist 按 user_id 隔离）。
DEFAULT_USER_ID = 1


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    watchlist_items = relationship("WatchlistItem", back_populates="user")


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    market = Column(String(20), nullable=False)  # sh, sz
    list_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    klines = relationship("DailyKline", back_populates="stock", passive_deletes=True)
    backtest_trades_list = relationship(
        "BacktestTrade", back_populates="stock", passive_deletes=True
    )
    backtest_results = relationship(
        "BacktestResult", back_populates="stock", passive_deletes=True
    )
    watchlist_items = relationship(
        "WatchlistItem", back_populates="stock", passive_deletes=True
    )


class DailyKline(Base):
    """日 K 线。

    价格列使用 Numeric(12,4)（元）、成交量 Numeric(18,2)（股）、
    成交额 Numeric(18,2)（元），避免 Float 累计舍入误差。
    """

    __tablename__ = "daily_klines"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(
        String(20),
        ForeignKey("stocks.code", name="fk_daily_klines_stock_code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False, index=True)
    open = Column(Numeric(12, 4), nullable=False)  # 元
    high = Column(Numeric(12, 4), nullable=False)  # 元
    low = Column(Numeric(12, 4), nullable=False)  # 元
    close = Column(Numeric(12, 4), nullable=False)  # 元
    volume = Column(Numeric(18, 2), nullable=False)  # 股
    amount = Column(Numeric(18, 2), nullable=True)  # 元
    created_at = Column(DateTime, server_default=func.now())

    stock = relationship("Stock", back_populates="klines")

    __table_args__ = (
        Index("idx_stock_date", "stock_code", "date", unique=True),
        CheckConstraint(
            "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0 AND volume >= 0 "
            "AND (amount IS NULL OR amount >= 0)",
            name="ck_daily_klines_nonneg",
        ),
    )


class KlineArchive(Base):
    """归档 K 线（数据生命周期：超过保留期的 K 线由 maintenance 移入）。"""

    __tablename__ = "daily_klines_archive"

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Numeric(12, 4), nullable=False)
    high = Column(Numeric(12, 4), nullable=False)
    low = Column(Numeric(12, 4), nullable=False)
    close = Column(Numeric(12, 4), nullable=False)
    volume = Column(Numeric(18, 2), nullable=False)
    amount = Column(Numeric(18, 2), nullable=True)
    archived_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_archive_stock_date", "stock_code", "date"),
    )


class WatchlistItem(Base):
    __tablename__ = "user_watchlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", name="fk_watchlist_user_id", ondelete="CASCADE"),
        nullable=False,
        default=DEFAULT_USER_ID,
    )
    stock_code = Column(
        String(20),
        ForeignKey("stocks.code", name="fk_watchlist_stock_code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    added_at = Column(DateTime, server_default=func.now())

    stock = relationship("Stock")
    user = relationship("User", back_populates="watchlist_items")

    __table_args__ = (
        Index("idx_added_at", "added_at"),
        Index("uq_watchlist_user_stock", "user_id", "stock_code", unique=True),
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(50), nullable=False)  # ma_cross, mean_reversion
    parameters = Column(JSON, nullable=True)  # 策略参数字典（schema v1）
    schema_version = Column(Integer, nullable=False, server_default="1", default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    backtest_results = relationship("BacktestResult", back_populates="strategy")


class BacktestResult(Base):
    """回测结果。

    金额列 Numeric(16,2)（元）；total_return / annual_return / max_drawdown /
    win_rate 为百分比（%）；sharpe_ratio / profit_factor 为无量纲比率。
    """

    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(
        Integer,
        ForeignKey(
            "strategies.id",
            name="fk_backtest_results_strategy_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    stock_code = Column(
        String(20),
        ForeignKey("stocks.code", name="fk_backtest_results_stock_code", ondelete="CASCADE"),
        nullable=False,
    )
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Numeric(16, 2), nullable=False)  # 元
    final_capital = Column(Numeric(16, 2), nullable=False)  # 元
    total_return = Column(Numeric(10, 4), nullable=False)  # 百分比 %
    annual_return = Column(Numeric(10, 4), nullable=False)  # 百分比 %
    sharpe_ratio = Column(Numeric(10, 4), nullable=True)  # 无量纲
    max_drawdown = Column(Numeric(10, 4), nullable=True)  # 百分比 %
    win_rate = Column(Numeric(10, 4), nullable=True)  # 百分比 %
    total_trades = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    strategy = relationship("Strategy", back_populates="backtest_results")
    stock = relationship("Stock", back_populates="backtest_results")
    trades = relationship("BacktestTrade", back_populates="backtest_result", passive_deletes=True)

    __table_args__ = (
        Index("idx_backtest_stock_created", "stock_code", "created_at"),
        CheckConstraint(
            "initial_capital > 0 AND final_capital >= 0",
            name="ck_backtest_results_capital",
        ),
        CheckConstraint("start_date <= end_date", name="ck_backtest_results_date_range"),
        CheckConstraint("total_trades >= 0", name="ck_backtest_results_trades_nonneg"),
    )


class BacktestTrade(Base):
    """回测交易记录。

    价格 Numeric(12,4)、金额 Numeric(16,2)；action 限 buy/sell，
    数量与金额非负。
    """

    __tablename__ = "backtest_trades"

    id = Column(Integer, primary_key=True, index=True)
    backtest_result_id = Column(
        Integer,
        ForeignKey(
            "backtest_results.id",
            name="fk_backtest_trades_result_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    stock_code = Column(
        String(20),
        ForeignKey("stocks.code", name="fk_backtest_trades_stock_code", ondelete="CASCADE"),
        nullable=False,
    )
    trade_date = Column(Date, nullable=False)
    action = Column(String(10), nullable=False)  # buy, sell
    price = Column(Numeric(12, 4), nullable=False)  # 元
    quantity = Column(Integer, nullable=False)  # 股（整手）
    amount = Column(Numeric(16, 2), nullable=False)  # 元
    created_at = Column(DateTime, server_default=func.now())

    backtest_result = relationship("BacktestResult", back_populates="trades")
    stock = relationship("Stock", back_populates="backtest_trades_list")

    __table_args__ = (
        Index("idx_backtest_trades_result_stock", "backtest_result_id", "stock_code"),
        CheckConstraint("action IN ('buy', 'sell')", name="ck_backtest_trades_action"),
        CheckConstraint("price >= 0", name="ck_backtest_trades_price_nonneg"),
        CheckConstraint("quantity >= 0", name="ck_backtest_trades_quantity_nonneg"),
        CheckConstraint("amount >= 0", name="ck_backtest_trades_amount_nonneg"),
    )


class JobDbRecord(Base):
    """Persistent job record for async task tracking."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("uq_jobs_job_key", "job_key", unique=True),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
    )

    id = Column(String(36), primary_key=True)
    job_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    message = Column(Text, nullable=False, default="")
    progress = Column(Numeric(5, 4), nullable=False, default=0.0)  # 0-1 进度
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
    # payload/result 的 schema 版本，读取端应先检查。
    schema_version = Column(Integer, nullable=False, server_default="1", default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
