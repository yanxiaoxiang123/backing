"""告警持久化模型（规格 v2 决策 24；US-3.4）。

告警落库并可关联 run/数据事件；阈值可配置；面板展示 + 已读状态。
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.config import Base

ALERT_TYPES = "('drawdown', 'data_staleness', 'provider_failure', 'cost_anomaly', 'signal_drift')"
ALERT_SEVERITIES = "('info', 'warning', 'critical')"


class AlertRecord(Base):
    """一条告警（US-3.4）：类型/级别/消息 + run/数据事件关联。"""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(30), nullable=False)
    severity = Column(String(10), nullable=False, default="warning")
    message = Column(Text, nullable=False)
    run_id = Column(String(64), nullable=True, index=True)
    data_ref = Column(String(255), nullable=True)
    value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    is_read = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"alert_type IN {ALERT_TYPES}", name="ck_alerts_type"),
        CheckConstraint(
            f"severity IN {ALERT_SEVERITIES}", name="ck_alerts_severity"
        ),
    )
