"""Authenticated data health endpoints."""

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.auth import get_current_api_key
from app.config import get_db
from app.services.data_quality import coverage_report
from app.services.backtest_executor import BacktestExecutor
from app.exceptions import ValidationError
from app.services.market_data import load_bars
from app.services.corporate_actions import adjusted_history
from app.services.market_data_sync import calendar_quality, completed_end
from app.services.tasks import get_task_executor
import app.services.market_data_jobs  # noqa: F401

router = APIRouter(prefix="/api/v1/data", tags=["data-quality"])


@router.get("/quality")
def get_quality(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict:
    return coverage_report(db, limit=limit)


@router.get("/backtests/{result_id}/replay")
def replay_backtest(
    result_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
) -> dict:
    try:
        return BacktestExecutor(db).replay(result_id)
    except ValueError as exc:
        raise ValidationError(detail=str(exc)) from exc


class HistorySyncRequest(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=10000)
    start_date: date
    end_date: date
    metadata: bool = False

    @model_validator(mode="after")
    def validate_interval(self):
        from app.domain.stock_codes import normalize_stock_code

        self.codes = list(dict.fromkeys(normalize_stock_code(code) for code in self.codes))
        if self.end_date < self.start_date or self.end_date > completed_end():
            raise ValueError("Request must cover completed daily sessions only")
        if (self.end_date - self.start_date).days > 365 * 30:
            raise ValueError("Maximum history interval is 30 years")
        return self


@router.post("/history/sync", status_code=202)
def submit_history_sync(body: HistorySyncRequest, _: str = Depends(get_current_api_key)) -> dict:
    job = get_task_executor().submit("market_history_sync", payload=body.model_dump(mode="json"))
    return {"job_id": job.id, "status": job.status}


@router.get("/history/{stock_code}")
def get_versioned_history(
    stock_code: str, start_date: date, end_date: date,
    observed_before: datetime | None = None,
    adjustment: Literal["raw", "qfq", "hfq"] = "raw",
    db: Session = Depends(get_db), _: str = Depends(get_current_api_key),
) -> dict:
    from app.domain.stock_codes import normalize_stock_code

    if end_date < start_date or (end_date - start_date).days > 365 * 30:
        raise ValidationError(detail="Invalid history interval")
    code = normalize_stock_code(stock_code)
    try:
        if adjustment == "raw":
            frame, provenance = load_bars(db, code, start_date, end_date, observed_before=observed_before)
        else:
            frame, provenance = adjusted_history(db, code, start_date, end_date, mode=adjustment,
                                                  observed_before=observed_before)
    except ValueError as exc:
        raise ValidationError(detail=str(exc)) from exc
    return {"stock_code": code, "data": frame.to_dict(orient="records"),
            "provenance": provenance, "quality": calendar_quality(
                db, code, start_date, end_date, observed_before=observed_before)}
