"""Append-only saved portfolio input/result snapshots."""

from sqlalchemy import JSON, Column, DateTime, Index, String, func

from app.config import Base


class PortfolioExperiment(Base):
    __tablename__ = "portfolio_experiments"

    experiment_id = Column(String(32), primary_key=True)
    owner = Column(String(100), nullable=False)
    name = Column(String(120), nullable=False)
    engine_version = Column(String(40), nullable=False)
    snapshot_sha256 = Column(String(64), nullable=False)
    result_sha256 = Column(String(64), nullable=False)
    snapshot = Column(JSON, nullable=False)
    result = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_portfolio_experiments_owner_created", "owner", "created_at"),)
