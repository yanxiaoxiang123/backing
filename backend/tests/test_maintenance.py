"""数据生命周期维护测试：任务/分析/回测清理、K 线归档、SQLite 备份。"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.services.job_store as job_store_module
from app.config import Base
from app.models.analysis import AnalysisRecord
from app.models.models import (
    BacktestResult,
    BacktestTrade,
    DailyKline,
    JobDbRecord,
    Stock,
    Strategy,
)
from app.services import maintenance


@pytest.fixture()
def session(tmp_path):
    """文件型临时 DB（备份测试需要真实文件），启用外键以验证级联清理。"""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'maintenance_test.db'}",
        connect_args={"timeout": 10},
    )

    from sqlalchemy import event as sa_event

    @sa_event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    original = job_store_module.SessionLocal
    job_store_module.SessionLocal = sessionmaker(bind=engine)
    maintenance.SessionLocal = sessionmaker(bind=engine)
    maintenance.engine = engine
    yield sessionmaker(bind=engine)()
    maintenance.SessionLocal = original
    maintenance.engine = None


def _seed_stock(session):
    session.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    session.commit()


def _backdate(session, row, days):
    row.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    session.add(row)
    session.commit()


class TestPurge:
    def test_purge_old_analysis(self, session):
        for i, days in enumerate((10, 400)):
            session.add(
                AnalysisRecord(
                    stock_code="sh.600000",
                    analysis_date=date(2024, 1, 1),
                    mode="quick",
                    final_signal="hold",
                    final_confidence=0.5,
                    duration_s=1.0,
                )
            )
        session.commit()
        rows = session.query(AnalysisRecord).all()
        _backdate(session, rows[0], 400)  # 旧记录
        # 新记录保持默认 created_at
        deleted = maintenance.purge_old_analysis(days=180, db=session)
        assert deleted == 1
        assert session.query(AnalysisRecord).count() == 1

    def test_purge_old_backtests_cascades_trades(self, session):
        _seed_stock(session)
        session.add(Strategy(name="ma", strategy_type="ma_cross", parameters={}))
        session.commit()
        strategy = session.query(Strategy).first()
        result = BacktestResult(
            strategy_id=strategy.id,
            stock_code="sh.600000",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=100000,
            final_capital=100000,
            total_return=0,
            annual_return=0,
            total_trades=1,
        )
        session.add(result)
        session.commit()
        session.add(
            BacktestTrade(
                backtest_result_id=result.id,
                stock_code="sh.600000",
                trade_date=date(2024, 1, 2),
                action="buy",
                price=10,
                quantity=100,
                amount=1000,
            )
        )
        _backdate(session, result, 500)
        deleted = maintenance.purge_old_backtests(days=365, db=session)
        assert deleted == 1
        assert session.query(BacktestResult).count() == 0
        assert session.query(BacktestTrade).count() == 0

    def test_cleanup_old_jobs(self, session, tmp_path):
        engine = create_engine(
            f"sqlite:///{tmp_path / 'jobs_test.db'}", connect_args={"timeout": 10}
        )
        Base.metadata.create_all(bind=engine)
        original = job_store_module.SessionLocal
        job_store_module.SessionLocal = sessionmaker(bind=engine)
        try:
            job_store_module.job_store.create("sync_stocks")
            job = job_store_module.job_store.create("sync_stocks")
            job_store_module.job_store.update(job.id, status="completed", progress=1.0)
            old = job_store_module.job_store.get(job.id)
            with job_store_module.SessionLocal() as s:
                rec = (
                    s.query(JobDbRecord)
                    .filter(JobDbRecord.id == old.id)
                    .first()
                )
                rec.updated_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=400)
                s.commit()
            assert maintenance.cleanup_old_jobs(days=30) == 1
        finally:
            job_store_module.SessionLocal = original


class TestArchiveKlines:
    def test_archive_moves_old_klines(self, session):
        _seed_stock(session)
        session.add(
            DailyKline(
                stock_code="sh.600000", date=date(2014, 6, 30),
                open=1, high=2, low=1, close=1.5, volume=100,
            )
        )
        session.add(
            DailyKline(
                stock_code="sh.600000", date=date(2024, 6, 30),
                open=1, high=2, low=1, close=1.5, volume=100,
            )
        )
        session.commit()

        report = maintenance.archive_klines(date(2015, 1, 1), db=session)
        assert report["archived"] == 1
        assert report["remaining"] == 1

        remaining = session.query(DailyKline).all()
        assert [k.date for k in remaining] == [date(2024, 6, 30)]
        archived = session.query(maintenance.KlineArchive).all()
        assert len(archived) == 1
        assert archived[0].date == date(2014, 6, 30)
        assert archived[0].archived_at is not None


class TestBackup:
    def test_backup_copies_sqlite_file(self, tmp_path):
        import app.services.maintenance as maint

        src = tmp_path / "src.db"
        engine = create_engine(f"sqlite:///{src}", connect_args={"timeout": 10})
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO stocks (code, name, market) VALUES ('sh.600000','浦发银行','sh')"))
            conn.commit()
        engine.dispose()

        maint.engine = engine
        maint.settings = type("S", (), {"DATABASE_URL": f"sqlite:///{src}"})()
        out = tmp_path / "backup" / "restore" / "backing-test.db"
        result = maint.backup_database(out)
        assert result.exists()
        assert result.read_bytes() == src.read_bytes()

        # 恢复演练：用备份覆盖"生产"库后数据仍在
        restore_target = tmp_path / "restored.db"
        restore_target.write_bytes(result.read_bytes())
        engine2 = create_engine(f"sqlite:///{restore_target}")
        with engine2.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM stocks")).scalar()
        assert count == 1

    def test_backup_rejects_mysql(self, tmp_path):
        import app.services.maintenance as maint

        maint.engine = create_engine("sqlite:///:memory:")
        maint.settings = type("S", (), {"DATABASE_URL": "mysql+pymysql://u:p@h/db"})()
        with pytest.raises(NotImplementedError):
            maint.backup_database(tmp_path / "x.db")
