"""Migration chain regression tests.

Regression for: ``alembic upgrade head`` failing on SQLite with "No support
for ALTER of constraints in SQLite dialect", and startup ``create_all()``
masking missing migrations / drifted schema (see PROJECT_AUDIT issue 3).

Each test runs the real alembic env (``migrations/env.py``) against an
isolated temp SQLite database.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.config import Base, settings

BACKEND = Path(__file__).resolve().parents[1]


def _alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture()
def db_url(tmp_path) -> str:
    """Point alembic at an isolated temp SQLite DB for the duration of a test.

    ``migrations/env.py`` reads ``settings.DATABASE_URL`` and overrides the
    alembic url with it, so patching the settings instance is sufficient.
    """
    url = f"sqlite:///{tmp_path / 'migration_test.db'}"
    original = settings.DATABASE_URL
    settings.DATABASE_URL = url
    yield url
    settings.DATABASE_URL = original


def test_fresh_upgrade_reaches_head(db_url):
    """Empty DB must upgrade cleanly — this used to crash on
    op.create_foreign_key with "No support for ALTER of constraints".
    """
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert {
        "stocks",
        "daily_klines",
        "strategies",
        "backtest_results",
        "backtest_trades",
        "analysis_records",
        "user_watchlist",
        "jobs",
    } <= tables

    # The watchlist FK must exist, not just the table.
    engine = create_engine(db_url)
    try:
        fks = inspect(engine).get_foreign_keys("user_watchlist")
    finally:
        engine.dispose()
    assert [fk["referred_table"] for fk in fks] == ["stocks"]


def test_upgrade_downgrade_upgrade_roundtrip(db_url):
    """upgrade -> downgrade base -> upgrade must all succeed and leave a
    clean base (no leftover tables) in between.
    """
    cfg = _alembic_config(db_url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(db_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    # Only alembic's own version table may remain — alembic keeps it after
    # reaching base (it is re-ensured on the next run).
    assert tables <= {"alembic_version"}

    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    try:
        assert "user_watchlist" in inspect(engine).get_table_names()
        assert "jobs" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_schema_matches_models_after_upgrade(db_url):
    """The migrated schema must equal the SQLAlchemy models — this is the
    drift check that startup create_all() used to mask.
    """
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], f"Schema drift between migrations and models: {diff}"


def test_upgrade_repairs_drifted_watchlist_and_jobs(db_url):
    """Reproduce the reported production state and verify `upgrade head`
    repairs it in place:

    - DB stamped at 20260316_02 (chain broken)
    - user_watchlist present but without the FK (left by the failed migration)
    - jobs present (created by the old startup create_all(), untracked)
    """
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, "20260316_02")

    # Recreate the drift left behind by the broken migration + create_all().
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE user_watchlist ("
                " id INTEGER NOT NULL PRIMARY KEY,"
                " stock_code VARCHAR(20) NOT NULL,"
                " added_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX ix_user_watchlist_id ON user_watchlist (id)"
            )
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX ix_user_watchlist_stock_code "
                "ON user_watchlist (stock_code)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX idx_added_at ON user_watchlist (added_at)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE jobs ("
                " id VARCHAR(36) NOT NULL PRIMARY KEY,"
                " job_type VARCHAR(50) NOT NULL,"
                " status VARCHAR(20) NOT NULL,"
                " message TEXT NOT NULL,"
                " progress FLOAT NOT NULL,"
                " payload JSON, result JSON, error TEXT,"
                " created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                " updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.exec_driver_sql("CREATE INDEX ix_jobs_job_type ON jobs (job_type)")
            conn.exec_driver_sql("CREATE INDEX ix_jobs_status ON jobs (status)")
    finally:
        engine.dispose()

    # Must succeed without "table already exists" / ALTER errors.
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    try:
        insp = inspect(engine)
        # FK repaired via batch-mode table recreation.
        assert [fk["referred_table"] for fk in insp.get_foreign_keys("user_watchlist")] == [
            "stocks"
        ]
        assert "jobs" in insp.get_table_names()
        backtest_indexes = {i["name"] for i in insp.get_indexes("backtest_results")}
        assert "idx_backtest_stock_created" in backtest_indexes
        analysis_indexes = {i["name"] for i in insp.get_indexes("analysis_records")}
        assert "idx_analysis_stock_date" in analysis_indexes
    finally:
        engine.dispose()

    # And the repaired database still matches the models exactly.
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()
    assert diff == [], f"Schema drift after drift repair: {diff}"
