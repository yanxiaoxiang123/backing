from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.agent_runtime import artifacts
from app.agent_runtime.paper import service
from app.config import Base
from app.models.agent_runtime import AgentRun, ApprovalRecord
from app.models.paper_trading import PaperAccount, PaperOrder, PaperFill, PaperOrderEvent
from app.tools import execution
from app.tools.base import ToolContext
from paper_evidence import seed_paper_evidence, risk_assessment, propose_verified


@pytest.fixture
def ledger(monkeypatch, tmp_path):
    clock = [datetime(2026, 10, 30, 8, tzinfo=timezone.utc)]
    monkeypatch.setattr(execution, "_now", lambda: clock[0])
    monkeypatch.setattr(service, "_now_utc", lambda: clock[0])
    monkeypatch.setattr(artifacts, "_ROOT", tmp_path / "artifacts")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(AgentRun(run_id="paper-test", objective="Explicit paper risk test", status="completed"))
        seed_paper_evidence(db, clock[0])
        yield db, clock
    engine.dispose()


def invoke(db, artifact_id, quantity=100, run_id="paper-test"):
    params = execution.ProposeOrderParams(stock_code="sh.600000", side="buy", quantity=quantity,
                                          risk_artifact_id=artifact_id)
    return execution._propose_order(params, ToolContext(db=db, run_id=run_id))


def test_new_orders_require_a_provenance_reference(ledger):
    db, _ = ledger
    with pytest.raises(ValueError):
        execution.ProposeOrderParams(stock_code="sh.600000", side="buy", quantity=100)
    assert db.query(PaperOrder).count() == db.query(ApprovalRecord).count() == 0


def test_fixture_provides_completed_prices_between_1530_and_1600(ledger):
    db, clock = ledger
    clock[0] = clock[0].replace(hour=7, minute=45)
    report = risk_assessment(db, clock[0])
    assert not report["proposal"]["rejected"], report["proposal"]["rejection_reasons"]
    invoke(db, report["artifact_id"])
    assert db.query(PaperOrder).count() == 1


def test_unapproved_rejected_wrong_run_and_oversized_intents_cannot_create_orders(ledger):
    db, clock = ledger
    rejected = risk_assessment(db, clock[0], weight=0.9)
    with pytest.raises(ValueError, match="未通过"):
        invoke(db, rejected["artifact_id"])
    accepted = risk_assessment(db, clock[0])
    with pytest.raises(ValueError, match="数量"):
        invoke(db, accepted["artifact_id"], quantity=accepted["orders"][0]["quantity"] + 100)
    db.add(AgentRun(run_id="other-run", objective="other"))
    db.commit()
    with pytest.raises(ValueError, match="当前研究"):
        invoke(db, accepted["artifact_id"], run_id="other-run")
    assert db.query(PaperOrder).count() == 0


def test_proposal_revalidates_cash_and_prevents_reusing_the_same_intent(ledger):
    db, clock = ledger
    accepted = risk_assessment(db, clock[0])
    invoke(db, accepted["artifact_id"])
    with pytest.raises(ValueError, match="复核未通过"):
        invoke(db, accepted["artifact_id"])
    assert db.query(PaperOrder).count() == 1


def test_expired_or_tampered_evidence_never_creates_an_order(ledger):
    db, clock = ledger
    accepted = risk_assessment(db, clock[0])
    clock[0] += timedelta(minutes=6)
    with pytest.raises(ValueError, match="过期"):
        invoke(db, accepted["artifact_id"])
    clock[0] -= timedelta(minutes=6)
    path = artifacts.workspace_dir("paper-test") / f"risk-{accepted['evidence_sha256']}.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="校验失败"):
        invoke(db, accepted["artifact_id"])


def test_approval_rechecks_account_without_mutating_state_on_failure(ledger):
    db, clock = ledger
    order = propose_verified(db, clock[0])
    db.query(PaperAccount).one().cash = 1000
    db.commit()
    with pytest.raises(ValueError, match="复核未通过"):
        service.decide_approval(db, order["approval_id"], "approved")
    assert db.get(ApprovalRecord, order["approval_id"]).status == "pending"
    assert db.query(PaperOrder).one().status == "pending_approval"


def test_verified_full_lifecycle_records_three_risk_checks_and_only_one_fill(ledger):
    db, clock = ledger
    proposed = propose_verified(db, clock[0])
    decision = service.decide_approval(db, proposed["approval_id"], "approved")
    assert decision["target_trade_date"] == "2026-11-02"
    assert service.run_matching_cycle(db)["noop"] == 1
    clock[0] = datetime(2026, 11, 2, 8, tzinfo=timezone.utc)
    assert service.run_matching_cycle(db)["filled"] == 1
    assert service.run_matching_cycle(db)["processed"] == 0
    assert db.query(PaperFill).count() == 1
    events = db.query(PaperOrderEvent).order_by(PaperOrderEvent.seq).all()
    assert [row.detail_json["risk_check"]["stage"] for row in events] == ["propose", "approve", "fill"]
    proof = events[-1].detail_json["risk_check"]["assessment"]
    assert proof["evidence"]["execution_context"]["sh.600000"]["valuation"] == "session_open"
    assert proof["evidence"]["market"]["sh.600000"]["session"] == "2026-10-30"


def test_legacy_approved_orders_without_risk_evidence_expire(ledger):
    db, _ = ledger
    db.add(PaperOrder(order_id="legacy", run_id="paper-test", stock_code="sh.600000",
                      side="buy", quantity=100, status="approved"))
    db.commit()
    assert service.run_matching_cycle(db)["expired"] == 1
    assert db.query(PaperFill).count() == 0


def test_user_endpoint_only_proposes_a_bound_order_and_masks_api_credentials(ledger, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.sessions import SessionMiddleware
    from app.agent_api.paper import router
    from app.config import get_db, settings

    db, clock = ledger
    report = risk_assessment(db, clock[0])
    monkeypatch.setattr(settings, "API_KEY", "test-sensitive-credential")
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-session")
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        payload = {"stock_code":"sh.600000", "side":"buy", "quantity":100,
                   "risk_artifact_id":report["artifact_id"]}
        url = "/api/v1/agent-runs/paper-test/paper-orders"
        assert client.post(url, json=payload).status_code == 401
        response = client.post(url, json=payload, headers={"X-API-Key":"test-sensitive-credential"})
        assert response.status_code == 201
        assert response.json()["status"] == "pending_approval"
        event = db.query(PaperOrderEvent).one()
        assert event.detail_json["proposed_by"] == "api_key"
        assert "test-sensitive-credential" not in str(event.detail_json)
        assert db.query(PaperFill).count() == 0


def test_a_client_cannot_relax_server_caps_and_policy_changes_are_rechecked(ledger, monkeypatch):
    from app.domain.risk import PortfolioRiskRequest, RiskLimits
    from app.config import settings
    from app.services.paper_risk_assessment import assess_paper_risk

    db, clock = ledger
    permissive = RiskLimits(max_single_weight=1, max_gross_weight=1, minimum_cash_weight=0,
                            max_position_loss=1, max_portfolio_loss=1, max_participation=1)
    request = PortfolioRiskRequest(targets=[{"stock_code":"sh.600000", "target_weight":0.5,
                                             "stop_loss_pct":0.05,"reason":"explicit target"}], limits=permissive)
    report = assess_paper_risk(db, "paper-test", request, at=clock[0])
    assert report["proposal"]["rejected"]
    assert report["evidence"]["request"]["limits"]["max_single_weight"] == 0.15
    accepted = propose_verified(db, clock[0])
    monkeypatch.setattr(settings, "PAPER_RISK_LIMITS", RiskLimits(max_single_weight=0.005))
    with pytest.raises(ValueError, match="复核未通过"):
        service.decide_approval(db, accepted["approval_id"], "approved")
