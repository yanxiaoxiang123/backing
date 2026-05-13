# -*- coding: utf-8 -*-
"""分析记录表模型"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text
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
    final_confidence = Column(Float, nullable=False)
    final_reason = Column(Text, nullable=True)

    # 详细结果 (JSON)
    opinions_json = Column(Text, nullable=True)  # 各 Agent 意见
    stages_json = Column(Text, nullable=True)  # 各阶段结果

    # 元数据
    duration_s = Column(Float, nullable=False)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
