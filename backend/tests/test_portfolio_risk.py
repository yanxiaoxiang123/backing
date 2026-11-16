from datetime import date, datetime, timedelta

import pytest

from app.domain.risk import PortfolioRiskRequest, RiskAccountEvidence, RiskMarketEvidence, RiskPositionEvidence
from app.services.portfolio_risk import evaluate_portfolio_risk

NOW = datetime(2026, 10, 30, 8)
CODE = "sh.600000"


def request(weight=0.1, stop=0.05, **limits):
    return PortfolioRiskRequest(targets=[{"stock_code": CODE, "target_weight": weight,
                                          "stop_loss_pct": stop, "reason": "用户明确的目标仓位"}], limits=limits)


def account(**changes):
    return RiskAccountEvidence(account_id="default", observed_at=NOW, cash=100000, **changes)


def quotes(**changes):
    row = dict(stock_code=CODE, session=date(2026, 10, 29), expected_session=date(2026, 10, 29),
               price=10, volume=1000000, suspended=False, locked=False, listed=True, raw=True,
               batch_ids=["verified-batch"])
    return {CODE: RiskMarketEvidence(**(row | changes))}


def evaluate(intent=None, balance=None, market=None):
    return evaluate_portfolio_risk(intent or request(), balance or account(), market or quotes(),
                                    run_id="risk-test", as_of=NOW)


def test_sizing_uses_account_cash_target_and_stop_budget_with_full_evidence():
    report = evaluate()
    assert not report["proposal"]["rejected"]
    order = report["orders"][0]
    assert order["side"] == "buy" and order["quantity"] == 1000
    assert report["equity"] == 100000
    assert report["projected_cash"] > 0
    assert len(report["evidence_sha256"]) == 64


def test_stop_budget_and_previous_session_liquidity_reduce_quantity():
    stop_limited = evaluate(request(stop=0.5))
    assert stop_limited["orders"][0]["quantity"] <= 200
    assert stop_limited["projected_stop_loss_pct"] <= 0.01
    liquidity_limited = evaluate(market=quotes(volume=2000))
    assert liquidity_limited["orders"][0]["quantity"] == 100


def test_concentration_sizing_accounts_for_fees_and_slippage():
    report = evaluate(request(weight=0.15))
    assert not report["proposal"]["rejected"]
    assert report["projected_weights"][CODE] <= 0.15
    assert report["orders"][0]["quantity"] == 1400


@pytest.mark.parametrize("changes", [{"suspended": True}, {"locked": True}, {"listed": False},
                                      {"raw": False}, {"session": date(2026, 10, 28)}])
def test_unverified_or_nontradable_security_never_yields_orders(changes):
    report = evaluate(market=quotes(**changes))
    assert report["proposal"]["rejected"]
    assert report["orders"] == []


def test_stale_snapshot_pending_orders_and_kill_switch_fail_closed():
    stale = account().model_copy(update={"observed_at": NOW - timedelta(minutes=6)})
    for balance in [stale, account(kill_switch=True), account(pending_codes=[CODE])]:
        report = evaluate(balance=balance)
        assert report["proposal"]["rejected"] and report["orders"] == []


def test_no_stop_assumption_cannot_be_replaced_with_an_invented_buy():
    assert evaluate(request(stop=None))["proposal"]["rejected"]
    assert evaluate(request(weight=0.5))["orders"] == []


def test_cash_reservations_are_not_reused_and_t_plus_one_cannot_sell_new_shares():
    report = evaluate(balance=account(reserved_cash=95000))
    assert report["proposal"]["rejected"] and report["orders"] == []
    balance = account(positions={CODE: RiskPositionEvidence(quantity=1000, available_to_sell=0)})
    report = evaluate(request(weight=0), balance)
    assert report["proposal"]["rejected"] and report["orders"] == []
    assert any(row["rule"].startswith("t_plus_one") and not row["passed"]
               for row in report["proposal"]["constraints"])


def test_missing_industry_is_explicit_when_sector_limit_is_enabled():
    report = evaluate(request(max_sector_weight=0.3))
    assert report["proposal"]["rejected"]
    verified = evaluate(request(max_sector_weight=0.3), market=quotes(sector="banking"))
    assert not verified["proposal"]["rejected"]


def test_duplicate_intent_or_nonfinite_evidence_is_rejected():
    target = request().targets[0]
    with pytest.raises(ValueError, match="exactly one target"):
        PortfolioRiskRequest(targets=[target, target])
    with pytest.raises(ValueError):
        quotes(price=float("nan"))


def test_pending_buy_exposure_is_included_before_an_additional_order_is_allowed():
    other = "sz.000001"
    intent = PortfolioRiskRequest(targets=[
        {"stock_code":CODE,"target_weight":0.1,"stop_loss_pct":0.05,"reason":"new target"},
        {"stock_code":other,"target_weight":0.7,"stop_loss_pct":0.005,"reason":"pending target"},
    ], limits={"max_single_weight":0.8,"max_gross_weight":0.75,"minimum_cash_weight":0.1})
    market = quotes()
    market[other] = quotes()[CODE].model_copy(update={"stock_code":other})
    balance = account(reserved_cash=70020, pending_codes=[other], pending_buys={other:7000})
    from app.domain.risk import RiskOrder

    report = evaluate_portfolio_risk(intent, balance, market, run_id="test", as_of=NOW,
                                      fixed_order=RiskOrder(stock_code=CODE,side="buy",quantity=1000,
                                                            reference_price=10,estimated_fees=5))
    assert report["proposal"]["rejected"]
    assert any(row["rule"] == "gross_exposure" and not row["passed"] for row in report["proposal"]["constraints"])
    assert report["evidence"]["fixed_order"]["quantity"] == 1000
