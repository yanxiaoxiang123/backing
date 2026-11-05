"""Explicit provider/clock fixtures for paper-ledger integration tests."""

from datetime import datetime, time, timedelta, timezone

from app.domain.risk import PortfolioRiskRequest
from app.models.models import Stock
from app.models.paper_trading import PaperAccount
from app.services.market_data import store_bars, store_calendar, store_security
from app.services.paper_risk_assessment import assess_paper_risk
from app.tools.execution import ProposeOrderParams, _propose_order
from app.tools.base import ToolContext


def seed_paper_evidence(db, now, code="sh.600000"):
    start, end = now.date() - timedelta(days=40), now.date() + timedelta(days=10)
    if not db.query(Stock).filter_by(code=code).first():
        db.add(Stock(code=code, name="fixture", market=code.split(".")[0]))
    if not db.query(PaperAccount).first():
        db.add(PaperAccount(account_id="default", cash=100000, initial_cash=100000))
    calendar = [{"date": start + timedelta(days=i), "is_open": (start + timedelta(days=i)).weekday() < 5}
                for i in range((end - start).days + 1)]
    store_calendar(db, code.split(".")[0], calendar, provider="explicit-weekday-fixture")
    store_security(db, {"stock_code": code, "name": "fixture", "status": "listed",
                        "listed_on": "2020-01-01", "effective_date": start},
                   provider="fixture", observed_at=datetime.combine(start, time.min))
    for session in calendar:
        if session["is_open"]:
            store_bars(db, code, [{"date": session["date"], "open": 10, "high": 11,
                                   "low": 9, "close": 10, "volume": 1000000,
                                   "is_st": False, "suspended": False}], provider="fixture",
                       observed_at=datetime.combine(session["date"], time(7, 30), timezone.utc))
    db.commit()


def risk_assessment(db, now, run_id="paper-test", code="sh.600000", weight=0.1):
    request = PortfolioRiskRequest(targets=[{"stock_code": code, "target_weight": weight,
                                            "stop_loss_pct": 0.05, "reason": "Explicit test intent"}])
    return assess_paper_risk(db, run_id, request, at=now)


def propose_verified(db, now, *, run_id="paper-test", code="sh.600000", side="buy", quantity=100, limit_price=None):
    report = risk_assessment(db, now, run_id, code, weight=0 if side == "sell" else 0.1)
    assert not report["proposal"]["rejected"], report["proposal"]["rejection_reasons"]
    return _propose_order(ProposeOrderParams(stock_code=code, side=side, quantity=quantity,
                                             limit_price=limit_price, risk_artifact_id=report["artifact_id"]),
                           ToolContext(db=db, run_id=run_id, granted_permissions={"read", "approval"}))
