"""模拟盘 API（规格 v2 决策 21-23；US-3.1/3.2/3.5）。

- POST /agent-runs/{run_id}/approvals/{approval_id}/decide  审批决策（联动订单）
- GET  /agent-runs/{run_id}/approvals                       审批列表（工作台审批卡）
- POST /paper/match                                         手动触发撮合循环（demo/验收）
- GET  /paper/account | /paper/orders                       账户状态与订单（只读）
- GET  /paper/events                                        订单/资金事件（重放审计）

认证：沿用现有 session cookie / X-API-Key（get_current_api_key）。
"""

import logging
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent_runtime.paper import service as paper_service
from app.auth import get_current_api_key
from app.config import get_db
from app.models.agent_runtime import ApprovalRecord
from app.models.paper_trading import PaperCashEvent, PaperOrderEvent

logger = logging.getLogger(__name__)

router = APIRouter()


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


class DecideRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    decided_by: str = "user"


@router.post("/agent-runs/{run_id}/approvals/{approval_id}/decide")
def decide_approval(
    run_id: str,
    approval_id: int,
    body: DecideRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict[str, Any]:
    """审批决策：批准/拒绝（联动模拟盘订单与事件；一次性窗口）。"""
    try:
        return paper_service.decide_approval(
            db, approval_id, body.decision, decided_by=body.decided_by
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agent-runs/{run_id}/approvals")
def list_run_approvals(
    run_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict[str, Any]:
    rows = (
        db.query(ApprovalRecord)
        .filter(ApprovalRecord.run_id == run_id)
        .order_by(ApprovalRecord.created_at.asc())
        .all()
    )
    return {
        "approvals": [
            {
                "id": row.id,
                "run_id": row.run_id,
                "action": row.action,
                "summary": row.summary,
                "direction": row.direction,
                "target_position_pct": row.target_position_pct,
                "risk_summary": row.risk_summary,
                "expires_at": _iso(row.expires_at),
                "status": row.status,
                "decided_by": row.decided_by,
                "decided_at": _iso(row.decided_at),
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ]
    }


@router.post("/paper/match")
def trigger_matching_cycle(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict[str, int]:
    """手动触发撮合循环（确定性；demo 与验收用）。"""
    return paper_service.run_matching_cycle(db)


@router.get("/paper/account")
def get_paper_account(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict[str, Any]:
    return paper_service.account_state(db)


@router.get("/paper/orders")
def get_paper_orders(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict[str, Any]:
    return {"orders": paper_service.list_orders(db, status=status)}


@router.get("/paper/events")
def get_paper_events(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict[str, Any]:
    """订单与资金事件（append-only，重放审计用）。"""
    order_events = (
        db.query(PaperOrderEvent).order_by(PaperOrderEvent.id.asc()).limit(500).all()
    )
    cash_events = (
        db.query(PaperCashEvent).order_by(PaperCashEvent.seq.asc()).limit(500).all()
    )
    return {
        "order_events": [
            {
                "order_id": e.order_id,
                "seq": e.seq,
                "event_type": e.event_type,
                "detail": e.detail_json,
                "created_at": _iso(e.created_at),
            }
            for e in order_events
        ],
        "cash_events": [
            {
                "seq": e.seq,
                "event_type": e.event_type,
                "amount": e.amount,
                "order_id": e.order_id,
                "created_at": _iso(e.created_at),
            }
            for e in cash_events
        ],
    }


@router.get("/paper/attribution")
def get_attribution(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict[str, Any]:
    """盘后归因：组合权益 vs sh.000300 的收益分解（US-3.3）。"""
    from datetime import date, timedelta

    end = end_date or date.today().isoformat()
    start = start_date or (date.fromisoformat(end) - timedelta(days=30)).isoformat()
    benchmark_series: list[float] | None = None
    try:
        from app.services.research_data import fetch_index_kline

        entry = fetch_index_kline("sh.000300", start, end)
        rows = entry["payload"]["kline"]
        benchmark_series = [float(r["close"]) for r in rows] or None
    except Exception:
        benchmark_series = None
    try:
        return paper_service.attribution_report(
            db, start, end, benchmark_series=benchmark_series
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/paper/plan")
def get_pre_market_plan(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict[str, Any]:
    """盘前计划：待批/已批订单快照（US-3.3）。"""
    return paper_service.pre_market_plan(db)
