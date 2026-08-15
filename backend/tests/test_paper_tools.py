"""execution.paper.* 工具域测试（规格 v2 决策 21-22；US-3.1/3.2；切片 04）。

覆盖：提议/撤销/查询、参数校验、权限分级、事件 append-only、run/approval 关联。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.models.agent_runtime import AgentRun, ApprovalRecord
from app.models.models import Stock
from app.models.paper_trading import (
    PaperAccount,
    PaperOrder,
    PaperOrderEvent,
    PaperPosition,
)
from app.tools import DEFAULT_REGISTRY, ToolContext


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def db():
    session = sessionmaker(bind=_engine())()
    yield session
    session.close()


def _seed_run_and_stock(db, run_id="run-paper-1"):
    db.add(AgentRun(run_id=run_id, objective="测试"))
    db.add(Stock(code="sh.600519", name="贵州茅台", market="sh"))
    db.add(PaperAccount(account_id="default", cash=1_000_000.0, initial_cash=1_000_000.0))
    db.commit()
    return run_id


def _ctx(db, run_id, permissions=("read", "approval")):
    return ToolContext(
        granted_permissions=set(permissions), run_id=run_id, db=db
    )


def _propose(db, run_id, **overrides):
    params = {"stock_code": "sh.600519", "side": "buy", "quantity": 100}
    params.update(overrides)
    result = DEFAULT_REGISTRY.invoke(
        "execution.paper.propose_order", params, _ctx(db, run_id)
    )
    assert result["ok"] is True
    return result["data"]["order_id"]


class TestPropose:
    def test_creates_order_approval_and_event(self, db):
        run_id = _seed_run_and_stock(db)
        order_id = _propose(db, run_id, limit_price=10.5, trigger_note="测试触发")
        order = (
            db.query(PaperOrder)
            .filter(PaperOrder.order_id == order_id)
            .one()
        )
        assert order.status == "pending_approval"
        assert order.run_id == run_id
        assert order.limit_price == 10.5
        assert order.trigger_note == "测试触发"
        approval = db.get(ApprovalRecord, order.approval_id)
        assert approval is not None
        assert approval.status == "pending"
        assert approval.action == "paper.order"
        events = (
            db.query(PaperOrderEvent)
            .filter(PaperOrderEvent.order_id == order_id)
            .order_by(PaperOrderEvent.seq.asc())
            .all()
        )
        assert [(e.seq, e.event_type) for e in events] == [(1, "proposed")]

    def test_rejects_unknown_stock(self, db):
        run_id = _seed_run_and_stock(db)
        result = DEFAULT_REGISTRY.invoke(
            "execution.paper.propose_order",
            {"stock_code": "sh.999999", "side": "buy", "quantity": 100},
            _ctx(db, run_id),
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "handler"

    def test_requires_run_context(self, db):
        _seed_run_and_stock(db)
        ctx = ToolContext(granted_permissions={"read", "approval"}, db=db)
        result = DEFAULT_REGISTRY.invoke(
            "execution.paper.propose_order",
            {"stock_code": "sh.600519", "side": "buy", "quantity": 100},
            ctx,
        )
        assert result["ok"] is False
        assert "run" in result["error"]["message"]


class TestCancel:
    def test_cancel_pending_order_appends_event(self, db):
        run_id = _seed_run_and_stock(db)
        order_id = _propose(db, run_id)
        result = DEFAULT_REGISTRY.invoke(
            "execution.paper.cancel_order",
            {"order_id": order_id},
            _ctx(db, run_id),
        )
        assert result["ok"] is True
        assert result["data"]["status"] == "cancelled"
        order = (
            db.query(PaperOrder)
            .filter(PaperOrder.order_id == order_id)
            .one()
        )
        assert order.status == "cancelled"
        events = (
            db.query(PaperOrderEvent)
            .filter(PaperOrderEvent.order_id == order_id)
            .order_by(PaperOrderEvent.seq.asc())
            .all()
        )
        assert [(e.seq, e.event_type) for e in events] == [
            (1, "proposed"),
            (2, "cancelled"),
        ]

    def test_cancel_filled_order_fails(self, db):
        run_id = _seed_run_and_stock(db)
        order_id = _propose(db, run_id)
        order = (
            db.query(PaperOrder)
            .filter(PaperOrder.order_id == order_id)
            .one()
        )
        order.status = "filled"
        db.commit()
        result = DEFAULT_REGISTRY.invoke(
            "execution.paper.cancel_order",
            {"order_id": order_id},
            _ctx(db, run_id),
        )
        assert result["ok"] is False
        assert "不可撤销" in result["error"]["message"]

    def test_cancel_requires_approval_permission(self, db):
        run_id = _seed_run_and_stock(db)
        order_id = _propose(db, run_id)
        ctx = ToolContext(granted_permissions={"read"}, run_id=run_id, db=db)
        result = DEFAULT_REGISTRY.invoke(
            "execution.paper.cancel_order", {"order_id": order_id}, ctx
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "permission_denied"


class TestQueries:
    def test_positions_account_orders(self, db):
        run_id = _seed_run_and_stock(db)
        order_id = _propose(db, run_id)
        db.add(
            PaperPosition(stock_code="sh.600519", quantity=100, avg_cost=10.5)
        )
        db.commit()

        ctx = _ctx(db, run_id, permissions=("read",))
        pos_env = DEFAULT_REGISTRY.invoke(
            "execution.paper.positions", {}, ctx
        )
        assert pos_env["ok"] is True
        assert pos_env["data"]["positions"][0]["quantity"] == 100

        acc_env = DEFAULT_REGISTRY.invoke("execution.paper.account", {}, ctx)
        assert acc_env["ok"] is True
        assert acc_env["data"]["cash"] == 1_000_000.0

        ord_env = DEFAULT_REGISTRY.invoke(
            "execution.paper.orders", {"status": "pending_approval"}, ctx
        )
        assert ord_env["ok"] is True
        assert [o["order_id"] for o in ord_env["data"]["orders"]] == [order_id]

    def test_query_tools_are_read_permission(self):
        by_name = {t["name"]: t for t in DEFAULT_REGISTRY.list_tools()}
        for name in (
            "execution.paper.positions",
            "execution.paper.account",
            "execution.paper.orders",
        ):
            assert by_name[name]["permission"] == "read"
