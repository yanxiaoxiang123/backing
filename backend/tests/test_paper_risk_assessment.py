from datetime import date, datetime, timedelta, timezone
import hashlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.agent_runtime import artifacts
from app.agent_runtime.graphs.experts import portfolio_risk_node
from app.agent_runtime.runtime import NodeContext
from app.agent_runtime.stores import create_stores
from app.domain.risk import PortfolioRiskRequest
from app.models.agent_runtime import AgentRun, AgentStep, ApprovalRecord
from app.models.paper_trading import PaperAccount, PaperOrder
from app.services.market_data import store_bars, store_calendar, store_security
from app.services import paper_risk_assessment as service
from app.config import Base
from test_backtest_executor import seed_market_data

NOW = datetime(2026, 10, 30, 8, tzinfo=timezone.utc)


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz else NOW.replace(tzinfo=None)


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "datetime", FixedClock)
    monkeypatch.setattr(artifacts, "_ROOT", tmp_path / "artifacts")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_market_data(db)
        db.add(AgentRun(run_id="risk-test", objective="明确目标的风险评估", status="running"))
        db.add(PaperAccount(account_id="default", cash=100000, initial_cash=100000))
        start = date(2026, 9, 30)
        store_calendar(db, "sh", [{"date": start + timedelta(days=i),
                                   "is_open": (start + timedelta(days=i)).weekday() < 5}
                                  for i in range(31)], provider="fixture")
        store_security(db, {"stock_code": "sh.600000", "name": "A", "status": "listed",
                            "listed_on": "2020-01-01", "effective_date": "2026-10-29"},
                       provider="fixture", observed_at=NOW - timedelta(days=1))
        store_bars(db, "sh.600000", [{"date": "2026-10-30", "open": 10, "high": 11,
                                      "low": 9, "close": 10, "volume": 1000000}],
                   provider="fixture", observed_at=NOW - timedelta(minutes=1))
        db.commit()
        yield db
    engine.dispose()


def intent():
    return PortfolioRiskRequest(targets=[{"stock_code": "sh.600000", "target_weight": 0.1,
                                          "stop_loss_pct": 0.05, "reason": "明确用户目标"}])


def test_assessment_uses_server_facts_and_never_creates_orders_or_approvals(db):
    report = service.assess_paper_risk(db, "risk-test", intent())
    assert not report["proposal"]["rejected"]
    assert report["orders"][0]["quantity"] == 1000
    assert report["evidence"]["account"]["cash"] == 100000
    assert report["artifact_id"]
    assert db.query(PaperOrder).count() == db.query(ApprovalRecord).count() == 0


def test_persisted_intent_drives_risk_node_instead_of_a_demonstration_allocation(db):
    service.save_risk_request(db, "risk-test", intent())
    step = AgentStep(run_id="risk-test", seq=1, node="portfolio_risk", status="running")
    db.add(step)
    db.commit()
    ctx = NodeContext(run_id="risk-test", seq=1, node="portfolio_risk", step_db_id=step.id,
                       stores=create_stores(db), db=db, as_of=NOW)
    output = portfolio_risk_node("sh.600000").run(ctx)["output"]
    assert not output["rejected"]
    assert output["positions"][0]["code"] == "sh.600000"
    assert 0 < output["positions"][0]["weight"] <= 0.1 + 0.0001


def test_old_assessment_artifact_remains_verifiable_after_a_new_assessment(db):
    first = service.assess_paper_risk(db, "risk-test", intent())
    path = artifacts.workspace_dir("risk-test") / f"risk-{first['evidence_sha256']}.json"
    content = path.read_bytes()
    account = db.query(PaperAccount).one()
    account.cash = 50000
    db.commit()
    second = service.assess_paper_risk(db, "risk-test", intent())
    assert second["evidence_sha256"] != first["evidence_sha256"]
    assert path.read_bytes() == content


def test_current_account_cannot_be_backdated_and_mid_collection_changes_fail_closed(db, monkeypatch):
    with pytest.raises(ValueError, match="historical/future"):
        service.assess_paper_risk(db, "risk-test", intent(), as_of=NOW - timedelta(days=1))
    revisions = iter(["before", "after"])
    monkeypatch.setattr(service, "_account_revision", lambda db: next(revisions))
    with pytest.raises(ValueError, match="changed while collecting"):
        service.assess_paper_risk(db, "risk-test", intent())


def test_risk_endpoint_requires_auth_and_persists_authenticated_evidence(db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.sessions import SessionMiddleware
    from app.agent_api.paper import router
    from app.config import get_db, settings

    monkeypatch.setattr(settings, "API_KEY", "risk-test-key")
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-only")
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        body = intent().model_dump(mode="json")
        assert client.post("/api/v1/agent-runs/risk-test/risk", json=body).status_code == 401
        response = client.post("/api/v1/agent-runs/risk-test/risk", json=body,
                               headers={"X-API-Key": "risk-test-key"})
        assert response.status_code == 200
        assert not response.json()["proposal"]["rejected"]
        assert response.json()["artifact_id"]


def test_tampered_risk_intent_is_rejected(db):
    row = service.save_risk_request(db, "risk-test", intent())
    path = artifacts.workspace_dir("risk-test") / artifacts.filename_of(row["uri"])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row["checksum"]
    path.write_text('{"targets": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        service.assess_saved_risk_request(db, "risk-test")
