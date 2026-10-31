"""Append-only market observations; valid time and observation time stay distinct."""

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, String, UniqueConstraint,
)

from app.config import Base


class MarketDataBatch(Base):
    __tablename__ = "market_data_batches"

    batch_id = Column(String(64), primary_key=True)
    stock_code = Column(String(20), nullable=False)
    provider = Column(String(50), nullable=False)
    adjustment = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    observed_at = Column(DateTime, nullable=False)
    checksum = Column(String(64), nullable=False)
    row_count = Column(Integer, nullable=False)
    schema_version = Column(Integer, nullable=False, default=1, server_default="1")
    __table_args__ = (
        Index("ix_market_batch_security_observed", "stock_code", "observed_at"),
        CheckConstraint("adjustment IN ('raw','qfq','hfq','legacy_unknown')", name="ck_market_batch_adjustment"),
        CheckConstraint("row_count > 0 AND start_date <= end_date", name="ck_market_batch_range"),
    )


class MarketDailyBar(Base):
    __tablename__ = "market_daily_bars"

    batch_id = Column(String(64), ForeignKey("market_data_batches.batch_id", name="fk_market_bar_batch", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, primary_key=True)
    open = Column(Numeric(16, 6), nullable=False)
    high = Column(Numeric(16, 6), nullable=False)
    low = Column(Numeric(16, 6), nullable=False)
    close = Column(Numeric(16, 6), nullable=False)
    volume = Column(Numeric(22, 2), nullable=False)
    amount = Column(Numeric(22, 2), nullable=True)
    suspended = Column(Boolean, nullable=False, default=False, server_default="0")
    is_st = Column(Boolean, nullable=True)
    __table_args__ = (
        CheckConstraint("open > 0 AND close > 0 AND low > 0 AND high >= open AND high >= close AND low <= open AND low <= close AND volume >= 0", name="ck_market_bar_ohlcv"),
    )


class TradingSession(Base):
    __tablename__ = "trading_sessions"

    exchange = Column(String(8), primary_key=True)
    date = Column(Date, primary_key=True)
    is_open = Column(Boolean, nullable=False)
    provider = Column(String(50), nullable=False)
    observed_at = Column(DateTime, nullable=False)


class SecuritySessionObservation(Base):
    """Explicit provider status; never inferred from a missing price candle."""

    __tablename__ = "security_session_observations"

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False)
    date = Column(Date, nullable=False)
    suspended = Column(Boolean, nullable=False)
    provider = Column(String(50), nullable=False)
    observed_at = Column(DateTime, nullable=False)
    checksum = Column(String(64), nullable=False)
    __table_args__ = (
        UniqueConstraint("stock_code", "date", "provider", "observed_at", "checksum", name="uq_security_session_observation"),
        Index("ix_security_session_asof", "stock_code", "date", "observed_at"),
    )


class SecurityObservation(Base):
    __tablename__ = "security_observations"

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False)
    effective_date = Column(Date, nullable=False)
    observed_at = Column(DateTime, nullable=False)
    name = Column(String(100), nullable=False)
    listed_on = Column(Date, nullable=True)
    delisted_on = Column(Date, nullable=True)
    status = Column(String(20), nullable=False)
    provider = Column(String(50), nullable=False)
    checksum = Column(String(64), nullable=False)
    __table_args__ = (
        UniqueConstraint("stock_code", "checksum", name="uq_security_observation"),
        Index("ix_security_observation_asof", "stock_code", "observed_at", "effective_date"),
    )


class MarketMetadataBatch(Base):
    """Complete provider response, including an explicitly empty response."""

    __tablename__ = "market_metadata_batches"

    batch_id = Column(String(64), primary_key=True)
    stock_code = Column(String(20), nullable=False)
    kind = Column(String(30), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    observed_at = Column(DateTime, nullable=False)
    provider = Column(String(50), nullable=False)
    checksum = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="ck_market_metadata_range"),
        CheckConstraint("kind IN ('adjustment_factor','dividend')", name="ck_market_metadata_kind"),
        Index("ix_market_metadata_asof", "stock_code", "kind", "observed_at"),
    )


class CorporateActionObservation(Base):
    __tablename__ = "corporate_action_observations"

    id = Column(Integer, primary_key=True)
    stock_code = Column(String(20), nullable=False)
    effective_date = Column(Date, nullable=False)
    # NULL means no verifiable publication timestamp, never guessed from ex-date.
    announced_at = Column(DateTime, nullable=True)
    observed_at = Column(DateTime, nullable=False)
    kind = Column(String(30), nullable=False)
    provider = Column(String(50), nullable=False)
    checksum = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (
        UniqueConstraint("stock_code", "kind", "checksum", name="uq_corporate_action_observation"),
        Index("ix_corporate_action_asof", "stock_code", "effective_date", "observed_at"),
    )
