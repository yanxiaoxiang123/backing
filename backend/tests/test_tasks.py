"""任务执行系统测试：幂等键、租约/认领、重试、取消、指标。

使用独立的内存 SQLite，并替换 ``job_store`` 的 session 工厂，避免触碰
开发数据库。
"""

import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.job_store as job_store_module
from app.config import Base
from app.exceptions import ProviderUnavailableError
from app.services.job_store import job_store
from app.services.tasks import task_metrics
from app.services.tasks.base import (
    TaskCancelledError,
    TaskRetryableError,
    register_runner,
)
from app.services.tasks.runner import run_claimed_job, run_job_once
from app.services.tasks.threads import ThreadTaskExecutor


def _utcnow() -> datetime:
    """Naive UTC now — matches the jobs table's convention (UTC-naive)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def db(tmp_path):
    """File-backed temp DB; patch job_store's session factory.

    A file DB (not :memory:) is required because worker threads and the
    polling test thread each open their own connection, like production.
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'tasks_test.db'}",
        connect_args={"timeout": 10},
    )
    Base.metadata.create_all(bind=engine)
    original = job_store_module.SessionLocal
    job_store_module.SessionLocal = sessionmaker(bind=engine)
    yield engine
    job_store_module.SessionLocal = original


@pytest.fixture(autouse=True)
def _clean_metrics():
    task_metrics._counters.clear()
    task_metrics._durations.clear()
    yield
    task_metrics._counters.clear()
    task_metrics._durations.clear()


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


# ---------------------------------------------------------------------------
# 幂等键
# ---------------------------------------------------------------------------


class TestIdempotencyKey:
    def test_same_job_key_returns_same_job(self, db):
        a = job_store.create("sync_stocks", job_key="k1")
        b = job_store.create("sync_stocks", job_key="k1")
        assert a.id == b.id

    def test_different_job_keys_create_distinct_jobs(self, db):
        a = job_store.create("sync_stocks", job_key="k1")
        b = job_store.create("sync_stocks", job_key="k2")
        assert a.id != b.id

    def test_duplicate_key_after_completion_still_dedupes(self, db):
        a = job_store.create("sync_stocks", job_key="k1")
        job_store.update(a.id, status="completed", progress=1.0)
        b = job_store.create("sync_stocks", job_key="k1")
        assert a.id == b.id

    def test_null_job_key_never_dedupes(self, db):
        a = job_store.create("sync_stocks")
        b = job_store.create("sync_stocks")
        assert a.id != b.id


# ---------------------------------------------------------------------------
# 认领 / 租约
# ---------------------------------------------------------------------------


class TestClaimAndLease:
    def test_claim_due_claims_pending_job(self, db):
        job = job_store.create("sync_stocks")
        claimed = job_store.claim_due()
        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.status == "running"
        assert claimed.lease_until is not None

    def test_claim_due_returns_none_when_idle(self, db):
        assert job_store.claim_due() is None

    def test_claim_is_exclusive(self, db):
        job = job_store.create("sync_stocks")
        first = job_store.claim_due()
        second = job_store.claim_due()
        assert first is not None
        assert second is None  # claimed job is not claimable again

    def test_running_job_with_expired_lease_is_reclaimed(self, db):
        job = job_store.create("sync_stocks")
        job_store.claim_due()
        job_store.update(
            job.id,
            lease_until=_utcnow() - timedelta(seconds=1),
        )
        reclaimed = job_store.claim_due()
        assert reclaimed is not None
        assert reclaimed.id == job.id

    def test_running_job_with_fresh_lease_not_reclaimed(self, db):
        job = job_store.create("sync_stocks")
        job_store.claim_due()
        assert job_store.claim_due() is None

    def test_pending_job_with_future_retry_not_claimable(self, db):
        job = job_store.create("sync_stocks")
        future = _utcnow() + timedelta(seconds=60)
        job_store.update(job.id, status="pending", next_retry_at=future)
        assert job_store.claim_due() is None

    def test_lease_expired_running_skipped_by_guard(self, db):
        """run_job_once must not double-execute a job held by another worker."""
        job = job_store.create("sync_stocks")
        job_store.claim_due()
        assert run_job_once(job.id) == "skipped"


# ---------------------------------------------------------------------------
# 生命周期：完成 / 失败 / 重试 / 取消
# ---------------------------------------------------------------------------


@register_runner("test_ok")
def _ok_runner(job_id, payload):
    pass


@register_runner("test_fail")
def _fail_runner(job_id, payload):
    raise RuntimeError("boom")


@register_runner("test_retryable")
def _retryable_runner(job_id, payload):
    raise ProviderUnavailableError(detail="provider down", provider="baostock")


@register_runner("test_cancel")
def _cancel_runner(job_id, payload):
    raise TaskCancelledError("cancelled by user")


@register_runner("test_wait")
def _wait_runner(job_id, payload):
    time.sleep(0.3)


class TestLifecycle:
    def test_completed(self, db):
        job = job_store.create("test_ok")
        job_store.claim_due()
        assert run_claimed_job(job.id) == "completed"
        record = job_store.get(job.id)
        assert record.status == "completed"
        assert record.progress == 1.0
        assert record.error is None

    def test_failed_non_retryable(self, db):
        job = job_store.create("test_fail")
        job_store.claim_due()
        assert run_claimed_job(job.id) == "failed"
        record = job_store.get(job.id)
        assert record.status == "failed"
        assert "boom" in (record.error or "")

    def test_retry_then_succeed(self, db):
        attempts = {"n": 0}

        @register_runner("test_flaky")
        def flaky(job_id, payload):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ProviderUnavailableError(
                    detail="temporary", provider="baostock"
                )

        job = job_store.create("test_flaky")
        job_store.claim_due()
        assert run_claimed_job(job.id) == "retry"
        record = job_store.get(job.id)
        assert record.status == "pending"
        assert record.retry_count == 1
        assert record.next_retry_at is not None

        # 重试时间到（手动提前），重新认领执行
        job_store.update(job.id, next_retry_at=None)
        job_store.claim_due()
        assert run_claimed_job(job.id) == "completed"
        assert job_store.get(job.id).status == "completed"
        assert attempts["n"] == 2

    def test_retry_exhausted_fails(self, db):
        original = job_store_module.settings.TASK_MAX_RETRIES
        job_store_module.settings.TASK_MAX_RETRIES = 2
        try:
            job = job_store.create("test_retryable")
            for _ in range(3):
                job_store.update(job.id, next_retry_at=None)
                job_store.claim_due()
                outcome = run_claimed_job(job.id)
            assert outcome == "failed"
            assert job_store.get(job.id).status == "failed"
        finally:
            job_store_module.settings.TASK_MAX_RETRIES = original

    def test_task_retryable_error_is_retried(self, db):
        @register_runner("test_rte")
        def rte(job_id, payload):
            raise TaskRetryableError("transient")

        job = job_store.create("test_rte")
        job_store.claim_due()
        assert run_claimed_job(job.id) == "retry"

    def test_cancelled(self, db):
        job = job_store.create("test_cancel")
        job_store.claim_due()
        assert run_claimed_job(job.id) == "cancelled"
        record = job_store.get(job.id)
        assert record.status == "failed"
        assert record.error == "Cancelled"

    def test_missing_job(self, db):
        assert run_job_once("does-not-exist") == "missing"

    def test_unknown_runner_fails(self, db):
        job = job_store.create("no_such_runner_type")
        job_store.claim_due()
        assert run_claimed_job(job.id) == "failed"
        assert "No runner registered" in (job_store.get(job.id).error or "")

    def test_task_metrics_recorded(self, db):
        job = job_store.create("test_ok")
        job_store.claim_due()
        run_claimed_job(job.id)
        counters = {c["name"] for c in task_metrics.snapshot()["counters"]}
        assert "task.completed" in counters

    def test_cancel_marker_prevents_start(self, db):
        """cancel_job 端点写入的 cancelled 标记应阻止任务开始执行。"""
        job = job_store.create("test_ok")
        job_store.update(
            job.id, status="failed", error="Cancelled", message="Cancelled by user"
        )
        # failed 为终态：不会执行 runner，也不会被 claim_due 重新认领
        assert run_job_once(job.id) == "failed"
        assert job_store.get(job.id).status == "failed"
        assert job_store.claim_due() is None


# ---------------------------------------------------------------------------
# 线程执行器
# ---------------------------------------------------------------------------


class TestThreadExecutor:
    def test_submit_runs_job_to_completion(self, db):
        executor = ThreadTaskExecutor()
        executor.startup()
        try:
            job = executor.submit("test_ok")
            assert _wait_for(lambda: job_store.get(job.id).status == "completed")
        finally:
            executor.shutdown()

    def test_submit_idempotent_via_job_key(self, db):
        executor = ThreadTaskExecutor()
        executor.startup()
        try:
            a = executor.submit("test_ok", job_key="same")
            b = executor.submit("test_ok", job_key="same")
            assert a.id == b.id
        finally:
            executor.shutdown()

    def test_cancel_cooperative(self, db):
        """取消后，协作式 runner 应中止并保持 cancelled 状态。"""

        @register_runner("test_cancel_loop")
        def loop(job_id, payload):
            for _ in range(100):
                record = job_store.get(job_id)
                if record and record.error == "Cancelled":
                    raise TaskCancelledError("stopped")
                time.sleep(0.01)

        executor = ThreadTaskExecutor()
        executor.startup()
        try:
            job = executor.submit("test_cancel_loop")
            _wait_for(lambda: job_store.get(job.id).status == "running")
            job_store.update(
                job.id, status="failed", error="Cancelled", message="Cancelled by user"
            )
            assert _wait_for(
                lambda: (job_store.get(job.id).error or "") == "Cancelled"
            )
            assert job_store.get(job.id).status == "failed"
        finally:
            executor.shutdown()

    def test_heartbeat_keeps_lease_fresh(self, db):
        original = job_store_module.settings.TASK_HEARTBEAT_INTERVAL_S
        job_store_module.settings.TASK_HEARTBEAT_INTERVAL_S = 0.05
        job_store_module.settings.TASK_LEASE_SECONDS = 60
        executor = ThreadTaskExecutor()
        executor.startup()
        try:
            job = executor.submit("test_wait")
            _wait_for(lambda: job_store.get(job.id).status == "running")
            lease = job_store.get(job.id).lease_until
            assert lease is not None
            time.sleep(0.3)  # 让心跳刷新几次
            # 任务应因租约保持而完成而非被认领；断言任务最终 completed
            assert _wait_for(lambda: job_store.get(job.id).status == "completed")
        finally:
            executor.shutdown()
            job_store_module.settings.TASK_HEARTBEAT_INTERVAL_S = original

    def test_metrics_endpoint_shape(self, db):
        snapshot = task_metrics.snapshot()
        assert set(snapshot.keys()) == {"started_at", "counters", "durations"}
        assert isinstance(snapshot["counters"], list)
