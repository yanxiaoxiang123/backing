"""Paper lifecycle with verified intent, calendars and dated raw observations."""

from datetime import date, datetime, timezone
from threading import Barrier, Thread

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent_runtime.paper import service
from app.agent_runtime.paper.replay import replay_account
from app.config import Base
from app.models.agent_runtime import AgentRun, ApprovalRecord
from app.models.market_data import MarketDailyBar, TradingSession
from app.models.paper_trading import PaperAccount, PaperOrder, PaperFill, PaperCashEvent, PaperPosition
from app.services.market_data import store_bars, store_session_statuses
from paper_evidence import seed_paper_evidence, propose_verified
from test_paper_order_risk import ledger as ledger_fixture

ledger = ledger_fixture


def approved(db, clock, **kwargs):
    order = propose_verified(db, clock[0], **kwargs)
    service.decide_approval(db, order["approval_id"], "approved")
    return order


def advance(clock):
    clock[0] = datetime(2026, 11, 2, 8, tzinfo=timezone.utc)


def test_approval_sets_verified_next_session_expiry_and_rejects_double_decision(ledger):
    db, clock = ledger
    proposed = approved(db, clock)
    row = db.get(ApprovalRecord, proposed["approval_id"])
    assert row.expires_at and 0 < row.target_position_pct < 1
    assert db.query(PaperOrder).one().target_trade_date == "2026-11-02"
    with pytest.raises(ValueError, match="不可再决策"):
        service.decide_approval(db, row.id, "rejected")


def test_rejection_and_pending_orders_never_fill(ledger):
    db, clock = ledger
    proposed = propose_verified(db, clock[0])
    assert service.run_matching_cycle(db)["processed"] == 0
    service.decide_approval(db, proposed["approval_id"], "rejected")
    assert db.query(PaperOrder).one().status == "rejected"
    assert service.run_matching_cycle(db)["filled"] == 0


@pytest.mark.parametrize("decision,expected", [("invalid", "非法决策"), ("approved", "审批不存在")])
def test_invalid_decisions_are_rejected(ledger, decision, expected):
    db, _ = ledger
    with pytest.raises(ValueError, match=expected):
        service.decide_approval(db, 999, decision)


def test_calendar_not_future_price_arrival_determines_window(ledger):
    db, clock = ledger
    db.query(MarketDailyBar).filter(MarketDailyBar.date >= date(2026, 11, 2)).delete()
    db.commit()
    approved(db, clock)
    assert db.query(PaperOrder).one().target_trade_date == "2026-11-02"
    advance(clock)
    assert service.run_matching_cycle(db)["noop"] == 1
    clock[0] = datetime(2026, 11, 3, 8, tzinfo=timezone.utc)
    assert service.run_matching_cycle(db)["expired"] == 1


def test_unknown_future_calendar_blocks_approval_without_consuming_it(ledger):
    db, clock = ledger
    proposed = propose_verified(db, clock[0])
    db.query(TradingSession).filter(TradingSession.date == date(2026, 11, 2)).delete()
    db.commit()
    with pytest.raises(ValueError, match="日历"):
        service.decide_approval(db, proposed["approval_id"], "approved")
    assert db.get(ApprovalRecord, proposed["approval_id"]).status == "pending"


def test_full_daily_bar_cannot_be_used_before_session_has_completed(ledger):
    db, clock = ledger
    approved(db, clock)
    clock[0] = datetime(2026, 11, 2, 3, tzinfo=timezone.utc)
    assert service.run_matching_cycle(db)["noop"] == 1
    assert db.query(PaperFill).count() == 0


def test_known_suspension_and_limit_price_expire_without_filling(ledger):
    db, clock = ledger
    approved(db, clock, limit_price=1)
    advance(clock)
    assert service.run_matching_cycle(db)["expired"] == 1
    assert db.query(PaperFill).count() == 0
    # A fresh Friday proposal can be examined separately on the same fixture.
    clock[0] = datetime(2026, 10, 30, 8, tzinfo=timezone.utc)
    approved(db, clock)
    advance(clock)
    store_session_statuses(db, [{"stock_code": "sh.600000", "date": "2026-11-02", "suspended": True}],
                           provider="fixture", observed_at=clock[0])
    db.commit()
    assert service.run_matching_cycle(db)["expired"] == 1
    assert db.query(PaperFill).count() == 0


def test_locked_bar_cannot_fill_and_uses_historical_status(ledger):
    db, clock = ledger
    approved(db, clock)
    advance(clock)
    store_bars(db, "sh.600000", [{"date": "2026-11-02", "open": 11, "high": 11, "low": 11,
                                  "close": 11, "volume": 1000000, "is_st": False}],
               provider="revised", observed_at=clock[0])
    db.commit()
    assert service.run_matching_cycle(db)["expired"] == 1


def test_cash_changes_after_approval_are_rechecked(ledger):
    db, clock = ledger
    approved(db, clock)
    db.query(PaperAccount).one().cash = 10
    db.commit()
    advance(clock)
    assert service.run_matching_cycle(db)["expired"] == 1
    assert db.query(PaperFill).count() == 0


def test_yesterdays_volume_caps_execution_even_when_today_volume_is_huge(ledger):
    db, clock = ledger
    approved(db, clock)
    advance(clock)
    store_bars(db, "sh.600000", [{"date": "2026-10-30", "open": 10, "high": 11, "low": 9,
                                  "close": 10, "volume": 1000, "is_st": False}],
               provider="revised", observed_at=clock[0])
    db.commit()
    assert service.run_matching_cycle(db)["expired"] == 1


def test_sell_uses_only_available_old_shares_and_removes_a_liquidated_position(ledger):
    db, clock = ledger
    db.add(PaperPosition(stock_code="sh.600000", quantity=100, avg_cost=10))
    db.commit()
    approved(db, clock, side="sell")
    advance(clock)
    assert service.run_matching_cycle(db)["filled"] == 1
    assert db.query(PaperPosition).count() == 0


def test_t_plus_one_is_rechecked_at_fill(ledger):
    db, clock = ledger
    db.add(PaperPosition(stock_code="sh.600000", quantity=100, avg_cost=10))
    db.commit()
    approved(db, clock, side="sell")
    advance(clock)
    # A prior liquidation/replacement has left the same projection quantity,
    # now entirely backed by a same-day acquisition.
    db.add(PaperOrder(order_id="replacement", run_id="paper-test", stock_code="sh.600000",
                      side="buy", quantity=100, status="filled"))
    db.flush()
    db.add(PaperFill(order_id="replacement", fill_seq=1, trade_date="2026-11-02", price=10, quantity=100))
    db.commit()
    assert service.run_matching_cycle(db)["expired"] == 1
    assert db.query(PaperPosition).one().quantity == 100


def test_filled_events_replay_to_the_same_account_and_repeated_cycles_are_idempotent(ledger):
    db, clock = ledger
    approved(db, clock)
    advance(clock)
    assert service.run_matching_cycle(db)["filled"] == 1
    assert service.run_matching_cycle(db)["processed"] == 0
    fills = [{"stock_code": order.stock_code, "side": order.side, "price": fill.price, "quantity": fill.quantity}
             for fill, order in db.query(PaperFill, PaperOrder).join(PaperOrder, PaperFill.order_id == PaperOrder.order_id)]
    cash = [{"event_type": row.event_type, "amount": row.amount} for row in db.query(PaperCashEvent)]
    replay = replay_account(initial_cash=100000, cash_events=cash, fills=fills)
    state = service.account_state(db)
    assert state["cash"] == pytest.approx(replay["cash"], abs=0.0001)
    assert state["positions"] == [{"stock_code": code, **position} for code, position in replay["positions"].items()]


def test_concurrent_file_database_cycles_do_not_double_fill(ledger, tmp_path):
    _, clock = ledger
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(AgentRun(run_id="paper-test", objective="concurrency"))
        seed_paper_evidence(db, clock[0])
        approved(db, clock)
    advance(clock)
    barrier, errors = Barrier(2), []

    def run():
        try:
            with Session(engine) as db:
                barrier.wait(timeout=5)
                service.run_matching_cycle(db)
        except Exception as exc:
            errors.append(exc)

    workers = [Thread(target=run) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=15)
    assert not errors
    assert not any(worker.is_alive() for worker in workers)
    with Session(engine) as db:
        assert db.query(PaperFill).count() == 1
    engine.dispose()


def test_risk_rechecks_do_not_commit_an_earlier_fill_if_the_cycle_fails(ledger, monkeypatch):
    db, clock = ledger
    approved(db, clock)
    seed_paper_evidence(db, clock[0], code="sh.600001")
    db.add(PaperOrder(order_id="legacy-second", run_id="paper-test", stock_code="sh.600001",
                      side="sell", quantity=100, status="approved"))
    db.commit()
    advance(clock)
    original = service._match_one
    outcomes = []

    def fail_second(db, account, order):
        if outcomes:
            raise RuntimeError("injected failure after first fill")
        result = original(db, account, order)
        outcomes.append(result)
        return result

    monkeypatch.setattr(service, "_match_one", fail_second)
    with pytest.raises(RuntimeError, match="after first fill"):
        service.run_matching_cycle(db)
    assert outcomes == ["filled"]
    db.rollback()
    assert db.query(PaperFill).count() == 0
    assert db.query(PaperAccount).one().cash == 100000
