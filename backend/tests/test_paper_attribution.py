"""盘前计划/盘后归因测试（规格 v2 决策 24；US-3.3；切片 09）。

覆盖：归因纯函数确定性分解、权益序列构建、基准退化、盘前计划快照。
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent_runtime.paper import service as paper_service
from app.agent_runtime.paper.attribution import decompose_returns
from app.config import Base
from app.models.agent_runtime import AgentRun
from app.models.models import DailyKline, Stock
from app.models.paper_trading import (
    PaperAccount,
    PaperCashEvent,
    PaperFill,
    PaperOrder,
)


class TestDecompose:
    def test_alpha_when_portfolio_outperforms(self):
        report = decompose_returns(
            [100.0, 105.0, 110.0],
            [100.0, 102.0, 104.0],
            start_date="2026-08-01",
            end_date="2026-08-03",
        )
        assert report.total_portfolio_return == pytest.approx(0.10, abs=1e-9)
        assert report.total_benchmark_return == pytest.approx(0.04, abs=1e-9)
        assert report.alpha == pytest.approx(0.06, abs=1e-9)
        # 组合波动大于基准 → beta > 1（确定性协方差/方差）
        assert report.beta > 1.0

    def test_cost_drag_reduces_selection(self):
        report = decompose_returns(
            [100.0, 110.0],
            [100.0, 100.0],
            start_date="2026-08-01",
            end_date="2026-08-02",
            total_cost=2.0,
            initial_equity=100.0,
        )
        # alpha = 0.10 - 0 = 0.10；cost_drag = 2%；selection = 0.10 - 0.02
        assert report.cost_drag == pytest.approx(0.02, abs=1e-9)
        assert report.selection_effect == pytest.approx(0.08, abs=1e-9)

    def test_flat_benchmark_beta_zero(self):
        report = decompose_returns(
            [100.0, 101.0],
            [100.0, 100.0],
            start_date="2026-08-01",
            end_date="2026-08-02",
        )
        assert report.beta == 0.0

    def test_insufficient_series_raises(self):
        with pytest.raises(ValueError):
            decompose_returns(
                [100.0], [100.0], start_date="a", end_date="b"
            )


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _seed_account_with_fills(db):
    """账户 + 一笔买入（T 日成交）+ 连续 K 线。"""
    db.add(AgentRun(run_id="run-att-1", objective="测试"))
    db.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    db.add(
        PaperAccount(
            account_id="default",
            cash=999_080.0,
            initial_cash=1_000_000.0,
        )
    )
    order = PaperOrder(
        order_id="po-att-1",
        run_id="run-att-1",
        stock_code="sh.600000",
        side="buy",
        quantity=1000,
        status="filled",
        target_trade_date="2026-08-03",
    )
    db.add(order)
    db.flush()
    db.add(
        PaperFill(
            order_id="po-att-1",
            fill_seq=1,
            trade_date="2026-08-03",
            price=10.0,
            quantity=1000,
            commission=5.0,
            stamp_tax=0.0,
            transfer_fee=0.1,
        )
    )
    db.add(
        PaperCashEvent(
            seq=1,
            event_type="buy",
            amount=-10005.1,
            order_id="po-att-1",
            created_at=datetime(2026, 8, 3, 6, 0, tzinfo=timezone.utc),
        )
    )
    closes = {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.5, 5: 11.0}
    for day, close in closes.items():
        d = date(2026, 8, day)
        db.add(
            DailyKline(
                stock_code="sh.600000",
                date=d,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=100000,
                amount=close * 100000,
            )
        )
    db.commit()


class TestEquitySeries:
    def test_equity_series_marks_positions_at_close(self, db):
        _seed_account_with_fills(db)
        series = paper_service.equity_series(db, "2026-08-01", "2026-08-05")
        assert [s["date"] for s in series] == [
            "2026-08-01",
            "2026-08-02",
            "2026-08-03",
            "2026-08-04",
            "2026-08-05",
        ]
        # 08-03 买入 1000 @10 → 权益 = 989994.9 + 1000*10
        day3 = series[2]
        assert day3["equity"] == pytest.approx(989_994.9 + 10_000.0, abs=1e-3)
        # 08-05 收盘 11 → 市值 11000
        day5 = series[4]
        assert day5["equity"] == pytest.approx(989_994.9 + 11_000.0, abs=1e-3)

    def test_attribution_report_with_benchmark(self, db):
        _seed_account_with_fills(db)
        report = paper_service.attribution_report(
            db,
            "2026-08-01",
            "2026-08-05",
            benchmark_series=[100.0, 100.0, 100.0, 102.0, 103.0],
        )
        assert report["benchmark_available"] is True
        assert report["total_portfolio_return"] > 0
        assert "alpha" in report
        assert "equity_series" in report
        assert report["dates"][-1] == "2026-08-05"

    def test_attribution_degrades_without_benchmark(self, db):
        _seed_account_with_fills(db)
        report = paper_service.attribution_report(db, "2026-08-01", "2026-08-05")
        assert report["benchmark_available"] is False
        # 退化：以组合自身为基准 → alpha = 0
        assert report["alpha"] == 0.0


class TestPreMarketPlan:
    def test_plan_lists_pending_orders(self, db):
        _seed_account_with_fills(db)
        db.add(
            PaperOrder(
                order_id="po-plan-1",
                run_id="run-att-1",
                stock_code="sh.600000",
                side="buy",
                quantity=100,
                status="pending_approval",
            )
        )
        db.commit()
        plan = paper_service.pre_market_plan(db)
        assert [o["order_id"] for o in plan["orders"]] == ["po-plan-1"]
        assert plan["as_of"]
