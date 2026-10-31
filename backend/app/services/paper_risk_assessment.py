"""Collect paper-ledger and versioned-market facts, then persist a reviewable assessment."""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.agent_runtime.artifacts import emit_artifact, filename_of, read_artifact
from app.agent_runtime.stores import create_stores
from app.domain.risk import PortfolioRiskRequest, RiskAccountEvidence, RiskMarketEvidence, RiskPositionEvidence, RiskOrder
from app.models.agent_runtime import AgentRun, ArtifactRecord
from app.models.market_data import SecurityObservation
from app.models.paper_trading import PaperAccount, PaperFill, PaperOrder, PaperPosition
from app.services.backtest_simulation import ExecutionCosts
from app.services.market_data import digest, load_bars, naive_utc, open_sessions, session_statuses
from app.services.market_data_sync import completed_end
from app.services.portfolio_risk import evaluate_portfolio_risk
from app.config import settings


def _account_revision(db: Session) -> str:
    # Column queries bypass the ORM identity map. Include the append-only fill
    # cursor so an intervening trade followed by a reversing trade is visible.
    return digest({
        "accounts": [tuple(row) for row in db.execute(select(PaperAccount.account_id, PaperAccount.cash)
                                                      .order_by(PaperAccount.id))],
        "positions": [tuple(row) for row in db.execute(select(PaperPosition.stock_code, PaperPosition.quantity,
                                                             PaperPosition.avg_cost).order_by(PaperPosition.id))],
        "orders": [tuple(row) for row in db.execute(select(PaperOrder.order_id, PaperOrder.status,
                                                          PaperOrder.quantity, PaperOrder.limit_price)
                                                   .where(PaperOrder.status.in_(["pending_approval", "approved"]))
                                                   .order_by(PaperOrder.id))],
        "fill_cursor": db.execute(select(func.max(PaperFill.id))).scalar(),
    })


def save_risk_request(db: Session, run_id: str, request: PortfolioRiskRequest) -> dict:
    if db.query(AgentRun.id).filter_by(run_id=run_id).first() is None:
        raise ValueError("Risk assessment run not found")
    payload = request.model_dump(mode="json")
    artifact = emit_artifact(create_stores(db), run_id, "portfolio_risk_request",
                             f"risk-request-{digest(payload)}.json", payload)
    if artifact is None:
        raise ValueError("Unable to persist risk intent")
    return artifact


def assess_paper_risk(db: Session, run_id: str, request: PortfolioRiskRequest, *,
                      as_of: datetime | None = None, at: datetime | None = None,
                      exclude_order_id: str | None = None, persist: bool = True,
                      trade_date: date | None = None, exact_order: dict | None = None) -> dict:
    now = at or datetime.now(timezone.utc)
    requested_point = naive_utc(as_of or now)
    if not 0 <= (naive_utc(now) - requested_point).total_seconds() <= 300:
        raise ValueError("Current paper account cannot support a historical/future risk assessment")
    point = naive_utc(now)
    submitted_request = request.model_dump(mode="json")
    policy = settings.PAPER_RISK_LIMITS
    request = request.model_copy(update={"limits": request.limits.bounded_by(policy)}, deep=True)
    revision = _account_revision(db)
    account = db.query(PaperAccount).populate_existing().filter_by(account_id="default").one_or_none()
    if account is None:
        raise ValueError("Paper account not initialized; no executable account evidence")
    holdings = db.query(PaperPosition).populate_existing().filter(PaperPosition.quantity > 0).all()
    pending_query = db.query(PaperOrder).populate_existing().filter(PaperOrder.status.in_(["pending_approval", "approved"]))
    if exclude_order_id:
        pending_query = pending_query.filter(PaperOrder.order_id != exclude_order_id)
    pending = pending_query.all()
    # The legacy paper ledger is single-account; do not pretend these positions
    # are segregated if a second account has been inserted by another client.
    if db.query(PaperAccount.id).count() != 1:
        raise ValueError("Existing paper ledger cannot yet prove multi-account ownership")
    required = {position.stock_code for position in holdings} | {target.stock_code for target in request.targets}
    required |= {order.stock_code for order in pending}
    end = trade_date - timedelta(days=1) if trade_date else completed_end(point.replace(tzinfo=timezone.utc))
    execution_context = {}
    if trade_date:
        if trade_date > point.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).date():
            raise ValueError("Cannot assess an unobserved future opening")
        if db.query(PaperFill.id).filter(PaperFill.trade_date > trade_date.isoformat()).first():
            raise ValueError("Paper ledger contains fills after the requested execution session")
    market = {}
    for code in sorted(required):
        sessions = open_sessions(db, code.split(".")[0], end - timedelta(days=30), end)
        if not sessions:
            raise ValueError(f"No verified completed trading session for {code}")
        expected = sessions[-1]
        frame, provenance = load_bars(db, code, expected - timedelta(days=45), expected, observed_before=point)
        if frame.empty:
            raise ValueError(f"No raw valuation evidence for {code}")
        last = frame.iloc[-1]
        security = db.query(SecurityObservation).filter(
            SecurityObservation.stock_code == code, SecurityObservation.observed_at <= point,
            SecurityObservation.effective_date <= point.date(),
        ).order_by(SecurityObservation.observed_at.desc(), SecurityObservation.id.desc()).first()
        if security is None:
            raise ValueError(f"No observed security-status evidence for {code}")
        listed = (security.status == "listed" and (security.listed_on is None or security.listed_on <= expected)
                  and (security.delisted_on is None or security.delisted_on > expected))
        statuses = session_statuses(db, code, expected, expected, observed_before=point)
        price, suspended, locked = last["close"], statuses.get(expected, bool(last["suspended"])), last["high"] == last["low"]
        if trade_date:
            opening, opening_provenance = load_bars(db, code, trade_date, trade_date, observed_before=point)
            target_status = session_statuses(db, code, trade_date, trade_date, observed_before=point)
            if opening.empty:
                if not target_status.get(trade_date, False):
                    raise ValueError(f"Missing opening valuation evidence for {code} {trade_date}")
                suspended, locked = True, True
                execution_context[code] = {"valuation": "last_close_suspended", "trade_date": str(trade_date)}
            else:
                current = opening.iloc[0]
                price = current["open"]
                suspended = target_status.get(trade_date, bool(current["suspended"]))
                locked = current["high"] == current["low"]
                execution_context[code] = {"valuation": "session_open", "trade_date": str(trade_date),
                                            "batch_ids": opening_provenance["batch_ids"]}
        market[code] = RiskMarketEvidence(stock_code=code, session=last["date"], expected_session=expected,
                                          price=price, volume=last["volume"], raw=True,
                                          suspended=suspended, locked=locked, listed=listed,
                                          batch_ids=provenance["batch_ids"])
    local_day = (trade_date or point.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).date()).isoformat()
    bought = {}
    fills = db.query(PaperFill, PaperOrder).join(PaperOrder, PaperFill.order_id == PaperOrder.order_id).filter(
        PaperFill.trade_date == local_day, PaperOrder.side == "buy").all()
    for fill, order in fills:
        bought[order.stock_code] = bought.get(order.stock_code, 0) + fill.quantity
    sell_reservations = {}
    reserved_cash = 0.0
    pending_buys = {}
    costs = ExecutionCosts()
    for order in pending:
        if order.side == "buy":
            reference = order.limit_price or market[order.stock_code].price * (1 + costs.slippage_rate)
            amount = reference * order.quantity
            reserved_cash += amount + costs.fees("buy", amount)
            pending_buys[order.stock_code] = pending_buys.get(order.stock_code, 0) + order.quantity
        else:
            sell_reservations[order.stock_code] = sell_reservations.get(order.stock_code, 0) + order.quantity
    positions = {row.stock_code: RiskPositionEvidence(quantity=row.quantity,
                 available_to_sell=max(0, row.quantity - bought.get(row.stock_code, 0)
                                       - sell_reservations.get(row.stock_code, 0))) for row in holdings}
    evidence = RiskAccountEvidence(account_id=account.account_id, observed_at=point, cash=account.cash,
                                    positions=positions, reserved_cash=reserved_cash,
                                    pending_codes=sorted({order.stock_code for order in pending}),
                                    pending_buys=pending_buys,
                                    source_ids=[f"paper_account:{account.id}",
                                                *[f"paper_position:{row.id}" for row in holdings],
                                                *[f"paper_order:{row.order_id}" for row in pending],
                                                *[f"paper_fill:{fill.id}" for fill, _ in fills]])
    if _account_revision(db) != revision:
        raise ValueError("Paper ledger changed while collecting risk evidence; retry assessment")
    fixed = None
    if exact_order is not None:
        code, side, quantity = exact_order["stock_code"], exact_order["side"], exact_order["quantity"]
        if code not in market:
            raise ValueError("Order has no verified market evidence")
        reference = exact_order.get("reference_price")
        if reference is None:
            reference = market[code].price * (1 + costs.slippage_rate if side == "buy" else 1 - costs.slippage_rate)
            limit = exact_order.get("limit_price")
            if limit is not None:
                reference = max(reference, limit) if side == "buy" else min(reference, limit)
        reference = round(reference, 4)
        fixed = RiskOrder(stock_code=code, side=side, quantity=quantity, reference_price=reference,
                          estimated_fees=costs.fees(side, reference * quantity))
    report = evaluate_portfolio_risk(request, evidence, market, run_id=run_id, as_of=point, costs=costs,
                                     fixed_order=fixed)
    report["evidence"]["account_revision"] = revision
    report["evidence"]["submitted_request"] = submitted_request
    report["evidence"]["server_policy"] = policy.model_dump(mode="json")
    if trade_date:
        report["evidence"]["execution_context"] = execution_context
    report["evidence_sha256"] = digest(report["evidence"])
    report.update(research_as_of=requested_point.isoformat(), account_revision=revision)
    if not persist:
        return report
    artifact = emit_artifact(create_stores(db), run_id, "portfolio_risk_assessment",
                             f"risk-{report['evidence_sha256']}.json", report)
    if artifact is None:
        raise ValueError("Unable to persist risk evidence")
    return {**report, "artifact_id": artifact["id"]}


def assess_saved_risk_request(db: Session, run_id: str, *, as_of: datetime | None = None) -> dict | None:
    row = db.query(ArtifactRecord).filter_by(run_id=run_id, artifact_type="portfolio_risk_request").order_by(
        ArtifactRecord.id.desc()).first()
    if row is None:
        return None
    content = read_artifact(run_id, filename_of(row.uri))
    if content is None or hashlib.sha256(content.encode()).hexdigest() != row.checksum:
        raise ValueError("Risk intent artifact is missing or has a checksum mismatch")
    return assess_paper_risk(db, run_id, PortfolioRiskRequest.model_validate(json.loads(content)), as_of=as_of)
