from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import SessionLocal
from app.models.models import JobDbRecord

logger = logging.getLogger(__name__)


def _row_to_dict(row: JobDbRecord) -> Dict[str, Any]:
    """Convert a JobDbRecord ORM row to the same dict shape as the old JobRecord."""
    return {
        "id": row.id,
        "job_type": row.job_type,
        "status": row.status,
        "message": row.message,
        "progress": row.progress,
        "payload": row.payload or {},
        "result": row.result,
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


class JobRecord:
    """Lightweight dict-like wrapper returned by JobStore to preserve call-site API."""

    id: str
    job_type: str
    status: str
    message: str
    progress: float
    payload: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: str
    updated_at: str

    def __init__(self, data: Dict[str, Any]):
        for key, value in data.items():
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class JobStore:
    """Database-backed job store.

    Exposes the same create / get / update interface as the previous in-memory
    implementation, but persists records to the database so they survive restarts.
    """

    def create(
        self, job_type: str, payload: Optional[Dict[str, Any]] = None
    ) -> JobRecord:
        db: Session = SessionLocal()
        try:
            row = JobDbRecord(
                id=str(uuid4()),
                job_type=job_type,
                payload=payload or {},
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return JobRecord(_row_to_dict(row))
        except Exception:
            db.rollback()
            logger.error("Failed to create job record", exc_info=True)
            raise
        finally:
            db.close()

    def get(self, job_id: str) -> Optional[JobRecord]:
        db: Session = SessionLocal()
        try:
            row = db.query(JobDbRecord).filter(JobDbRecord.id == job_id).first()
            if row is None:
                return None
            return JobRecord(_row_to_dict(row))
        finally:
            db.close()

    def update(self, job_id: str, **changes: Any) -> Optional[JobRecord]:
        db: Session = SessionLocal()
        try:
            row = db.query(JobDbRecord).filter(JobDbRecord.id == job_id).first()
            if row is None:
                return None

            for key, value in changes.items():
                setattr(row, key, value)
            setattr(row, "updated_at", datetime.utcnow())
            db.commit()
            db.refresh(row)
            return JobRecord(_row_to_dict(row))
        except Exception:
            db.rollback()
            logger.error("Failed to update job %s", job_id, exc_info=True)
            raise
        finally:
            db.close()


job_store = JobStore()
