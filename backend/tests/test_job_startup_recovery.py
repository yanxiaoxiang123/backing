from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.models.models import JobDbRecord
from app.services.job_store import JobStore


def test_starting_another_worker_preserves_pending_and_live_leased_jobs():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with sessionmaker(bind=engine)() as db:
        db.add_all([
            JobDbRecord(id="queued", job_type="test", status="pending"),
            JobDbRecord(id="alive", job_type="test", status="running", lease_until=now + timedelta(minutes=5)),
            JobDbRecord(id="expired", job_type="test", status="running", lease_until=now - timedelta(minutes=5)),
        ])
        db.commit()
        assert JobStore().reset_stale_jobs(db=db) == 1
        db.commit()
        db.expire_all()
        assert db.get(JobDbRecord, "queued").status == "pending"
        assert db.get(JobDbRecord, "alive").status == "running"
        assert db.get(JobDbRecord, "expired").status == "pending"
    engine.dispose()
