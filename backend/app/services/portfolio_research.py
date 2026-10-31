"""Raw-data loading, immutable snapshots and deterministic portfolio replay."""

import json
from uuid import uuid4

import pandas as pd
from sqlalchemy.orm import Session

from app.schemas.portfolio_research import PortfolioResearchRequest
from app.models.models import Stock
from app.models.portfolio_research import PortfolioExperiment
from app.services.backtest_simulation import ExecutionCosts
from app.services.corporate_actions import execution_actions
from app.services.market_data import digest, open_sessions, session_statuses
from app.services.market_data_sync import completed_end
from app.services.market_research_prices import load_research_bars
from app.services.portfolio_simulation import benchmark_comparison, simulate_portfolio

ENGINE_VERSION = "portfolio-next-open-v1"


def execute_snapshot(snapshot: dict) -> dict:
    if snapshot.get("engine_version") != ENGINE_VERSION:
        raise ValueError("Unsupported portfolio engine version")
    request = PortfolioResearchRequest.model_validate(snapshot["request"])
    frames = {}
    for code, item in snapshot["securities"].items():
        frame = pd.DataFrame(item["bars"])
        frame.attrs["suspended_sessions"] = item["suspended_sessions"]
        frames[code] = frame
    options = {"costs": ExecutionCosts(**snapshot["request"]["costs"]),
               "corporate_actions": {code: item["actions"] for code, item in snapshot["securities"].items()},
               "dividend_tax_rate": request.dividend_tax_rate}
    result = simulate_portfolio(
        {code: frames[code] for code in request.weights}, snapshot["session_dates"],
        request.weights, request.initial_capital, rebalance=request.rebalance, **options)
    if request.benchmark:
        benchmark = simulate_portfolio(
            {request.benchmark: frames[request.benchmark]}, snapshot["session_dates"],
            {request.benchmark: 1.0}, request.initial_capital, rebalance="none", **options)
        result["benchmark"] = {"stock_code": request.benchmark,
                               "portfolio_values": benchmark["portfolio_values"], "metrics": benchmark["metrics"]}
        result["comparison"] = benchmark_comparison(result, benchmark)
    result["engine_version"] = ENGINE_VERSION
    result["limitations"] = snapshot["limitations"]
    return result


def build_snapshot(db: Session, request: PortfolioResearchRequest) -> dict:
    if request.end_date > completed_end():
        raise ValueError("Portfolio research requires completed market sessions")
    codes = sorted(set(request.weights) | ({request.benchmark} if request.benchmark else set()))
    securities = {}
    sessions = None
    limitations = {"explicit_user_universe_not_point_in_time_selection", "retrospective_observations",
                   "costs_are_constant_research_assumptions", "locked_bars_blocked_conservatively",
                   "prior_close_quantities_unadjusted_on_ex_date", "unfilled_residuals_expire_next_session",
                   "buy_allocation_prorated_then_rounded_down_to_lots"}
    for code in codes:
        stock = db.query(Stock).filter_by(code=code).first()
        if stock is None:
            raise ValueError(f"Security not found: {code}")
        if stock.list_date and stock.list_date > request.start_date:
            raise ValueError(f"{code} was not listed at portfolio start; shorten the requested period")
        frame = load_research_bars(db, code, request.start_date, request.end_date, source="raw")
        calendar = [day.isoformat() for day in open_sessions(
            db, code.split(".")[0], request.start_date, request.end_date)]
        if len(calendar) < 2:
            raise ValueError("Portfolio research requires at least two verified trading sessions")
        if sessions is not None and sessions != calendar:
            raise ValueError("Portfolio securities must share the same verified exchange sessions")
        sessions = calendar
        actions, action_provenance = [], {}
        if request.corporate_action_mode == "verified":
            actions, action_provenance = execution_actions(db, code, request.start_date, request.end_date)
            limitations.update(action_provenance["limitations"])
        else:
            limitations.add("corporate_actions_not_applied")
        suspended = [day.isoformat() for day, value in session_statuses(
            db, code, request.start_date, request.end_date).items() if value]
        # Status evidence must override a conflicting price row for execution.
        if not frame.empty:
            frame["suspended"] = [bool(row.get("suspended", False)) or str(row["date"]) in suspended
                                  for row in frame.to_dict(orient="records")]
        securities[code] = {
            "bars": json.loads(frame.to_json(orient="records", date_format="iso", double_precision=15)),
            "suspended_sessions": sorted(suspended), "actions": actions,
            "price_provenance": frame.attrs.get("provenance", {}), "action_provenance": action_provenance,
        }
    return {"engine_version": ENGINE_VERSION, "request": request.model_dump(mode="json"),
            "session_dates": sessions, "securities": securities,
            "rebalance_timing": "first_completed_session_of_period_then_next_open",
            "sizing_timing": "previous_completed_close", "fill_timing": "next_session_open",
            "sell_before_buy": True, "annualization_sessions": 252,
            "benchmark_method": "same_capital_costs_actions_next_open_buy_and_hold",
            "limitations": sorted(limitations)}


def create_experiment(db: Session, request: PortfolioResearchRequest, owner: str) -> PortfolioExperiment:
    snapshot = build_snapshot(db, request)
    result = execute_snapshot(snapshot)
    experiment = PortfolioExperiment(
        experiment_id=uuid4().hex, owner=owner, name=request.name, engine_version=ENGINE_VERSION,
        snapshot_sha256=digest(snapshot), result_sha256=digest(result), snapshot=snapshot, result=result)
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def replay_experiment(experiment: PortfolioExperiment) -> dict:
    if digest(experiment.snapshot) != experiment.snapshot_sha256:
        raise ValueError("Portfolio input snapshot checksum mismatch")
    if digest(experiment.result) != experiment.result_sha256:
        raise ValueError("Saved portfolio result checksum mismatch")
    result = execute_snapshot(experiment.snapshot)
    return {"experiment_id": experiment.experiment_id,
            "reproduced": digest(result) == experiment.result_sha256,
            "snapshot_sha256": experiment.snapshot_sha256, "result": result}
