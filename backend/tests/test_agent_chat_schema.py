"""T1 数据模型与迁移：agent_chat_threads / agent_chat_turns / agent_chat_events。

规格 2026-08-18 决策 D4（agent 工作台聊天化）：
- 三张新表在迁移后存在，且具备 D4 要求的列、唯一约束与外键。
- ``agent_runs.thread_id`` 带索引（右栏“最近 run”按 thread 查询加速）。
- 迁移可正反向：upgrade -> downgrade -1 -> upgrade 后状态干净、无 drift。
- 模型注册进 ``app.config.Base`` 并可从 ``app.models`` 导入；
  ``Idempotency-Key`` 与 ``(turn_id, seq)`` 唯一约束在 ORM 层真实生效。

测试模式复用 tests/test_migrations.py：真实 alembic env + 临时 SQLite 库。
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Base, settings

BACKEND = Path(__file__).resolve().parents[1]

CHAT_TABLES = ("agent_chat_threads", "agent_chat_turns", "agent_chat_events")
THREAD_ID_INDEX = "ix_agent_runs_thread_id"


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
    url = f"sqlite:///{tmp_path / 'agent_chat_test.db'}"
    original = settings.DATABASE_URL
    settings.DATABASE_URL = url
    yield url
    settings.DATABASE_URL = original


def _unique_index_columns(insp, table: str) -> set:
    return {
        tuple(ix["column_names"]) for ix in insp.get_indexes(table) if ix["unique"]
    }


def test_models_registered_on_base() -> None:
    from app.models import AgentChatEvent, AgentChatThread, AgentChatTurn

    assert AgentChatThread.__tablename__ == "agent_chat_threads"
    assert AgentChatTurn.__tablename__ == "agent_chat_turns"
    assert AgentChatEvent.__tablename__ == "agent_chat_events"
    for table in CHAT_TABLES:
        assert table in Base.metadata.tables


def test_upgrade_creates_chat_tables_with_d4_shape(db_url) -> None:
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    try:
        insp = inspect(engine)
        assert set(CHAT_TABLES) <= set(insp.get_table_names())

        thread_cols = {c["name"] for c in insp.get_columns("agent_chat_threads")}
        assert {
            "thread_id",
            "session_id",
            "title",
            "status",
            "last_run_id",
            "archived",
            "created_at",
            "updated_at",
        } <= thread_cols

        turn_cols = {c["name"] for c in insp.get_columns("agent_chat_turns")}
        assert {
            "thread_id",
            "user_input",
            "context_json",
            "status",
            "final_reply",
            "finish_reason",
            "error",
            "idempotency_key",
            "created_at",
            "updated_at",
        } <= turn_cols

        event_cols = {c["name"] for c in insp.get_columns("agent_chat_events")}
        assert {"turn_id", "seq", "event_type", "payload", "created_at"} <= event_cols

        # D4：thread_id 唯一、Idempotency-Key 唯一（SQLite 反射为唯一索引）。
        assert ("thread_id",) in _unique_index_columns(insp, "agent_chat_threads")
        assert ("idempotency_key",) in _unique_index_columns(insp, "agent_chat_turns")

        # D4：turns.thread_id / events.turn_id 外键。
        turn_fks = insp.get_foreign_keys("agent_chat_turns")
        assert {fk["referred_table"] for fk in turn_fks} == {"agent_chat_threads"}
        event_fks = insp.get_foreign_keys("agent_chat_events")
        assert {fk["referred_table"] for fk in event_fks} == {"agent_chat_turns"}

        # 状态机检查约束（与既有 ck_* 命名一致）。
        thread_checks = {
            ck["name"] for ck in insp.get_check_constraints("agent_chat_threads")
        }
        assert "ck_agent_chat_threads_status" in thread_checks
        turn_checks = {
            ck["name"] for ck in insp.get_check_constraints("agent_chat_turns")
        }
        assert "ck_agent_chat_turns_status" in turn_checks
    finally:
        engine.dispose()


def test_agent_runs_thread_id_indexed(db_url) -> None:
    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    try:
        indexes = {ix["name"] for ix in inspect(engine).get_indexes("agent_runs")}
    finally:
        engine.dispose()

    assert THREAD_ID_INDEX in indexes


def test_migration_reversible(db_url) -> None:
    cfg = _alembic_config(db_url)

    command.upgrade(cfg, "head")
    # The repository now has a later backtest snapshot migration; explicitly
    # downgrade past the chat migration instead of relying on ``-1``.
    command.downgrade(cfg, "20260817_02")

    engine = create_engine(db_url)
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert not (set(CHAT_TABLES) & tables), "downgrade 应删除三张新表"
        assert "agent_runs" in tables, "downgrade 不得影响既有表"
        indexes = {ix["name"] for ix in insp.get_indexes("agent_runs")}
        assert THREAD_ID_INDEX not in indexes
    finally:
        engine.dispose()

    # 再次升级：新表恢复，且全库 schema 与模型零 drift。
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    try:
        assert set(CHAT_TABLES) <= set(inspect(engine).get_table_names())
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == [], f"Schema drift after re-upgrade: {diff}"
    finally:
        engine.dispose()


def _add_thread_and_turn(session: Session) -> None:
    from app.models import AgentChatThread, AgentChatTurn

    session.add(AgentChatThread(thread_id="thr-1", session_id="sess-1"))
    session.add(
        AgentChatTurn(
            turn_id="turn-1",
            thread_id="thr-1",
            user_input="分析 600519",
            idempotency_key="key-1",
        )
    )
    session.flush()


def test_idempotency_key_unique_constraint_enforced() -> None:
    """US-C8：同一 Idempotency-Key 重复提交必须被唯一约束拦截。"""
    from app.models import AgentChatTurn

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            _add_thread_and_turn(session)
            session.add(
                AgentChatTurn(
                    turn_id="turn-2",
                    thread_id="thr-1",
                    user_input="重复提交",
                    idempotency_key="key-1",
                )
            )
            with pytest.raises(IntegrityError):
                session.flush()
    finally:
        engine.dispose()


def test_event_seq_unique_constraint_enforced() -> None:
    """US-C3：(turn_id, seq) 唯一，事件重放不丢不重。"""
    from app.models import AgentChatEvent

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            _add_thread_and_turn(session)
            session.add(
                AgentChatEvent(
                    turn_id="turn-1",
                    seq=1,
                    event_type="assistant",
                    payload={"text": "你好"},
                )
            )
            session.flush()
            session.add(
                AgentChatEvent(
                    turn_id="turn-1",
                    seq=1,
                    event_type="assistant",
                    payload={"text": "重复序号"},
                )
            )
            with pytest.raises(IntegrityError):
                session.flush()
    finally:
        engine.dispose()
