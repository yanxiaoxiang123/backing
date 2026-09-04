import logging
import re
from datetime import date
from typing import List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_api_key
from app.config import SessionLocal, get_db
from app.exceptions import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from app.limiter import limiter
from app.models.models import (
    DEFAULT_USER_ID,
    BacktestResult,
    DailyKline,
    Stock,
    WatchlistItem,
)
from app.schemas.schemas import (
    BacktestListResponse,
    BacktestRequest,
    BacktestResultResponse,
    DailyKlineResponse,
    StockResponse,
    SyncResponse,
)
from app.services.backtest_engine import BacktestEngine
from app.services.baostock_service import baostock_service
from app.services.dashboard_service import DashboardService
from app.services.indicator_service import indicator_service
from app.services.job_store import job_store
from app.services.tasks import get_task_executor, register_runner, task_metrics

router = APIRouter()

logger = logging.getLogger(__name__)

# Stock code format: sh.600000, sz.000001, bj.430047, etc.
_STOCK_CODE_RE = re.compile(r"^(sh|sz|bj)\.\d{6}$")


def _validate_stock_code(code: str) -> str:
    """Validate stock code format. Returns the code if valid, raises HTTPException otherwise."""
    if not _STOCK_CODE_RE.match(code):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid stock code format: '{code}'. Expected format: sh.XXXXXX, sz.XXXXXX, or bj.XXXXXX",
        )
    return code


def _resolve_stock_code(db: Session, code: str) -> str:
    """Accept canonical codes and resolve legacy six-digit route values."""
    normalized = code.strip().lower()
    if _STOCK_CODE_RE.match(normalized):
        return normalized
    if re.fullmatch(r"\d{6}", normalized):
        matches = (
            db.query(Stock.code)
            .filter(Stock.code.endswith(f".{normalized}"))
            .limit(2)
            .all()
        )
        if len(matches) == 1:
            return str(matches[0][0])
        if not matches:
            raise HTTPException(status_code=404, detail="Stock not found")
        raise HTTPException(
            status_code=422,
            detail=f"Ambiguous stock code: '{code}'. Please include the market prefix.",
        )
    return _validate_stock_code(normalized)


class JobResponse(BaseModel):
    job_id: str
    status: str
    job_type: str
    message: str


@register_runner("sync_stocks")
def run_stock_sync_job(job_id: str, payload: dict) -> None:
    """Sync the full stock list from baostock (runs inside the task executor)."""
    db = SessionLocal()
    try:
        job_store.update(job_id, status="running", message="Syncing stock list")
        count, message = baostock_service.sync_stock_list(db)
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message=message,
            result={"stocks_synced": count, "message": message},
        )
    except Exception:
        logger.exception("Stock sync job failed", extra={"job_id": job_id})
        job_store.update(
            job_id, status="failed", error="Stock sync failed", message="Stock sync failed"
        )
    finally:
        db.close()


@register_runner("sync_kline")
def run_kline_sync_job(job_id: str, payload: dict) -> None:
    """Sync kline data from baostock (runs inside the task executor)."""
    db = SessionLocal()
    try:
        job_store.update(job_id, status="running", message="Syncing kline data")
        stock_codes = payload.get("stock_codes") or None
        strategy = payload.get("strategy", "incremental")
        start_date = "2020-01-01" if strategy == "full" else None
        count, message = baostock_service.sync_kline_data(
            db,
            stock_codes=stock_codes,
            start_date=start_date,
            end_date=None,
        )
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message=message,
            result={"klines_synced": count, "message": message},
        )
    except Exception:
        logger.exception("Kline sync job failed", extra={"job_id": job_id})
        job_store.update(
            job_id, status="failed", error="Kline sync failed", message="Kline sync failed"
        )
    finally:
        db.close()


@register_runner("sync_indices")
def run_index_sync_job(job_id: str, payload: dict) -> None:
    """Sync index kline data from baostock (runs inside the task executor)."""
    db = SessionLocal()
    try:
        job_store.update(job_id, status="running", message="Syncing index data")
        count, message = baostock_service.sync_index_kline_data(
            db,
            index_codes=payload.get("index_codes"),
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
        )
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message=message,
            result={"index_klines_synced": count, "message": message},
        )
    except Exception:
        logger.exception("Index sync job failed", extra={"job_id": job_id})
        job_store.update(
            job_id, status="failed", error="Index sync failed", message="Index sync failed"
        )
    finally:
        db.close()


# Stock endpoints
@router.get("/stocks", response_model=List[StockResponse])
@limiter.limit("100/minute")
def get_stocks(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
    market: str = Query(None, description="Filter by market (sh/sz)"),
    search: str = Query(None, description="Search by code or name (case-insensitive)"),
    cursor: int = Query(0, description="Cursor: last stock id (exclusive)"),
    limit: int = Query(100, ge=1, le=500),
):
    """Get stock list with cursor-based pagination and optional search"""
    query = db.query(Stock)
    if market:
        query = query.filter(Stock.market == market)
    if search:
        q = f"%{search}%"
        query = query.filter(
            (Stock.code.ilike(q)) | (Stock.name.ilike(q))
        )
        # When searching, use offset pagination (search makes cursor meaningless)
        total = query.count()
        response.headers["X-Total-Count"] = str(total)
        offset = cursor  # reuse cursor param as offset when searching
        stocks = query.order_by(Stock.id.asc()).offset(offset).limit(limit).all()
    else:
        # Cursor-based: fetch stocks with id > cursor
        query = query.filter(Stock.id > cursor)
        query = query.order_by(Stock.id.asc())
        response.headers["X-Total-Count"] = str(query.count())
        stocks = query.limit(limit).all()
    return stocks


@router.get("/stocks/{code}", response_model=StockResponse)
@limiter.limit("100/minute")
def get_stock(
    request: Request,
    code: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Get stock by code"""
    code = _resolve_stock_code(db, code)
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@router.get("/stocks/{code}/overview")
@limiter.limit("60/minute")
def get_stock_overview(
    request: Request,
    code: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Return the compact decision-research context for one stock."""
    code = _resolve_stock_code(db, code)
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    bars = (
        db.query(DailyKline)
        .filter(DailyKline.stock_code == code)
        .order_by(DailyKline.date.desc())
        .limit(2)
        .all()
    )
    latest = bars[0] if bars else None
    previous = bars[1] if len(bars) > 1 else latest
    previous_close = float(previous.close) if previous else 0.0
    latest_close = float(latest.close) if latest else 0.0
    change = latest_close - previous_close
    change_percent = (change / previous_close * 100) if previous_close else 0.0
    watchlisted = (
        db.query(WatchlistItem.id)
        .filter(
            WatchlistItem.user_id == DEFAULT_USER_ID,
            WatchlistItem.stock_code == code,
        )
        .first()
        is not None
    )
    quote = None
    if latest:
        quote = {
            "id": 0,
            "code": code,
            "name": stock.name,
            "current_price": round(latest_close, 2),
            "high": round(float(latest.high), 2),
            "low": round(float(latest.low), 2),
            "volume": int(latest.volume),
            "change": round(change, 2),
            "change_percent": round(change_percent, 2),
        }
    return {
        "stock": stock,
        "quote": quote,
        "watchlisted": watchlisted,
        "technical": {"updated_at": latest.date.isoformat() if latest else None},
        "recent_analysis": [],
    }


@router.get("/stocks/{code}/indicators")
@limiter.limit("50/minute")
def get_stock_indicators(
    request: Request,
    code: str,
    period: str = Query("daily", description="daily/weekly/monthly"),
    start_date: date = Query(None),
    end_date: date = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Get stock kline data with technical indicators"""
    code = _resolve_stock_code(db, code)
    # Verify stock exists
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    try:
        data = indicator_service.get_kline_with_indicators(
            db=db,
            stock_code=code,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise ValidationError(detail=str(exc)) from exc
    return {
        "success": True,
        "stock_code": code,
        "stock_name": stock.name,
        "period": period,
        "data": data,
    }


@router.get("/stocks/{code}/kline", response_model=List[DailyKlineResponse])
@limiter.limit("50/minute")
def get_stock_kline(
    request: Request,
    code: str,
    start_date: date = Query(None),
    end_date: date = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Get stock kline data"""
    code = _resolve_stock_code(db, code)
    query = db.query(DailyKline).filter(DailyKline.stock_code == code)
    if start_date:
        query = query.filter(DailyKline.date >= start_date)
    if end_date:
        query = query.filter(DailyKline.date <= end_date)
    klines = query.order_by(DailyKline.date).all()
    return klines


@router.get("/dashboard")
@limiter.limit("30/minute")
def get_dashboard_summary(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Get dashboard summary using real market and index data."""
    return DashboardService(db).get_summary()


@router.post("/stocks/sync", response_model=SyncResponse)
@limiter.limit("10/minute")
def sync_stocks(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Sync stock list from baostock"""
    try:
        count, message = baostock_service.sync_stock_list(db)
    except Exception as exc:
        raise ExternalServiceError(
            detail="Stock sync failed", provider="baostock", retryable=True
        ) from exc
    return SyncResponse(success=True, message=message, stocks_synced=count)


@router.post("/stocks/sync/submit", response_model=JobResponse)
@limiter.limit("10/minute")
def submit_sync_stocks(
    request: Request,
    _: str = Depends(get_current_api_key),
):
    job = get_task_executor().submit(
        job_type="sync_stocks",
        job_key=f"sync_stocks:{date.today().isoformat()}",
    )
    return JobResponse(
        job_id=job.id,
        status=job.status,
        job_type=job.job_type,
        message="Stock sync queued",
    )


@router.post("/stocks/sync-kline", response_model=SyncResponse)
@limiter.limit("10/minute")
def sync_kline(
    request: Request,
    stock_codes: List[str] = Body(None),
    strategy: str = Query("incremental"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Sync kline data from baostock"""
    try:
        requested_start = (
            start_date.isoformat()
            if start_date is not None
            else ("2020-01-01" if strategy == "full" else None)
        )
        count, message = baostock_service.sync_kline_data(
            db,
            stock_codes=stock_codes,
            start_date=requested_start,
            end_date=end_date.isoformat() if end_date is not None else None,
        )
    except Exception as exc:
        raise ExternalServiceError(
            detail="Kline sync failed", provider="baostock", retryable=True
        ) from exc
    return SyncResponse(success=True, message=message, klines_synced=count)


@router.post("/stocks/sync-kline/submit", response_model=JobResponse)
@limiter.limit("10/minute")
def submit_sync_kline(
    request: Request,
    stock_codes: List[str] = Body(None),
    strategy: str = Query("incremental"),
    _: str = Depends(get_current_api_key),
):
    payload = {
        "stock_codes": stock_codes or [],
        "strategy": strategy,
    }
    job_key = (
        f"sync_kline:{strategy}:"
        f"{','.join(sorted(stock_codes or [])) or 'ALL'}"
    )
    job = get_task_executor().submit(
        job_type="sync_kline", payload=payload, job_key=job_key
    )
    return JobResponse(
        job_id=job.id,
        status=job.status,
        job_type=job.job_type,
        message="Kline sync queued",
    )


# Index endpoints
@router.get("/indices")
@limiter.limit("10/minute")
def get_indices(request: Request, _: str = Depends(get_current_api_key)):
    """Get index list"""
    return baostock_service.get_index_list()


@router.post("/indices/sync", response_model=SyncResponse)
@limiter.limit("5/minute")
def sync_indices(
    request: Request,
    index_codes: List[str] = Body(None),
    start_date: Optional[str] = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Sync index kline data"""
    try:
        count, message = baostock_service.sync_index_kline_data(
            db, index_codes=index_codes, start_date=start_date, end_date=end_date
        )
    except Exception as exc:
        raise ExternalServiceError(
            detail="Index sync failed", provider="baostock", retryable=True
        ) from exc
    return SyncResponse(success=True, message=message, klines_synced=count)


@router.post("/indices/sync/submit", response_model=JobResponse)
@limiter.limit("5/minute")
def submit_sync_indices(
    request: Request,
    index_codes: List[str] = Body(None),
    start_date: Optional[str] = Query(None),
    end_date: str = Query(None),
    _: str = Depends(get_current_api_key),
):
    payload = {
        "index_codes": index_codes or [],
        "start_date": start_date,
        "end_date": end_date,
    }
    job_key = (
        f"sync_indices:{','.join(sorted(index_codes or [])) or 'MAJOR'}:"
        f"{start_date or ''}:{end_date or ''}"
    )
    job = get_task_executor().submit(
        job_type="sync_indices", payload=payload, job_key=job_key
    )
    return JobResponse(
        job_id=job.id,
        status=job.status,
        job_type=job.job_type,
        message="Index sync queued",
    )


# Backtest endpoints
@router.post("/backtest", response_model=BacktestResultResponse)
def run_backtest(
    request: BacktestRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Run backtest"""
    try:
        engine = BacktestEngine(db)
        result = engine.run_backtest(
            stock_code=request.stock_code,
            strategy_type=request.strategy_type,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            parameters=request.parameters,
        )
    except ValueError as exc:
        raise ValidationError(detail=str(exc)) from exc

    if not result:
        raise ValidationError(detail="Backtest failed")
    return result


@router.get("/backtest/results", response_model=List[BacktestListResponse])
def get_backtest_results(
    db: Session = Depends(get_db),
    stock_code: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _: str = Depends(get_current_api_key),
):
    """Get backtest results list"""
    query = db.query(BacktestResult)
    if stock_code:
        query = query.filter(BacktestResult.stock_code == stock_code)
    results = (
        query.order_by(BacktestResult.created_at.desc()).offset(skip).limit(limit).all()
    )
    return results


@router.get("/backtest/{result_id}", response_model=BacktestResultResponse)
def get_backtest_result(
    result_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_api_key)
):
    """Get backtest result by ID"""
    result = (
        db.query(BacktestResult)
        .options(joinedload(BacktestResult.trades))
        .filter(BacktestResult.id == result_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Backtest result not found")
    return result


# Health check
@router.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


# Job metrics (registered before /jobs/{job_id} so the literal path wins)
@router.get("/jobs/metrics")
def get_job_metrics(_: str = Depends(get_current_api_key)):
    """In-process task metrics: counters and durations per job type."""
    return task_metrics.snapshot()


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, _: str = Depends(get_current_api_key)):
    job = job_store.get(job_id)
    if not job:
        raise NotFoundError(detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, _: str = Depends(get_current_api_key)):
    """Request cancellation of a pending/running job.

    Cancellation is cooperative: the job runner checks for the cancelled
    marker between work steps. Returns the current status.
    """
    job = job_store.get(job_id)
    if not job:
        raise NotFoundError(detail="Job not found")
    if job.status == "completed":
        raise ConflictError(detail="Job already finished")
    if job.status == "failed" and (job.error or "") == "Cancelled":
        return {"status": "cancelled"}  # idempotent
    job_store.update(
        job_id,
        status="failed",
        error="Cancelled",
        message="Cancelled by user",
    )
    return {"status": "cancelled"}
