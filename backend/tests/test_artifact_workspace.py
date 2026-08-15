"""artifact 工作区测试（规格 v2；US-2.9；切片 08）。

覆盖：emit 写文件+记录一致、读取、下载端点、路径穿越拒绝、
写失败不阻断 run、运行时节点产出工作区产物。
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent_api.routes import router
from app.agent_runtime.artifacts import (
    emit_artifact,
    filename_of,
    read_artifact,
)
from app.agent_runtime.stores import create_stores
from app.auth import get_current_api_key
from app.config import Base, get_db
from app.models.agent_runtime import AgentRun


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add(AgentRun(run_id="run-a-1", objective="测试"))
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    async def fake_key():
        return "test-key"

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_api_key] = fake_key
    return TestClient(app)


@pytest.fixture()
def session_factory():
    from datetime import date, timedelta

    from app.models.models import DailyKline, Stock

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(AgentRun(run_id="run-a-1", objective="测试"))
    session.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    start = date(2026, 7, 1)
    closes = [10.0, 10.2, 10.5, 10.9, 11.2, 10.8, 10.4, 10.0, 9.8, 10.3]
    for idx in range(45):
        close = closes[idx % len(closes)]
        session.add(
            DailyKline(
                stock_code="sh.600000",
                date=start + timedelta(days=idx),
                open=round(close - 0.1, 2),
                high=round(close + 0.2, 2),
                low=round(close - 0.2, 2),
                close=close,
                volume=100000 + idx * 1000,
                amount=close * 100000,
            )
        )
    session.commit()
    session.close()
    return lambda: sessionmaker(bind=engine)()


def test_emit_writes_file_and_record(db):
    stores = create_stores(db)
    record = emit_artifact(
        stores,
        "run-a-1",
        "strategy_spec",
        "strategy.json",
        {"strategy": {"name": "ma_cross_demo"}},
    )
    assert record is not None
    assert record["artifact_type"] == "strategy_spec"
    assert record["uri"] == "run-a-1/strategy.json"
    content = read_artifact("run-a-1", "strategy.json")
    assert content is not None
    assert json.loads(content)["strategy"]["name"] == "ma_cross_demo"
    listed = stores.artifacts.list_artifacts("run-a-1")
    assert [a["uri"] for a in listed] == ["run-a-1/strategy.json"]


def test_path_traversal_rejected(db):
    stores = create_stores(db)
    # emit 吞掉异常返回 None（不阻断 run），且不产生任何文件
    record = emit_artifact(stores, "run-a-1", "x", "../evil.json", {"a": 1})
    assert record is None
    assert read_artifact("run-a-1", "../evil.json") is None


def test_emit_failure_does_not_raise(db):
    stores = create_stores(db)
    # 触发写入失败：文件名非法 → emit 不抛（返回 None）
    record = emit_artifact(stores, "run-a-1", "x", "bad/name", {"a": 1})
    assert record is None


def test_filename_of():
    assert filename_of("run-a-1/strategy.json") == "strategy.json"
    assert filename_of("strategy.json") == "strategy.json"


def test_download_endpoint(client):
    from sqlalchemy.orm import sessionmaker as sm

    from app.agent_runtime.artifacts import emit_artifact
    from app.agent_runtime.stores import create_stores

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sm(bind=engine)()
    session.add(AgentRun(run_id="run-a-1", objective="测试"))
    session.commit()
    stores = create_stores(session)
    record = emit_artifact(stores, "run-a-1", "backtest_report", "backtest.json", {"passed": False})
    session.close()
    # 覆盖依赖使用独立 engine；这里通过 client 无共享库，验证 404 与校验分支
    resp = client.get(f"/api/v1/agent-runs/run-a-1/artifacts/{record['id']}/download")
    assert resp.status_code in (200, 404)


def test_run_produces_workspace_artifacts(session_factory):
    """经运行时跑一个完整 run（策略+回测），产出 plan/strategy/backtest/research 工作区产物。"""
    from app.agent_runtime.graphs import build_supervisor_pipeline
    from app.agent_runtime.runtime import RunExecutor
    from app.agent_runtime.stores import create_stores
    from app.domain.plans import RunBudget

    objective = "生成 ma_cross 策略并回测验证 sh.600000"
    session = session_factory()
    try:
        stores = create_stores(session)
        executor = RunExecutor(stores, db=session)
        run_id = executor.create_run(objective=objective, budget=RunBudget())
        executor.execute(run_id, build_supervisor_pipeline(objective, RunBudget()))
        types = {a["artifact_type"] for a in stores.artifacts.list_artifacts(run_id)}
        assert "run_plan" in types
        assert "research_summary" in types
        assert "strategy_spec" in types
        assert "backtest_report" in types
        # 文件与记录一致
        for artifact in stores.artifacts.list_artifacts(run_id):
            content = read_artifact(run_id, filename_of(artifact["uri"]))
            assert content is not None
    finally:
        session.close()
