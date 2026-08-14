from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional
from uuid import uuid4

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import SessionLocal, settings
from app.models.models import JobDbRecord
from app.schemas.schemas import JobRecordSchema

logger = logging.getLogger(__name__)

# terminal statuses – jobs in these states are considered finished
_TERMINAL = {"completed", "failed", "cancelled"}
# active statuses – jobs in these states should be progressing
_ACTIVE = {"pending", "running"}


class JobStore:
    """Database-backed job store for async task tracking.

    Each method accepts an optional *db* session:
    - In FastAPI route handlers: pass ``db`` from ``Depends(get_db)`` for
      request-scoped session reuse.
    - In background threads: omit *db* and the method creates its own session.
    """

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _session(
        self, db: Optional[Session] = None
    ) -> Iterator[tuple[Session, bool]]:
        """Yield (session, owned).  Auto-commits / rolls back on owned sessions."""
        if db is not None:
            yield db, False
            return

        session = SessionLocal()
        try:
            yield session, True
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Startup recovery
    # ------------------------------------------------------------------

    def reset_stale_jobs(self, *, db: Optional[Session] = None) -> int:
        """Mark all non-terminal jobs as failed.

        Called on application startup because any in-flight background task
        was killed when the previous process shut down.
        """
        with self._session(db) as (session, _owned):
            count = (
                session.query(JobDbRecord)
                .filter(JobDbRecord.status.in_(_ACTIVE))
                .update(
                    {
                        JobDbRecord.status: "failed",
                        JobDbRecord.error: "Server restarted",
                        JobDbRecord.message: "Job aborted due to server restart",
                    },
                    synchronize_session=False,
                )
            )
            if count:
                logger.info("Reset %d stale job(s) on startup", count)
            return count

    def mark_timed_out_jobs(
        self, timeout_minutes: int = 30, *, db: Optional[Session] = None
    ) -> int:
        """Mark running jobs as failed if their *updated_at* is older than timeout.

        Can be called periodically (e.g. via cron or a background loop) to detect
        hung tasks that haven't reported progress.
        """
        with self._session(db) as (session, _owned):
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                minutes=timeout_minutes
            )
            count = (
                session.query(JobDbRecord)
                .filter(
                    JobDbRecord.status == "running",
                    JobDbRecord.updated_at < cutoff,
                )
                .update(
                    {
                        JobDbRecord.status: "failed",
                        JobDbRecord.error: "Job timed out",
                        JobDbRecord.message: f"No update for {timeout_minutes}+ min",
                    },
                    synchronize_session=False,
                )
            )
            if count:
                logger.warning("Timed out %d hung job(s)", count)
            return count

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        job_type: str,
        payload: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        *,
        db: Optional[Session] = None,
        job_key: Optional[str] = None,
    ) -> JobRecordSchema:
        """Create a job record.

        With *job_key*, creation is idempotent: an existing record with the
        same key is returned instead of creating a duplicate (the unique
        index ``uq_jobs_job_key`` makes this race-safe).
        """
        if job_key:
            existing = self._find_by_key(job_key, db)
            if existing is not None:
                return existing

        with self._session(db) as (session, _owned):
            row = JobDbRecord(
                id=job_id or str(uuid4()),
                job_type=job_type,
                payload=payload or {},
                job_key=job_key,
                max_retries=settings.TASK_MAX_RETRIES,
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError:
                # Concurrent duplicate job_key: return the winner's record.
                session.rollback()
                existing = self._find_by_key(job_key, db) if job_key else None
                if existing is not None:
                    return existing
                raise
            session.refresh(row)
            return JobRecordSchema.model_validate(row)

    def _find_by_key(
        self, job_key: str, db: Optional[Session] = None
    ) -> Optional[JobRecordSchema]:
        with self._session(db) as (session, _owned):
            row = (
                session.query(JobDbRecord)
                .filter(JobDbRecord.job_key == job_key)
                .first()
            )
            if row is None:
                return None
            return JobRecordSchema.model_validate(row)

    def claim_due(
        self, *, db: Optional[Session] = None
    ) -> Optional[JobRecordSchema]:
        """Atomically claim the next runnable job, or None when idle.

        Runnable = pending without a future retry time, OR a "running" job
        whose lease has expired (its executor died). Claiming flips the row to
        ``running`` with a fresh lease; the conditional UPDATE makes sure two
        executors never claim the same job.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        lease_until = now + timedelta(seconds=settings.TASK_LEASE_SECONDS)

        with self._session(db) as (session, _owned):
            row = (
                session.query(JobDbRecord)
                .filter(
                    or_(
                        and_(
                            JobDbRecord.status == "pending",
                            or_(
                                JobDbRecord.next_retry_at.is_(None),
                                JobDbRecord.next_retry_at <= now,
                            ),
                        ),
                        and_(
                            JobDbRecord.status == "running",
                            JobDbRecord.lease_until.isnot(None),
                            JobDbRecord.lease_until < now,
                        ),
                    )
                )
                .order_by(JobDbRecord.created_at.asc())
                .first()
            )
            if row is None:
                return None

            expected = row.status  # "pending" or "running" (expired lease)
            claimed = (
                session.query(JobDbRecord)
                .filter(
                    JobDbRecord.id == row.id,
                    JobDbRecord.status == expected,
                )
                .update(
                    {
                        JobDbRecord.status: "running",
                        JobDbRecord.lease_until: lease_until,
                    },
                    synchronize_session=False,
                )
            )
            if not claimed:
                return None  # lost the claim race
            session.flush()
            session.refresh(row)
            return JobRecordSchema.model_validate(row)

    def get(
        self, job_id: str, *, db: Optional[Session] = None
    ) -> Optional[JobRecordSchema]:
        with self._session(db) as (session, _owned):
            row = (
                session.query(JobDbRecord)
                .filter(JobDbRecord.id == job_id)
                .first()
            )
            if row is None:
                return None
            return JobRecordSchema.model_validate(row)

    def update(
        self, job_id: str, *, db: Optional[Session] = None, **changes: Any
    ) -> Optional[JobRecordSchema]:
        with self._session(db) as (session, _owned):
            row = (
                session.query(JobDbRecord)
                .filter(JobDbRecord.id == job_id)
                .first()
            )
            if row is None:
                return None
            for key, value in changes.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            # updated_at is handled by the ORM's onupdate=func.now()
            session.flush()
            session.refresh(row)
            return JobRecordSchema.model_validate(row)

    def list_recent(
        self,
        limit: int = 20,
        status: Optional[str] = None,
        *,
        db: Optional[Session] = None,
    ) -> List[JobRecordSchema]:
        with self._session(db) as (session, _owned):
            q = session.query(JobDbRecord).order_by(
                JobDbRecord.created_at.desc()
            )
            if status:
                q = q.filter(JobDbRecord.status == status)
            rows = q.limit(limit).all()
            return [JobRecordSchema.model_validate(r) for r in rows]

    def cleanup_old(
        self, days: int = 7, *, db: Optional[Session] = None
    ) -> int:
        """Delete completed / failed / cancelled jobs older than *days*."""
        with self._session(db) as (session, _owned):
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                days=days
            )
            deleted = (
                session.query(JobDbRecord)
                .filter(
                    JobDbRecord.status.in_(_TERMINAL),
                    JobDbRecord.updated_at < cutoff,
                )
                .delete(synchronize_session=False)
            )
            if deleted:
                logger.info("Cleaned up %d old job record(s)", deleted)
            return deleted


# Module-level singleton
job_store = JobStore()