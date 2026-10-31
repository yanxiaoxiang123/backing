"""Portfolio accounting, timing, governance, ownership and independent replay."""

from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.api.portfolio_research import router
from app.auth import get_authenticated_actor
from app.config import Base, get_db
from app.schemas.portfolio_research import PortfolioResearchRequest
from app.error_handlers import register_error_handlers
from app.models.models import Stock
from app.models.portfolio_research import PortfolioExperiment
from app.services.backtest_simulation import ExecutionCosts
from app.services.corporate_actions import store_metadata_batch
from app.services.market_data import store_bars, store_calendar, store_session_statuses
from app.services.portfolio_research import create_experiment, replay_experiment
from app.services.portfolio_simulation import simulate_portfolio

ZERO_COSTS = ExecutionCosts(commission_rate=0, minimum_commission=0, sell_tax_rate=0,
                            transfer_rate=0, slippage_rate=0, max_participation=1)
START = date(2024, 1, 2)


def frame(prices, volumes=None):
    return pd.DataFrame([
        {"date": START + timedelta(days=index), "open": price, "high": price + 1,
         "low": price - 1, "close": price, "volume": (volumes or [100000] * len(prices))[index]}
        for index, price in enumerate(prices)])


def run(frames=None, weights=None, costs=ZERO_COSTS, **kwargs):
    frames = frames or {"sh.600000": frame([10, 10, 10]), "sz.000001": frame([10, 10, 10])}
    weights = weights or {code: 1 / len(frames) for code in frames}
    return simulate_portfolio(frames, [(START + timedelta(days=i)).isoformat() for i in range(3)],
                              weights, 100000, costs=costs, **kwargs)


def test_shared_cash_has_one_capital_pool_and_executes_next_open():
    result = run(rebalance="none")
    assert len(result["trades"]) == 2
    assert sum(t["amount"] for t in result["trades"]) == 100000
    assert {t["date"] for t in result["trades"]} == {"2024-01-03"}
    assert result["portfolio_values"][0]["cash"] == 100000
    assert result["final_capital"] == 100000


def test_open_gap_prorates_buys_instead_of_giving_first_symbol_all_cash():
    result = run({"sh.600000": frame([10, 20, 20]), "sz.000001": frame([10, 20, 20])}, rebalance="none")
    assert [t["quantity"] for t in result["trades"]] == [2500, 2500]
    assert all(point["cash"] >= 0 for point in result["portfolio_values"])
    assert {row["reason"] for row in result["unfilled_orders"]} == {"shared_cash"}


def test_future_close_and_volume_do_not_change_open_sizing_or_prior_equity():
    frames = {"sh.600000": frame([10, 10, 10]), "sz.000001": frame([10, 10, 10])}
    original = run(frames, rebalance="none")
    frames["sh.600000"].loc[1, ["high", "close", "volume"]] = [100, 99, 1e8]
    changed = run(frames, rebalance="none")
    assert original["trades"] == changed["trades"]
    assert original["portfolio_values"][0] == changed["portfolio_values"][0]


def test_capacity_uses_previous_completed_volume_and_residual_expires():
    result = run({"sh.600000": frame([10, 10, 10], [200, 1e8, 1e8])}, rebalance="none")
    assert len(result["trades"]) == 1 and result["trades"][0]["quantity"] == 200
    assert result["unfilled_orders"][0]["quantity"] == 9800


def test_daily_rebalance_sells_before_buys_and_never_borrows():
    result = run({"sh.600000": frame([10, 10, 20]), "sz.000001": frame([10, 20, 20])}, rebalance="daily")
    day_three = [row for row in result["trades"] if row["date"] == "2024-01-04"]
    assert [row["action"] for row in day_three] == ["sell", "buy"]
    assert all(point["cash"] >= 0 for point in result["portfolio_values"])
    assert all(row["date"] > START.isoformat() for row in result["trades"])


def test_partial_target_weights_keep_unallocated_capital_in_cash_and_charge_costs():
    result = run(weights={"sh.600000": 0.25, "sz.000001": 0.25}, costs=ExecutionCosts(), rebalance="none")
    assert result["final_capital"] < 100000
    assert result["portfolio_values"][-1]["cash"] > 49000
    assert result["metrics"]["total_fees"] > 0
    assert result["metrics"]["slippage_cost"] > 0


def test_missing_bar_requires_explicit_suspension_and_does_not_delay_order():
    f = frame([10, 10, 10]).drop(index=1)
    with pytest.raises(ValueError, match="Missing unverified"):
        run({"sh.600000": f})
    f.attrs["suspended_sessions"] = ["2024-01-03"]
    result = run({"sh.600000": f}, rebalance="none")
    assert result["trades"] == []
    assert len(result["portfolio_values"]) == 3
    assert result["unfilled_orders"][0]["reason"] == "non_executable_session"


def test_corporate_action_receivables_and_bonus_shares_are_in_portfolio_equity():
    f = frame([10, 10, 4.5])
    action = {"action_id": "distribution", "record_date": "2024-01-03", "ex_date": "2024-01-04",
              "cash_per_share": 1, "bonus_ratio": 1, "cash_date": "2024-01-05", "stock_date": "2024-01-05"}
    result = run({"sh.600000": f}, rebalance="none", corporate_actions={"sh.600000": [action]})
    final = result["portfolio_values"][-1]
    assert final["receivable"] == 10000
    assert final["positions"]["sh.600000"]["pending_shares"] == 10000
    assert final["cash"] == 0 and final["total_value"] == 100000


@pytest.mark.parametrize("weights", [
    {"sh.600000": 0.8, "sz.000001": 0.8}, {"sh.600000": -0.1},
    {"sh.600000": float("nan")}, {"600000": 1}, {"sh.600000": 0},
])
def test_invalid_weight_requests_fail(weights):
    with pytest.raises(ValueError):
        PortfolioResearchRequest(weights=weights, start_date=START, end_date=START)


def test_weekly_and_monthly_targets_are_sized_after_first_session_of_period():
    sessions = ["2024-01-31", "2024-02-01", "2024-02-02", "2024-02-05", "2024-02-06"]
    f = frame([10, 20, 20, 10, 10])
    f["date"] = sessions
    monthly = simulate_portfolio({"sh.600000": f}, sessions, {"sh.600000": 0.5}, 100000,
                                  costs=ZERO_COSTS, rebalance="monthly")
    weekly = simulate_portfolio({"sh.600000": f}, sessions, {"sh.600000": 0.5}, 100000,
                                 costs=ZERO_COSTS, rebalance="weekly")
    assert {row["date"] for row in monthly["trades"]} == {"2024-02-01", "2024-02-02"}
    assert {row["date"] for row in weekly["trades"]} == {"2024-02-01", "2024-02-06"}


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for exchange in ("sh", "sz"):
        store_calendar(session, exchange, [{"date": START + timedelta(days=i), "is_open": True} for i in range(3)], provider="fixture")
    for code in ("sh.600000", "sz.000001"):
        session.add(Stock(code=code, market=code[:2], name=code, list_date=date(2000, 1, 1)))
        session.flush()
        store_bars(session, code, frame([10, 10, 10]).to_dict(orient="records"), provider="fixture")
        for kind in ("dividend", "adjustment_factor"):
            store_metadata_batch(session, code, kind, [], start=START, end=START + timedelta(days=2), provider="fixture")
    session.commit()
    yield session
    session.close()
    engine.dispose()


def request(**kwargs):
    return PortfolioResearchRequest(weights={"sh.600000": 0.5, "sz.000001": 0.5}, start_date=START,
                                     end_date=START + timedelta(days=2), benchmark="sh.600000", **kwargs)


def test_replay_is_independent_of_live_prices_and_detects_snapshot_and_result_corruption(db):
    experiment = create_experiment(db, request(), "alice")
    from app.models.market_data import MarketDailyBar

    db.query(MarketDailyBar).delete()
    db.commit()
    replay = replay_experiment(experiment)
    assert replay["reproduced"] is True
    assert replay["result"]["benchmark"]["metrics"]["total_trades"] == 1
    assert "comparison" in replay["result"]
    experiment.snapshot = experiment.snapshot | {"fill_timing": "same_close"}
    with pytest.raises(ValueError, match="snapshot checksum"):
        replay_experiment(experiment)
    db.rollback()
    experiment.result = experiment.result | {"final_capital": 1}
    with pytest.raises(ValueError, match="result checksum"):
        replay_experiment(experiment)


def test_verified_metadata_coverage_is_required_before_saving_any_experiment(db):
    from app.models.market_data import MarketMetadataBatch

    db.query(MarketMetadataBatch).delete()
    db.commit()
    with pytest.raises(ValueError, match="coverage missing"):
        create_experiment(db, request(), "alice")
    assert db.query(PortfolioExperiment).count() == 0
    explicit = create_experiment(db, request(corporate_action_mode="price_only"), "alice")
    assert "corporate_actions_not_applied" in explicit.result["limitations"]


def test_explicit_suspension_status_overrides_existing_bar(db):
    store_session_statuses(db, [{"date": START + timedelta(days=1), "stock_code": "sh.600000", "suspended": True}], provider="fixture")
    db.commit()
    item = create_experiment(db, request(rebalance="none"), "alice")
    assert not any(row["stock_code"] == "sh.600000" for row in item.result["trades"])


def test_portfolio_api_persists_lists_exports_replays_and_scopes_ownership(db):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-session")
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_authenticated_actor] = lambda: "alice"
    with TestClient(app) as client:
        created = client.post("/api/v1/portfolio-research", json=request().model_dump(mode="json"))
        assert created.status_code == 200, created.text
        item = created.json()
        path = "/api/v1/portfolio-research/" + item["experiment_id"]
        assert client.get("/api/v1/portfolio-research").json()["total"] == 1
        assert client.get(path).json()["result"] == item["result"]
        assert client.post(path + "/replay").json()["reproduced"] is True
        exported = client.get(path + "/export")
        assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
        assert exported.json()["snapshot"]["engine_version"] == "portfolio-next-open-v1"
        app.dependency_overrides[get_authenticated_actor] = lambda: "bob"
        assert client.get("/api/v1/portfolio-research").json()["total"] == 0
        for suffix in ("", "/export"):
            assert client.get(path + suffix).status_code == 404
        assert client.post(path + "/replay").status_code == 404
        app.dependency_overrides.pop(get_authenticated_actor)
        assert client.get("/api/v1/portfolio-research").status_code == 401


def test_api_rejects_invalid_requests_and_unknown_or_uncovered_securities(db):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_authenticated_actor] = lambda: "alice"
    with TestClient(app) as client:
        payload = request().model_dump(mode="json")
        assert client.post("/api/v1/portfolio-research", json=payload | {"weights": {"sh.600000": 2}}).status_code == 422
        invalid = client.post("/api/v1/portfolio-research", content='{"weights":{"sh.600000":NaN},"start_date":"2024-01-02","end_date":"2024-01-04"}', headers={"Content-Type": "application/json"})
        assert invalid.status_code == 422
        assert set(invalid.json()["error"]["detail"][0]) == {"type", "loc", "msg"}
        missing = client.post("/api/v1/portfolio-research", json=payload | {"weights": {"sh.600001": 1}})
        assert missing.status_code == 400
        assert db.query(PortfolioExperiment).count() == 0
