from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Body,
    Response,
    Request,
)
import logging
import re
from app.auth import get_current_api_key
from app.limiter import limiter
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from app.config import SessionLocal, get_db
from app.models.models import Stock, DailyKline, BacktestResult
from app.schemas.schemas import (
    StockResponse,
    DailyKlineResponse,
    BacktestRequest,
    BacktestResultResponse,
    BacktestListResponse,
    SyncResponse,
)
from app.services.baostock_service import baostock_service
from app.services.backtest_engine import BacktestEngine
from app.services.dashboard_service import DashboardService
from app.services.indicator_service import indicator_service
from app.services.job_store import job_store

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


class JobResponse(BaseModel):
    job_id: str
    status: str
    job_type: str
    message: str


def _run_stock_sync_job(job_id: str) -> None:
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
    except Exception as exc:
        logger.error("Stock sync job failed", exc_info=True)
        job_store.update(
            job_id, status="failed", error=str(exc), message="Stock sync failed"
        )
    finally:
        db.close()


def _run_kline_sync_job(
    job_id: str,
    stock_codes: Optional[List[str]],
    start_date: str,
    end_date: Optional[str],
) -> None:
    db = SessionLocal()
    try:
        job_store.update(job_id, status="running", message="Syncing kline data")
        count, message = baostock_service.sync_kline_data(
            db,
            stock_codes=stock_codes,
            start_date=start_date,
            end_date=end_date,
        )
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message=message,
            result={"klines_synced": count, "message": message},
        )
    except Exception as exc:
        logger.error("Kline sync job failed", exc_info=True)
        job_store.update(
            job_id, status="failed", error=str(exc), message="Kline sync failed"
        )
    finally:
        db.close()


def _run_index_sync_job(
    job_id: str,
    index_codes: Optional[List[str]],
    start_date: str,
    end_date: Optional[str],
) -> None:
    db = SessionLocal()
    try:
        job_store.update(job_id, status="running", message="Syncing index data")
        count, message = baostock_service.sync_index_kline_data(
            db,
            index_codes=index_codes,
            start_date=start_date,
            end_date=end_date,
        )
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message=message,
            result={"index_klines_synced": count, "message": message},
        )
    except Exception as exc:
        logger.error("Index sync job failed", exc_info=True)
        job_store.update(
            job_id, status="failed", error=str(exc), message="Index sync failed"
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
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Get stock list"""
    query = db.query(Stock)
    if market:
        query = query.filter(Stock.market == market)
    response.headers["X-Total-Count"] = str(query.count())
    stocks = query.offset(skip).limit(limit).all()
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
    _validate_stock_code(code)
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


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
    _validate_stock_code(code)
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
        return {
            "success": True,
            "stock_code": code,
            "stock_name": stock.name,
            "period": period,
            "data": data,
        }
    except Exception:
        logger.error("Failed to get stock indicators", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


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
    _validate_stock_code(code)
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
    try:
        return DashboardService(db).get_summary()
    except Exception:
        logger.error("Failed to get dashboard summary", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        return SyncResponse(success=True, message=message, stocks_synced=count)
    except Exception:
        logger.error("Stock sync failed", exc_info=True)
        return SyncResponse(success=False, message="Stock sync failed")


@router.post("/stocks/sync/submit", response_model=JobResponse)
@limiter.limit("10/minute")
def submit_sync_stocks(
    request: Request,
    background_tasks: BackgroundTasks,
    _: str = Depends(get_current_api_key),
):
    job = job_store.create(job_type="sync_stocks")
    background_tasks.add_task(_run_stock_sync_job, job.id)
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
    start_date: Optional[str] = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Sync kline data from baostock"""
    try:
        count, message = baostock_service.sync_kline_data(
            db, stock_codes=stock_codes, start_date=start_date, end_date=end_date
        )
        return SyncResponse(success=True, message=message, klines_synced=count)
    except Exception:
        logger.error("Kline sync failed", exc_info=True)
        return SyncResponse(success=False, message="Kline sync failed")


@router.post("/stocks/sync-kline/submit", response_model=JobResponse)
@limiter.limit("10/minute")
def submit_sync_kline(
    request: Request,
    background_tasks: BackgroundTasks,
    stock_codes: List[str] = Body(None),
    start_date: Optional[str] = Query(None),
    end_date: str = Query(None),
    _: str = Depends(get_current_api_key),
):
    job = job_store.create(
        job_type="sync_kline",
        payload={
            "stock_codes": stock_codes or [],
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    background_tasks.add_task(
        _run_kline_sync_job, job.id, stock_codes, start_date, end_date
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
        return SyncResponse(success=True, message=message, klines_synced=count)
    except Exception:
        logger.error("Index sync failed", exc_info=True)
        return SyncResponse(success=False, message="Index sync failed")


@router.post("/indices/sync/submit", response_model=JobResponse)
@limiter.limit("5/minute")
def submit_sync_indices(
    request: Request,
    background_tasks: BackgroundTasks,
    index_codes: List[str] = Body(None),
    start_date: Optional[str] = Query(None),
    end_date: str = Query(None),
    _: str = Depends(get_current_api_key),
):
    job = job_store.create(
        job_type="sync_indices",
        payload={
            "index_codes": index_codes or [],
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    background_tasks.add_task(
        _run_index_sync_job, job.id, index_codes, start_date, end_date
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

        if not result:
            raise HTTPException(status_code=400, detail="Backtest failed")

        return result
    except Exception:
        logger.error("Backtest failed", exc_info=True)
        raise HTTPException(status_code=400, detail="Backtest failed")


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


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, _: str = Depends(get_current_api_key)):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, _: str = Depends(get_current_api_key)):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in ("completed", "failed"):
        raise HTTPException(status_code=400, detail="Job already finished")
    job_store.update(job_id, status="failed", error="Cancelled", message="Cancelled by user")
    return {"status": "cancelled"}
