"""分析记录表模型"""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.config import Base


class AnalysisRecord(Base):
    """股票分析记录"""

    __tablename__ = "analysis_records"

    id = Column(Integer, primary_key=True, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(100), nullable=True)
    analysis_date = Column(Date, nullable=False, index=True)
    mode = Column(String(20), nullable=False)  # quick/standard/full/strategy

    # 最终决策
    final_signal = Column(String(10), nullable=False)  # buy/sell/hold
    final_confidence = Column(Numeric(5, 4), nullable=False)  # 0-1 置信度
    final_reason = Column(Text, nullable=True)

    # 详细结果（JSON，schema v1）
    opinions_json = Column(JSON, nullable=True)  # 各 Agent 意见
    stages_json = Column(JSON, nullable=True)  # 各阶段结果
    schema_version = Column(Integer, nullable=False, server_default="1", default=1)

    # 元数据
    duration_s = Column(Float, nullable=False)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_analysis_stock_date", "stock_code", "analysis_date"),
        CheckConstraint(
            "final_signal IN ('buy', 'sell', 'hold')",
            name="ck_analysis_final_signal",
        ),
    )
