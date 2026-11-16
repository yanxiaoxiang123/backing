# -*- coding: utf-8 -*-
"""Agent 分析 API"""

import logging
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy.orm import Session

from app.agent.orchestrator import AgentOrchestrator
from app.auth import get_current_api_key
from app.config import SessionLocal, get_db
from app.exceptions import (
    ExternalServiceError,
    NotFoundError,
    ProviderUnavailableError,
    ValidationError,
)
from app.models.analysis import AnalysisRecord
from app.models.models import DailyKline, Stock
from app.services.baostock_service import baostock_service
from app.services.job_store import job_store
from app.services.tasks import (
    TaskCancelledError,
    get_task_executor,
    register_runner,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class AnalyzeRequest(BaseModel):
    """分析请求"""

    stock_code: str
    stock_name: Optional[str] = ""
    mode: str = "standard"  # quick/standard/full/strategy


class AnalyzeResponse(BaseModel):
    """分析响应"""

    success: bool
    stock_code: str
    stock_name: str
    mode: str
    final_signal: str
    final_confidence: float
    final_reason: str
    opinions: List[dict]
    stages: List[dict]
    news_items: List[dict] = []
    duration_s: float
    error: Optional[str] = None


class AnalysisRecordResponse(BaseModel):
    """分析记录响应"""

    id: int
    stock_code: str
    stock_name: Optional[str]
    analysis_date: str
    mode: str
    final_signal: str
    final_confidence: float
    final_reason: Optional[str]
    duration_s: float
    error: Optional[str]
    created_at: str

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _convert_datetime(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("analysis_date", "created_at"):
                val = data.get(key)
                if hasattr(val, "isoformat"):
                    data[key] = val.isoformat()
        return data


class AnalyzeSubmitResponse(BaseModel):
    job_id: str
    status: str
    message: str


def _ensure_stock_kline_data(db: Session, stock_code: str) -> None:
    stock = db.query(Stock).filter(Stock.code == stock_code).first()
    if not stock:
        raise NotFoundError(detail=f"Stock '{stock_code}' not found")

    latest_kline = (
        db.query(DailyKline)
        .filter(DailyKline.stock_code == stock_code)
        .order_by(DailyKline.date.desc())
        .first()
    )
    if latest_kline:
        return

    logger.info("No kline data for %s, syncing before analysis", stock_code)
    try:
        count, message = baostock_service.sync_kline_data(
            db=db,
            stock_codes=[stock_code],
            start_date="2020-01-01",
            end_date=datetime.now().strftime("%Y-%m-%d"),
        )
    except Exception as exc:
        raise ExternalServiceError(
            detail=(
                f"Failed to sync kline data for {stock_code} before analysis"
            ),
            provider="baostock",
            retryable=True,
        ) from exc
    logger.info(
        "Pre-analysis kline sync result for %s: %s (%s)", stock_code, count, message
    )

    latest_kline = (
        db.query(DailyKline)
        .filter(DailyKline.stock_code == stock_code)
        .order_by(DailyKline.date.desc())
        .first()
    )
    if latest_kline is None:
        raise ValidationError(
            detail=f"No kline data available for {stock_code} after sync"
        )


def _persist_analysis(db: Session, request: AnalyzeRequest, result) -> AnalyzeResponse:
    news_items = _extract_news_items(result.stages)
    analysis_record = AnalysisRecord(
        stock_code=request.stock_code,
        stock_name=request.stock_name or request.stock_code,
        analysis_date=datetime.now().date(),
        mode=request.mode,
        final_signal=result.final_signal,
        final_confidence=result.final_confidence,
        final_reason=result.final_reason,
        # JSON 列直接存对象（读取端也直接取对象，无需 json.dumps/loads）
        opinions_json=result.opinions if result.opinions else None,
        stages_json=result.stages if result.stages else None,
        duration_s=result.duration_s,
        error=result.error,
    )
    db.add(analysis_record)
    db.commit()

    return AnalyzeResponse(
        success=result.success,
        stock_code=request.stock_code,
        stock_name=request.stock_name or request.stock_code,
        mode=request.mode,
        final_signal=result.final_signal,
        final_confidence=result.final_confidence,
        final_reason=result.final_reason,
        opinions=result.opinions,
        stages=result.stages,
        news_items=news_items,
        duration_s=result.duration_s,
        error=result.error,
    )


def _extract_news_items(stages: List[dict]) -> List[dict]:
    for stage in stages or []:
        if stage.get("stage_name") == "intel":
            meta = stage.get("meta") or {}
            news_items = meta.get("news_items")
            if isinstance(news_items, list):
                return news_items
    return []


@register_runner("agent_analysis")
def run_analysis_job(job_id: str, payload: dict) -> None:
    """Background runner for /agent/analyze/submit."""
    db = SessionLocal()
    try:
        request = AnalyzeRequest(**payload)
        job_store.update(job_id, status="running", message="Running agent analysis")
        _ensure_stock_kline_data(db, request.stock_code)
        orchestrator = AgentOrchestrator(mode=request.mode)
        if not orchestrator.is_available:
            raise ProviderUnavailableError(
                detail="LLM service not available. Please check API key configuration.",
                provider="deepseek",
            )

        def _on_progress(progress: float, stages: list):
            # 检查是否被取消（协作式取消：orchestrator 放行该异常）
            current = job_store.get(job_id)
            if current and current.status == "failed" and current.error == "Cancelled":
                raise TaskCancelledError("Job cancelled by user")
            job_store.update(
                job_id,
                progress=progress / 100.0,
                message=f"Running: {request.mode} analysis",
                payload={"stages": stages},
            )

        result = orchestrator.run(
            stock_code=request.stock_code,
            stock_name=request.stock_name or request.stock_code,
            progress_callback=_on_progress,
        )
        payload_response = _persist_analysis(db, request, result)
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message="Analysis completed",
            result=payload_response.model_dump(),
        )
    except Exception as exc:
        logger.exception("Async analysis failed", extra={"job_id": job_id})
        job_store.update(
            job_id, status="failed", error=str(exc), message="Analysis failed"
        )
    finally:
        db.close()


# Endpoints
@router.post("/agent/analyze", response_model=AnalyzeResponse)
def analyze_stock(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """执行股票分析（经统一 runtime：落 run/step/tool 事实，行为与旧版一致）"""
    from app.agent_api.adapter import run_legacy_analysis

    _ensure_stock_kline_data(db, request.stock_code)
    _, final, result = run_legacy_analysis(db, request)
    if final["status"] != "completed" or result is None:
        error = final.get("error") or "analysis failed"
        if "LLM service not available" in error or "API key" in error:
            raise ProviderUnavailableError(detail=error, provider="deepseek")
        raise HTTPException(status_code=500, detail=error)
    return _persist_analysis(db, request, result)


@router.post("/agent/analyze/submit", response_model=AnalyzeSubmitResponse)
def submit_analysis(
    request: AnalyzeRequest,
    _: str = Depends(get_current_api_key),
):
    job = get_task_executor().submit(
        job_type="agent_analysis",
        payload=request.model_dump(),
        job_key=f"analyze:{request.stock_code}:{request.mode}",
    )
    return AnalyzeSubmitResponse(
        job_id=job.id, status=job.status, message="Analysis queued"
    )


@router.get("/agent/history", response_model=List[AnalysisRecordResponse])
def get_analysis_history(
    stock_code: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """获取分析历史"""
    query = db.query(AnalysisRecord)

    if stock_code:
        query = query.filter(AnalysisRecord.stock_code == stock_code)

    records = (
        query.order_by(
            AnalysisRecord.analysis_date.desc(), AnalysisRecord.created_at.desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        AnalysisRecordResponse(
            id=r.id,
            stock_code=r.stock_code,
            stock_name=r.stock_name,
            analysis_date=str(r.analysis_date),
            mode=r.mode,
            final_signal=r.final_signal,
            final_confidence=r.final_confidence,
            final_reason=r.final_reason,
            duration_s=r.duration_s,
            error=r.error,
            created_at=str(r.created_at),
        )
        for r in records
    ]


@router.get("/agent/{record_id}")
def get_analysis_detail(
    record_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """获取分析详情"""
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == record_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Analysis record not found")

    return {
        "id": record.id,
        "stock_code": record.stock_code,
        "stock_name": record.stock_name,
        "analysis_date": str(record.analysis_date),
        "mode": record.mode,
        "final_signal": record.final_signal,
        "final_confidence": record.final_confidence,
        "final_reason": record.final_reason,
        # JSON 列直接返回对象（兼容迁移前的纯文本行：SQLAlchemy JSON 读取时自动解析）
        "opinions": record.opinions_json or [],
        "stages": record.stages_json or [],
        "news_items": _extract_news_items(record.stages_json or []),
        "duration_s": record.duration_s,
        "error": record.error,
        "created_at": str(record.created_at),
    }
