"""告警服务（规格 v2 决策 24；US-3.4）。

确定性条件检查 + 落库（同日同条件去重）：
- drawdown：组合权益自峰值回撤超阈值（默认 20%）
- data_staleness：已同步股票最新 K 线早于 N 天（默认 3）
- provider_failure：近窗口内工具调用失败数超阈值（默认 3）
- cost_anomaly：单日费用超阈值（默认 500 元）

阈值可配置（check_alerts 参数/环境变量）；每条告警可关联 run/数据事件。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_runtime import ToolCallRecord
from app.models.alerts import AlertRecord
from app.models.models import DailyKline, Stock

logger = logging.getLogger(__name__)

DEFAULT_DRAWDOWN_THRESHOLD = 0.20
DEFAULT_STALENESS_DAYS = 3
DEFAULT_PROVIDER_FAILURES = 3
DEFAULT_COST_THRESHOLD = 500.0


@dataclass(frozen=True)
class AlertDraft:
    alert_type: str
    severity: str
    message: str
    data_ref: str | None = None
    run_id: str | None = None
    value: float | None = None
    threshold: float | None = None


def _day_key(dt: datetime) -> str:
    return dt.date().isoformat()


def _exists_today(
    db: Session, alert_type: str, data_ref: str | None
) -> bool:
    """同日同条件去重（避免告警风暴）。"""
    today_start = f"{date.today().isoformat()} 00:00:00"
    row = (
        db.query(AlertRecord.id)
        .filter(
            AlertRecord.alert_type == alert_type,
            AlertRecord.data_ref == data_ref,
            AlertRecord.created_at >= today_start,
        )
        .first()
    )
    return row is not None


def _emit(db: Session, draft: AlertDraft) -> AlertRecord | None:
    if _exists_today(db, draft.alert_type, draft.data_ref):
        return None
    row = AlertRecord(
        alert_type=draft.alert_type,
        severity=draft.severity,
        message=draft.message,
        data_ref=draft.data_ref,
        run_id=draft.run_id,
        value=draft.value,
        threshold=draft.threshold,
        is_read=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _check_drawdown(
    db: Session, *, threshold: float = DEFAULT_DRAWDOWN_THRESHOLD
) -> list[AlertDraft]:
    """组合权益自峰值回撤检查（基于最近的 equity 序列）。"""
    from app.agent_runtime.paper.service import equity_series

    end = date.today()
    start = end - timedelta(days=120)
    series = equity_series(db, start.isoformat(), end.isoformat())
    if len(series) < 2:
        return []
    peak = series[0]["equity"]
    max_dd = 0.0
    for point in series:
        peak = max(peak, point["equity"])
        if peak > 0:
            max_dd = min(max_dd, point["equity"] / peak - 1.0)
    if max_dd < -threshold:
        return [
            AlertDraft(
                alert_type="drawdown",
                severity="critical",
                message=(
                    f"模拟盘回撤 {abs(max_dd):.1%} 超过阈值 {threshold:.1%}"
                ),
                data_ref=f"drawdown:{_day_key(datetime.now(timezone.utc))}",
                value=abs(max_dd),
                threshold=threshold,
            )
        ]
    return []


def _check_data_staleness(
    db: Session, *, max_days: int = DEFAULT_STALENESS_DAYS
) -> list[AlertDraft]:
    """已同步股票最新 K 线陈旧检查。"""
    cutoff = date.today() - timedelta(days=max_days)
    stale: list[AlertDraft] = []
    for stock in db.query(Stock).limit(100).all():
        latest = (
            db.query(DailyKline.date)
            .filter(DailyKline.stock_code == stock.code)
            .order_by(DailyKline.date.desc())
            .first()
        )
        if latest is None or latest[0] < cutoff:
            stale.append(
                AlertDraft(
                    alert_type="data_staleness",
                    severity="warning",
                    message=(
                        f"{stock.code} 最新 K 线 {latest[0] if latest else '缺失'}"
                        f" 早于 {cutoff.isoformat()}"
                    ),
                    data_ref=f"staleness:{stock.code}",
                    value=None,
                    threshold=float(max_days),
                )
            )
    return stale


def _check_provider_failure(
    db: Session, *, max_failures: int = DEFAULT_PROVIDER_FAILURES, window_h: int = 24
) -> list[AlertDraft]:
    """近窗口内工具调用失败（provider/网关失败）检查。"""
    since = datetime.now(timezone.utc) - timedelta(hours=window_h)
    failed = (
        db.query(ToolCallRecord)
        .filter(ToolCallRecord.status == "failed")
        .filter(ToolCallRecord.created_at >= since)
        .count()
    )
    if failed >= max_failures:
        return [
            AlertDraft(
                alert_type="provider_failure",
                severity="warning",
                message=f"近 {window_h}h 工具调用失败 {failed} 次（>= {max_failures}）",
                data_ref=f"provider:{_day_key(datetime.now(timezone.utc))}",
                value=float(failed),
                threshold=float(max_failures),
            )
        ]
    return []


def _check_cost_anomaly(
    db: Session, *, threshold: float = DEFAULT_COST_THRESHOLD
) -> list[AlertDraft]:
    """单日费用（佣金+印花税+过户费）异常检查。"""
    from app.models.paper_trading import PaperFill

    today = date.today().isoformat()
    total = (
        db.query(
            func.coalesce(
                func.sum(PaperFill.commission + PaperFill.stamp_tax + PaperFill.transfer_fee),
                0.0,
            )
        )
        .filter(PaperFill.trade_date == today)
        .scalar()
    ) or 0.0
    if float(total) > threshold:
        return [
            AlertDraft(
                alert_type="cost_anomaly",
                severity="warning",
                message=f"今日费用 {total:.2f} 元超过阈值 {threshold:.2f} 元",
                data_ref=f"cost:{today}",
                value=float(total),
                threshold=threshold,
            )
        ]
    return []


_CHECKS = (
    _check_drawdown,
    _check_data_staleness,
    _check_provider_failure,
    _check_cost_anomaly,
)


def run_alert_checks(db: Session, **kwargs: Any) -> list[dict[str, Any]]:
    """运行全部条件检查并落库（同日去重）；返回新增告警。"""
    created: list[dict[str, Any]] = []
    for check in _CHECKS:
        try:
            drafts = check(db, **kwargs)
        except Exception:
            logger.exception("告警检查 %s 失败", check.__name__)
            continue
        for draft in drafts:
            row = _emit(db, draft)
            if row is not None:
                created.append(
                    {
                        "id": row.id,
                        "alert_type": row.alert_type,
                        "severity": row.severity,
                        "message": row.message,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )
    return created


def list_alerts(
    db: Session, *, unread_only: bool = False, limit: int = 100
) -> list[dict[str, Any]]:
    query = db.query(AlertRecord)
    if unread_only:
        query = query.filter(AlertRecord.is_read == 0)
    rows = query.order_by(AlertRecord.created_at.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "alert_type": row.alert_type,
            "severity": row.severity,
            "message": row.message,
            "run_id": row.run_id,
            "data_ref": row.data_ref,
            "value": row.value,
            "threshold": row.threshold,
            "is_read": row.is_read == 1,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def mark_read(db: Session, alert_id: int) -> bool:
    row = db.get(AlertRecord, alert_id)
    if row is None:
        return False
    row.is_read = 1
    db.commit()
    return True
