"""Agent 运行时 repository 测试（任务 04 验收）。

覆盖：五类 store 的 CRUD、(run_id, seq) 唯一、JSON 往返、枚举 CheckConstraint、
外键级联清理、repository 接口可替换性（同一套测试只依赖协议）。
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.agent_runtime.stores import create_stores
from app.config import Base


def _engine(fk_enabled: bool = True):
    engine = create_engine("sqlite:///:memory:")
    if fk_enabled:

        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _rec):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def stores():
    engine = _engine()
    session = sessionmaker(bind=engine)()
    yield create_stores(session)
    session.close()


def _seed_run(stores, run_id="run-001"):
    return stores.runs.create_run(
        run_id=run_id,
        objective="研究 sh.600519",
        budget_json={"max_rounds": 5, "max_tool_calls": 10},
        thread_id="thread-1",
        snapshot_id="snap-1",
    )


# ---------- RunStore ----------

def test_run_create_and_get(stores):
    run = _seed_run(stores)
    assert run["run_id"] == "run-001"
    assert run["status"] == "planned"
    fetched = stores.runs.get_run("run-001")
    assert fetched is not None
    assert fetched["budget_json"] == {"max_rounds": 5, "max_tool_calls": 10}
    assert fetched["thread_id"] == "thread-1"
    assert stores.runs.get_run("missing") is None


def test_run_update_status_and_error(stores):
    _seed_run(stores)
    now = datetime.now(timezone.utc)
    assert stores.runs.update_run_status(
        "run-001", "failed", error="预算超限", finished_at=now.isoformat()
    )
    fetched = stores.runs.get_run("run-001")
    assert fetched["status"] == "failed"
    assert fetched["error"] == "预算超限"
    assert fetched["finished_at"] is not None
    assert stores.runs.update_run_status("missing", "failed") is False


def test_run_list_filter_by_status(stores):
    _seed_run(stores, "run-a")
    _seed_run(stores, "run-b")
    stores.runs.update_run_status("run-b", "running")
    assert {r["run_id"] for r in stores.runs.list_runs()} == {"run-a", "run-b"}
    assert {r["run_id"] for r in stores.runs.list_runs(status="running")} == {"run-b"}
    assert len(stores.runs.list_runs(limit=1)) == 1


def test_run_invalid_status_rejected(stores):
    with pytest.raises(IntegrityError):
        stores.runs.create_run(run_id="bad", objective="x", status="nonsense")


# ---------- StepStore ----------

def test_step_create_get_unique_seq(stores):
    _seed_run(stores)
    step = stores.steps.create_step(run_id="run-001", seq=1, node="data_qa")
    assert step["status"] == "pending"
    assert stores.steps.get_step("run-001", 1)["node"] == "data_qa"
    assert stores.steps.get_step("run-001", 9) is None
    with pytest.raises(IntegrityError):
        stores.steps.create_step(run_id="run-001", seq=1, node="dup")


def test_step_update_status_with_output(stores):
    _seed_run(stores)
    stores.steps.create_step(run_id="run-001", seq=1, node="research")
    assert stores.steps.update_step_status(
        "run-001",
        1,
        "completed",
        output_schema="ResearchClaim",
        output_json={"claims": []},
        duration_s=1.2,
        tokens_used=100,
    )
    step = stores.steps.get_step("run-001", 1)
    assert step["status"] == "completed"
    assert step["output_schema"] == "ResearchClaim"
    assert step["output_json"] == {"claims": []}
    assert step["tokens_used"] == 100
    assert stores.steps.update_step_status("run-001", 9, "completed") is False


def test_step_list_ordered(stores):
    _seed_run(stores)
    stores.steps.create_step(run_id="run-001", seq=2, node="b")
    stores.steps.create_step(run_id="run-001", seq=1, node="a")
    steps = stores.steps.list_steps("run-001")
    assert [s["seq"] for s in steps] == [1, 2]


# ---------- ToolCallStore ----------

def test_tool_call_create_and_list(stores):
    _seed_run(stores)
    tc = stores.tool_calls.create_tool_call(
        run_id="run-001",
        tool_name="market.kline",
        params_hash="abc123",
        params_json={"code": "sh.600519"},
        permission="read",
    )
    assert tc["tool_name"] == "market.kline"
    calls = stores.tool_calls.list_tool_calls("run-001")
    assert len(calls) == 1
    assert calls[0]["params_json"] == {"code": "sh.600519"}


def test_tool_call_invalid_permission_rejected(stores):
    _seed_run(stores)
    with pytest.raises(IntegrityError):
        stores.tool_calls.create_tool_call(
            run_id="run-001",
            tool_name="x",
            params_hash="h",
            params_json={},
            permission="root",
        )


# ---------- ArtifactStore ----------

def test_artifact_create_and_list(stores):
    _seed_run(stores)
    art = stores.artifacts.create_artifact(
        run_id="run-001",
        artifact_type="kline_parquet",
        uri="artifacts/run-001/kline.parquet",
        checksum="deadbeef",
        source_id="kline-1",
        schema_version="1.0.0",
    )
    assert art["checksum"] == "deadbeef"
    arts = stores.artifacts.list_artifacts("run-001")
    assert len(arts) == 1
    assert arts[0]["source_id"] == "kline-1"


# ---------- ApprovalStore ----------

def test_approval_lifecycle(stores):
    _seed_run(stores)
    appr = stores.approvals.create_approval(
        run_id="run-001",
        action="execution.paper.order",
        summary="买入 sh.600519 100股",
        direction="buy",
        target_position_pct=0.05,
        risk_summary="测试风险",
    )
    assert appr["status"] == "pending"
    assert stores.approvals.update_approval_status(
        appr["id"], "approved", decided_by="tester"
    )
    fetched = stores.approvals.get_approval(appr["id"])
    assert fetched["status"] == "approved"
    assert fetched["decided_by"] == "tester"
    assert stores.approvals.get_approval(9999) is None


def test_approval_invalid_status_rejected(stores):
    _seed_run(stores)
    with pytest.raises(IntegrityError):
        stores.approvals.create_approval(
            run_id="run-001", action="x", summary="y", status="maybe"
        )


# ---------- 外键级联 ----------

def test_run_delete_cascades_children(stores):
    _seed_run(stores)
    stores.steps.create_step(run_id="run-001", seq=1, node="research")
    stores.tool_calls.create_tool_call(
        run_id="run-001", tool_name="t", params_hash="h", params_json={}
    )
    stores.artifacts.create_artifact(run_id="run-001", artifact_type="t", uri="u")
    stores.approvals.create_approval(run_id="run-001", action="a", summary="s")

    stores.runs.update_run_status("run-001", "cancelled")
    # 直接删除 run 行验证级联（repository 层面由后续 run 生命周期管理）
    from app.models.agent_runtime import AgentRun

    session = stores.runs.session  # type: ignore[attr-defined]
    row = session.query(AgentRun).filter(AgentRun.run_id == "run-001").one()
    session.delete(row)
    session.commit()

    assert stores.steps.list_steps("run-001") == []
    assert stores.tool_calls.list_tool_calls("run-001") == []
    assert stores.artifacts.list_artifacts("run-001") == []
    assert stores.approvals.list_approvals("run-001") == []
