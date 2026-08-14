"""数据生命周期维护：清理过期任务/分析/回测、归档 K 线、SQLite 备份。

对应 PROJECT_AUDIT「数据模型」项的最后一节：
- 任务结果清理：``cleanup_old_jobs``
- 分析记录保留期：``purge_old_analysis``
- 回测结果保留期：``purge_old_backtests``
- K 线归档策略：``archive_klines``（移入 daily_klines_archive）
- 数据库备份：``backup_database``（SQLite 文件复制；MySQL 用 mysqldump）

由 ``backend/maintenance_cli.py`` 调用，可挂 systemd timer 每日执行
（见 deploy/systemd/stockbacking-maintenance.timer）。
"""

from __future__ import annotations

import logging
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from app.config import SessionLocal, engine, settings
from app.models.analysis import AnalysisRecord
from app.models.models import BacktestResult, DailyKline, KlineArchive
from app.services.job_store import job_store

logger = logging.getLogger(__name__)

# 默认保留期（天）
DEFAULT_JOB_RETENTION_DAYS = 30
DEFAULT_ANALYSIS_RETENTION_DAYS = 180
DEFAULT_BACKTEST_RETENTION_DAYS = 365


def _utcnow() -> datetime:
    """Naive UTC now — matches DB datetime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _session(db=None):
    """Yield (session, owned). Owned sessions commit/rollback/close."""
    if db is not None:
        return db, False
    session = SessionLocal()
    return session, True


# ---------------------------------------------------------------------------
# 清理
# ---------------------------------------------------------------------------


def cleanup_old_jobs(days: int = DEFAULT_JOB_RETENTION_DAYS) -> int:
    """删除超过保留期的终态任务记录（completed/failed/cancelled）。"""
    deleted = job_store.cleanup_old(days=days)
    if deleted:
        logger.info("maintenance: purged %d job records older than %s days", deleted, days)
    return deleted


def purge_old_analysis(days: int = DEFAULT_ANALYSIS_RETENTION_DAYS, *, db=None) -> int:
    """删除超过保留期的分析记录。"""
    cutoff = _utcnow() - timedelta(days=days)
    session, owned = _session(db)
    try:
        deleted = (
            session.query(AnalysisRecord)
            .filter(AnalysisRecord.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        if owned:
            session.commit()
        if deleted:
            logger.info("maintenance: purged %d analysis records older than %s days", deleted, days)
        return deleted
    except Exception:
        if owned:
            session.rollback()
        raise
    finally:
        if owned:
            session.close()


def purge_old_backtests(days: int = DEFAULT_BACKTEST_RETENTION_DAYS, *, db=None) -> int:
    """删除超过保留期的回测结果（交易明细随 FK CASCADE 一并清理）。"""
    cutoff = _utcnow() - timedelta(days=days)
    session, owned = _session(db)
    try:
        deleted = (
            session.query(BacktestResult)
            .filter(BacktestResult.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        if owned:
            session.commit()
        if deleted:
            logger.info("maintenance: purged %d backtest results older than %s days", deleted, days)
        return deleted
    except Exception:
        if owned:
            session.rollback()
        raise
    finally:
        if owned:
            session.close()


# ---------------------------------------------------------------------------
# K 线归档
# ---------------------------------------------------------------------------


def archive_klines(before_date: date, *, db=None) -> dict:
    """把 *before_date* 之前的日 K 线移入归档表（同一事务，先插后删）。

    Returns:
        {"archived": int, "remaining": int}
    """
    session, owned = _session(db)
    try:
        rows = (
            session.query(DailyKline)
            .filter(DailyKline.date < before_date)
            .all()
        )
        if rows:
            session.add_all(
                [
                    KlineArchive(
                        stock_code=r.stock_code,
                        date=r.date,
                        open=r.open,
                        high=r.high,
                        low=r.low,
                        close=r.close,
                        volume=r.volume,
                        amount=r.amount,
                    )
                    for r in rows
                ]
            )
            ids = [r.id for r in rows]
            (
                session.query(DailyKline)
                .filter(DailyKline.id.in_(ids))
                .delete(synchronize_session=False)
            )
        remaining = session.query(DailyKline).count()
        if owned:
            session.commit()
        logger.info(
            "maintenance: archived %d klines before %s, %d remaining",
            len(rows), before_date, remaining,
        )
        return {"archived": len(rows), "remaining": remaining}
    except Exception:
        if owned:
            session.rollback()
        raise
    finally:
        if owned:
            session.close()


# ---------------------------------------------------------------------------
# 备份 / 恢复
# ---------------------------------------------------------------------------


def backup_database(out_path: Path) -> Path:
    """复制 SQLite 数据库文件（先 checkpoint WAL，保证一致性）。

    MySQL 生产库请改用 ``mysqldump``（文档见 README「数据生命周期」）。
    恢复演练：停服 -> 用备份文件覆盖数据库 -> 起服 -> ``alembic upgrade head``
    校验版本 -> 抽查计数。
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        raise NotImplementedError(
            "backup_database only supports SQLite; use mysqldump for MySQL"
        )
    db_path = Path(engine.url.database)
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    shutil.copy2(db_path, out_path)
    logger.info("maintenance: backed up %s -> %s", db_path, out_path)
    return out_path


def run_all(*, archive_klines_before: date | None = None) -> dict:
    """默认保留期执行全部清理（挂 systemd timer 的入口）。"""
    report = {
        "jobs_purged": cleanup_old_jobs(),
        "analysis_purged": purge_old_analysis(),
        "backtests_purged": purge_old_backtests(),
    }
    if archive_klines_before is not None:
        report["klines_archived"] = archive_klines(archive_klines_before)
    logger.info("maintenance run_all finished: %s", report)
    return report
