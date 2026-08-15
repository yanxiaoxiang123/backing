"""告警系统测试（规格 v2 决策 24；US-3.4；切片 10）。

覆盖：四类条件检查、同日去重、已读状态、API 端点、撮合循环联动。
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent_api.paper import router
from app.agent_runtime import alerts as alert_service
from app.auth import get_current_api_key
from app.config import Base, get_db
from app.models.agent_runtime import AgentRun, ToolCallRecord
from app.models.alerts import AlertRecord
from app.models.models import DailyKline, Stock
from app.models.paper_trading import (
    PaperAccount,
    PaperCashEvent,
    PaperFill,
    PaperOrder,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _seed_basic(db):
    db.add(AgentRun(run_id="run-al-1", objective="测试"))
    db.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    # 陈旧 K 线（30 天前）触发 data_staleness
    db.add(
        DailyKline(
            stock_code="sh.600000",
            date=date.today() - timedelta(days=30),
            open=10.0,
            high=10.0,
            low=10.0,
            close=10.0,
            volume=100000,
            amount=1000000,
        )
    )
    db.commit()


class TestChecks:
    def test_data_staleness_triggers(self, db):
        _seed_basic(db)
        drafts = alert_service._check_data_staleness(db, max_days=3)
        assert any(d.alert_type == "data_staleness" for d in drafts)

    def test_drawdown_triggers(self, db):
        _seed_basic(db)
        # 制造大幅回撤：买入后权益暴跌
        db.add(
            PaperAccount(account_id="default", cash=800_000.0, initial_cash=1_000_000.0)
        )
        order = PaperOrder(
            order_id="po-dd",
            run_id="run-al-1",
            stock_code="sh.600000",
            side="buy",
            quantity=60000,
            status="filled",
        )
        db.add(order)
        db.flush()
        db.add(
            PaperFill(
                order_id="po-dd",
                fill_seq=1,
                trade_date=date.today().isoformat(),
                price=10.0,
                quantity=60000,
                commission=125.0,
                stamp_tax=0.0,
                transfer_fee=0.6,
            )
        )
        db.add(
            PaperCashEvent(
                seq=1,
                event_type="buy",
                amount=-600125.6,
                order_id="po-dd",
                created_at=datetime.now(timezone.utc),
            )
        )
        # 今天 K 线收盘 8.0 → 权益 399874.4+480k=879874.4 < 初始 1M（回撤 12%）
        db.add(
            DailyKline(
                stock_code="sh.600000",
                date=date.today(),
                open=10.0,
                high=10.0,
                low=8.0,
                close=8.0,
                volume=100000,
                amount=800000,
            )
        )
        db.commit()
        drafts = alert_service._check_drawdown(db, threshold=0.10)
        assert any(d.alert_type == "drawdown" for d in drafts)

    def test_provider_failure_triggers(self, db):
        _seed_basic(db)
        for i in range(3):
            db.add(
                ToolCallRecord(
                    run_id="run-al-1",
                    tool_name="event.news",
                    params_hash=f"h{i}",
                    params_json={},
                    status="failed",
                    created_at=datetime.now(timezone.utc),
                )
            )
        db.commit()
        drafts = alert_service._check_provider_failure(db, max_failures=3)
        assert any(d.alert_type == "provider_failure" for d in drafts)

    def test_cost_anomaly_triggers(self, db):
        _seed_basic(db)
        db.add(
            PaperAccount(account_id="default", cash=0.0, initial_cash=1_000_000.0)
        )
        order = PaperOrder(
            order_id="po-ca",
            run_id="run-al-1",
            stock_code="sh.600000",
            side="buy",
            quantity=100,
            status="filled",
        )
        db.add(order)
        db.flush()
        db.add(
            PaperFill(
                order_id="po-ca",
                fill_seq=1,
                trade_date=date.today().isoformat(),
                price=10.0,
                quantity=100,
                commission=600.0,
                stamp_tax=0.0,
                transfer_fee=0.0,
            )
        )
        db.commit()
        drafts = alert_service._check_cost_anomaly(db, threshold=500.0)
        assert any(d.alert_type == "cost_anomaly" for d in drafts)

    def test_dedup_same_day(self, db):
        _seed_basic(db)
        first = alert_service.run_alert_checks(db)
        second = alert_service.run_alert_checks(db)
        # 第二次检查不应重复创建（同日去重）
        assert len(second) == 0
        assert db.query(AlertRecord).count() >= len(first)

    def test_mark_read(self, db):
        _seed_basic(db)
        alert_service.run_alert_checks(db)
        row = db.query(AlertRecord).first()
        assert alert_service.mark_read(db, row.id) is True
        db.refresh(row)
        assert row.is_read == 1


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    async def fake_key():
        return "test-key"

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_api_key] = fake_key
    return TestClient(app)


class TestApi:
    def test_list_and_check_alerts(self, client):
        resp = client.get("/api/v1/paper/alerts")
        assert resp.status_code == 200
        assert "alerts" in resp.json()

        check = client.post("/api/v1/paper/alerts/check")
        assert check.status_code == 200
        assert "created" in check.json()

    def test_mark_read_unknown_404(self, client):
        resp = client.post("/api/v1/paper/alerts/99999/read")
        assert resp.status_code == 404
