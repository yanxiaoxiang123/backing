"""模拟盘服务测试（规格 v2 决策 21-23；US-3.1/3.2/3.5；切片 05）。

覆盖：审批状态机全路径、撮合循环（成交/过期/T+1/一字板/现金不足/限价）、
窗口过期、数据未到 noop、幂等、重放一致性。
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent_runtime.paper import service as paper_service
from app.agent_runtime.paper.replay import replay_account
from app.config import Base
from app.models.agent_runtime import AgentRun, ApprovalRecord
from app.models.models import DailyKline, Stock
from app.models.paper_trading import (
    PaperAccount,
    PaperCashEvent,
    PaperFill,
    PaperOrder,
    PaperOrderEvent,
    PaperPosition,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def freeze_paper_clock(monkeypatch):
    """固定审批时钟，避免日历推进让窗口测试依赖真实系统日期。"""
    monkeypatch.setattr(
        paper_service,
        "_now_utc",
        lambda: datetime(2026, 8, 15, 7, 0, tzinfo=timezone.utc),
    )


def _seed(db, code="sh.600000", days=35, start=date(2026, 7, 15)):
    """连续日历日 K 线（覆盖 2026-08-15 前后，保证审批后存在下一交易日）。"""
    db.add(AgentRun(run_id="run-p1", objective="测试"))
    db.add(Stock(code=code, name="浦发银行", market="sh"))
    closes = [10.0, 10.2, 10.5, 10.9, 11.2, 10.8, 10.4, 10.0, 9.8, 10.3]
    for idx in range(days):
        close = closes[idx % len(closes)]
        day = start + timedelta(days=idx)
        db.add(
            DailyKline(
                stock_code=code,
                date=day,
                open=round(close - 0.1, 2),
                high=round(close + 0.2, 2),
                low=round(close - 0.2, 2),
                close=close,
                volume=100000 + idx * 1000,
                amount=close * 100000,
            )
        )
    db.commit()


def _propose(
    db,
    order_id="po-1",
    *,
    side="buy",
    quantity=100,
    limit_price=None,
    status="pending_approval",
    stock_code="sh.600000",
):
    order = PaperOrder(
        order_id=order_id,
        run_id="run-p1",
        stock_code=stock_code,
        side=side,
        quantity=quantity,
        limit_price=limit_price,
        status=status,
    )
    db.add(order)
    db.flush()
    approval = ApprovalRecord(
        run_id="run-p1",
        action="paper.order",
        summary=f"{side} {quantity} 股",
        direction=side,
        status="pending",
    )
    db.add(approval)
    db.flush()
    order.approval_id = approval.id
    db.add(
        PaperOrderEvent(order_id=order.order_id, seq=1, event_type="proposed")
    )
    db.commit()
    return order.order_id, approval.id


class TestDecideApproval:
    def test_approve_sets_target_and_events(self, db):
        _seed(db)
        order_id, approval_id = _propose(db)
        result = paper_service.decide_approval(db, approval_id, "approved")
        assert result["status"] == "approved"
        order = (
            db.query(PaperOrder)
            .filter(PaperOrder.order_id == order_id)
            .one()
        )
        assert order.status == "approved"
        assert order.target_trade_date is not None
        approval = db.get(ApprovalRecord, approval_id)
        assert approval.status == "approved"
        assert approval.expires_at is not None
        events = (
            db.query(PaperOrderEvent)
            .filter(PaperOrderEvent.order_id == order_id)
            .order_by(PaperOrderEvent.seq.asc())
            .all()
        )
        assert [(e.seq, e.event_type) for e in events] == [
            (1, "proposed"),
            (2, "approved"),
        ]

    def test_reject_sets_order_rejected(self, db):
        _seed(db)
        order_id, approval_id = _propose(db)
        result = paper_service.decide_approval(db, approval_id, "rejected")
        assert result["status"] == "rejected"
        order = (
            db.query(PaperOrder)
            .filter(PaperOrder.order_id == order_id)
            .one()
        )
        assert order.status == "rejected"

    def test_cannot_decide_twice(self, db):
        _seed(db)
        _, approval_id = _propose(db)
        paper_service.decide_approval(db, approval_id, "approved")
        with pytest.raises(ValueError, match="不可再决策"):
            paper_service.decide_approval(db, approval_id, "rejected")

    def test_invalid_decision_rejected(self, db):
        _seed(db)
        _, approval_id = _propose(db)
        with pytest.raises(ValueError, match="非法决策"):
            paper_service.decide_approval(db, approval_id, "maybe")


class TestMatchingCycle:
    def test_approved_buy_fills_at_open(self, db):
        _seed(db)
        _, approval_id = _propose(db)
        paper_service.decide_approval(db, approval_id, "approved")
        order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-1").one()
        target = order.target_trade_date
        bar_date = date.fromisoformat(target)
        bar = (
            db.query(DailyKline)
            .filter(DailyKline.stock_code == "sh.600000", DailyKline.date == bar_date)
            .one()
        )
        summary = paper_service.run_matching_cycle(db)
        assert summary["filled"] == 1
        db.refresh(order)
        assert order.status == "filled"
        fill = db.query(PaperFill).filter(PaperFill.order_id == "po-1").one()
        assert fill.trade_date == target
        assert fill.price == float(bar.open)
        assert fill.quantity == 100
        pos = (
            db.query(PaperPosition)
            .filter(PaperPosition.stock_code == "sh.600000")
            .one()
        )
        assert pos.quantity == 100
        assert pos.avg_cost == pytest.approx(float(bar.open), abs=1e-4)
        events = (
            db.query(PaperOrderEvent)
            .filter(PaperOrderEvent.order_id == "po-1")
            .order_by(PaperOrderEvent.seq.asc())
            .all()
        )
        assert [e.event_type for e in events] == ["proposed", "approved", "filled"]

    def test_pending_approval_order_never_fills(self, db):
        """无审批任何订单不成交（US-3.2 硬约束）。"""
        _seed(db)
        _propose(db)  # 保持 pending_approval
        summary = paper_service.run_matching_cycle(db)
        for key in ("processed", "filled", "expired", "noop"):
            assert summary[key] == 0
        order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-1").one()
        assert order.status == "pending_approval"

    def test_sell_t_plus_1_blocks_same_day_buy(self, db):
        _seed(db)
        # 买入订单在 T 成交
        _, buy_approval = _propose(db, order_id="po-buy")
        paper_service.decide_approval(db, buy_approval, "approved")
        paper_service.run_matching_cycle(db)
        buy_order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-buy").one()
        target = buy_order.target_trade_date
        # 同日卖出同份额订单 → T+1 可用不足 → expired
        _, sell_approval = _propose(db, order_id="po-sell", side="sell", quantity=100)
        paper_service.decide_approval(db, sell_approval, "approved")
        sell_order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-sell").one()
        sell_order.target_trade_date = target
        db.commit()
        summary = paper_service.run_matching_cycle(db)
        db.refresh(sell_order)
        assert summary["expired"] == 1
        assert sell_order.status == "expired"

    def test_sell_fills_with_prior_position(self, db):
        _seed(db)
        db.add(
            PaperPosition(stock_code="sh.600000", quantity=100, avg_cost=10.0)
        )
        _, approval_id = _propose(db, order_id="po-sell", side="sell", quantity=100)
        paper_service.decide_approval(db, approval_id, "approved")
        summary = paper_service.run_matching_cycle(db)
        assert summary["filled"] == 1
        pos = (
            db.query(PaperPosition)
            .filter(PaperPosition.stock_code == "sh.600000")
            .one_or_none()
        )
        assert pos is None or pos.quantity == 0

    def test_one_word_limit_up_no_fill(self, db):
        _seed(db, code="sh.600001")
        # 在最后一个 bar 日期制造一字涨停，目标窗口指向它
        last = (
            db.query(DailyKline)
            .filter(DailyKline.stock_code == "sh.600001")
            .order_by(DailyKline.date.desc())
            .first()
        )
        target = last.date
        prev_close = (
            db.query(DailyKline)
            .filter(
                DailyKline.stock_code == "sh.600001",
                DailyKline.date < target,
            )
            .order_by(DailyKline.date.desc())
            .first()
        )
        limit_up = round(float(prev_close.close) * 1.1, 2)
        last.open = last.high = last.low = limit_up
        db.commit()
        _, approval_id = _propose(
            db, order_id="po-limit", stock_code="sh.600001"
        )
        paper_service.decide_approval(db, approval_id, "approved")
        order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-limit").one()
        order.target_trade_date = target.isoformat()
        db.commit()
        summary = paper_service.run_matching_cycle(db)
        db.refresh(order)
        assert summary["expired"] == 1
        assert order.status == "expired"

    def test_limit_price_rejects_above_open(self, db):
        _seed(db)
        _, approval_id = _propose(db, order_id="po-lp", limit_price=1.0)
        paper_service.decide_approval(db, approval_id, "approved")
        summary = paper_service.run_matching_cycle(db)
        order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-lp").one()
        assert summary["expired"] == 1
        assert order.status == "expired"

    def test_window_passed_without_bar_expires(self, db):
        _seed(db)
        # 删除目标日的 bar（模拟停牌），但存在更晚的 bar → 窗口过期
        _, approval_id = _propose(db, order_id="po-susp")
        paper_service.decide_approval(db, approval_id, "approved")
        order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-susp").one()
        target = order.target_trade_date
        db.query(DailyKline).filter(
            DailyKline.stock_code == "sh.600000",
            DailyKline.date == date.fromisoformat(target),
        ).delete()
        db.commit()
        summary = paper_service.run_matching_cycle(db)
        db.refresh(order)
        assert summary["expired"] == 1
        assert order.status == "expired"

    def test_data_not_yet_available_is_noop(self, db):
        _seed(db, days=20)  # 最后一个 bar 在 08-03 前后
        _, approval_id = _propose(db, order_id="po-future")
        paper_service.decide_approval(db, approval_id, "approved")
        order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-future").one()
        order.target_trade_date = "2026-12-01"  # 远超现有数据
        db.commit()
        summary = paper_service.run_matching_cycle(db)
        db.refresh(order)
        assert summary["noop"] == 1
        assert order.status == "approved"  # 数据到达前保持 approved

    def test_insufficient_cash_expires(self, db):
        _seed(db)
        _, approval_id = _propose(db, order_id="po-cash", quantity=100_000)
        paper_service.decide_approval(db, approval_id, "approved")
        summary = paper_service.run_matching_cycle(db)
        order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-cash").one()
        assert summary["expired"] == 1
        assert order.status == "expired"

    def test_cycle_is_idempotent(self, db):
        _seed(db)
        _, approval_id = _propose(db)
        paper_service.decide_approval(db, approval_id, "approved")
        first = paper_service.run_matching_cycle(db)
        assert first["filled"] == 1
        second = paper_service.run_matching_cycle(db)
        assert second["processed"] == 0  # 无重复处理/成交

    def test_approval_waits_for_next_bar_then_fills(self, db):
        """审批时无下一交易日数据（周末/同步滞后）→ 等待；数据到达后成交。"""
        _seed(db, days=20)  # bar 止于 08-03（早于审批日 08-15）
        _, approval_id = _propose(db, order_id="po-wait")
        paper_service.decide_approval(db, approval_id, "approved")
        order = db.query(PaperOrder).filter(PaperOrder.order_id == "po-wait").one()
        assert order.target_trade_date is None
        summary = paper_service.run_matching_cycle(db)
        db.refresh(order)
        assert summary["noop"] == 1
        assert order.status == "approved"  # 等待下一交易日数据

        # 新 bar 到达（模拟周一同步）→ 下一撮合窗口成交
        last = (
            db.query(DailyKline)
            .filter(DailyKline.stock_code == "sh.600000")
            .order_by(DailyKline.date.desc())
            .first()
        )
        prev_close = float(last.close)
        db.add(
            DailyKline(
                stock_code="sh.600000",
                date=date(2026, 8, 17),
                open=round(prev_close + 0.1, 2),
                high=round(prev_close + 0.3, 2),
                low=round(prev_close - 0.1, 2),
                close=round(prev_close + 0.2, 2),
                volume=100000,
                amount=(prev_close + 0.2) * 100000,
            )
        )
        db.commit()
        summary2 = paper_service.run_matching_cycle(db)
        db.refresh(order)
        assert summary2["filled"] == 1
        assert order.status == "filled"
        assert order.target_trade_date == "2026-08-17"


class TestReplayConsistency:
    def test_account_state_matches_replay(self, db):
        _seed(db)
        _, approval_id = _propose(db)
        paper_service.decide_approval(db, approval_id, "approved")
        paper_service.run_matching_cycle(db)
        state = paper_service.account_state(db)
        cash_events = [
            {"event_type": e.event_type, "amount": e.amount}
            for e in db.query(PaperCashEvent).order_by(PaperCashEvent.seq.asc()).all()
        ]
        fills = [
            {
                "stock_code": o.stock_code,
                "side": o.side,
                "price": f.price,
                "quantity": f.quantity,
            }
            for f, o in db.query(PaperFill, PaperOrder)
            .join(PaperOrder, PaperOrder.order_id == PaperFill.order_id)
            .all()
        ]
        replayed = replay_account(
            initial_cash=paper_service.DEFAULT_INITIAL_CASH,
            cash_events=cash_events,
            fills=fills,
        )
        assert state["cash"] == pytest.approx(replayed["cash"], abs=1e-4)
        assert state["positions"] == [
            {"stock_code": code, **pos}
            for code, pos in replayed["positions"].items()
        ]


class TestAccountEnsure:
    def test_ensure_account_creates_default(self, db):
        paper_service.ensure_account(db)
        account = (
            db.query(PaperAccount)
            .filter(PaperAccount.account_id == paper_service.DEFAULT_ACCOUNT_ID)
            .one()
        )
        assert account.cash == paper_service.DEFAULT_INITIAL_CASH


class TestConcurrency:
    def test_concurrent_cycles_no_double_fill(self, tmp_path):
        """并发撮合（soak 线程 vs 手动 API）只成交一次（规格风险 4 回归）。"""
        from threading import Barrier, Thread

        # 文件型 SQLite：多连接共享同一库（内存库每连接独立，无法模拟并发）
        engine = create_engine(f"sqlite:///{tmp_path / 'conc.db'}")
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        try:
            _seed(db)
            _, approval_id = _propose(db, order_id="po-conc")
            paper_service.decide_approval(db, approval_id, "approved")
            order = (
                db.query(PaperOrder)
                .filter(PaperOrder.order_id == "po-conc")
                .one()
            )
            order.target_trade_date = "2026-08-17"
            db.commit()

            barrier = Barrier(2)

            def worker():
                session = sessionmaker(bind=engine)()
                try:
                    barrier.wait()
                    paper_service.run_matching_cycle(session)
                finally:
                    session.close()

            threads = [Thread(target=worker) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            order = (
                db.query(PaperOrder)
                .filter(PaperOrder.order_id == "po-conc")
                .one()
            )
            assert order.status == "filled"
            fills = (
                db.query(PaperFill)
                .filter(PaperFill.order_id == "po-conc")
                .count()
            )
            assert fills == 1, "并发撮合不得重复成交"
            cash_seq = [
                e.seq
                for e in db.query(PaperCashEvent)
                .order_by(PaperCashEvent.seq)
                .all()
            ]
            assert len(cash_seq) == len(set(cash_seq)), "资金事件 seq 不得重复"
        finally:
            db.close()
