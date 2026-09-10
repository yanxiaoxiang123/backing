"""Tool Gateway 测试（任务 08 验收）。

覆盖：allowlist、权限矩阵、参数校验、envelope（source_id/as_of/vendor）、
输出限制、tool_calls 事实记录、确定性服务包装（provider 全部 mock/内存库）。
"""

import hashlib
import json
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.strategy  # noqa: F401  （注册策略副作用）
from app.agent_runtime.stores import create_stores
from app.config import Base
from app.models.models import DailyKline, Stock
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


def _seed_stock_and_klines(session):
    session.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    start = date(2024, 1, 1)
    closes = [10, 10.2, 10.5, 10.9, 11.2, 10.8, 10.4, 10.0, 9.8, 10.3, 10.9, 11.4]
    for idx, close in enumerate(closes):
        session.add(
            DailyKline(
                stock_code="sh.600000",
                date=start + timedelta(days=idx),
                open=close - 0.1,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=100000 + idx * 1000,
                amount=close * 100000,
            )
        )
    session.commit()


# ---------- 注册表与 allowlist ----------

def test_registry_allowlist_has_eight_domains():
    names = DEFAULT_REGISTRY.allowlist
    assert "market.kline" in names
    assert "market.snapshot" in names
    assert "factor.indicators" in names
    assert "fundamental.stock_info" in names
    assert "strategy.list" in names
    assert "strategy.validate" in names
    assert "backtest.run" in names
    assert "portfolio.constraints" in names
    assert "execution.paper.propose_order" in names


def test_list_tools_shape():
    tools = DEFAULT_REGISTRY.list_tools()
    by_name = {t["name"]: t for t in tools}
    assert "input_schema" in by_name["market.kline"]
    assert by_name["execution.paper.propose_order"]["permission"] == "approval"


def test_unknown_tool_rejected():
    ctx = ToolContext()
    result = DEFAULT_REGISTRY.invoke("market.unknown", {}, ctx)
    assert result["ok"] is False
    assert result["error"]["code"] == "unknown_tool"


# ---------- 权限矩阵 ----------

def test_strategy_tool_denied_without_permission():
    ctx = ToolContext()  # 默认只有 read
    result = DEFAULT_REGISTRY.invoke(
        "strategy.validate", {"spec": {"name": "x", "signal": "ma_cross"}}, ctx
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "permission_denied"


def test_strategy_tool_allowed_with_grant():
    ctx = ToolContext(granted_permissions={"read", "strategy"})
    spec = {
        "name": "测试策略",
        "signal": "ma_cross",
        "signal_parameters": {"short_period": 5, "long_period": 20},
    }
    result = DEFAULT_REGISTRY.invoke("strategy.validate", {"spec": spec}, ctx)
    assert result["ok"] is True
    assert result["data"]["valid"] is True


def test_strategy_validate_unknown_signal_fails():
    ctx = ToolContext(granted_permissions={"read", "strategy"})
    result = DEFAULT_REGISTRY.invoke(
        "strategy.validate", {"spec": {"name": "x", "signal": "no_such_signal"}}, ctx
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "handler"


def test_paper_propose_denied_without_approval():
    ctx = ToolContext()
    result = DEFAULT_REGISTRY.invoke(
        "execution.paper.propose_order",
        {"stock_code": "sh.600519", "side": "buy", "quantity": 100},
        ctx,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "permission_denied"


def test_paper_propose_creates_order_and_approval(db):
    from app.models.agent_runtime import AgentRun

    db.add(AgentRun(run_id="run-1", objective="测试"))
    db.add(Stock(code="sh.600519", name="贵州茅台", market="sh"))
    db.commit()
    ctx = ToolContext(
        granted_permissions={"read", "approval"}, run_id="run-1", db=db
    )
    result = DEFAULT_REGISTRY.invoke(
        "execution.paper.propose_order",
        {"stock_code": "sh.600519", "side": "buy", "quantity": 100},
        ctx,
    )
    assert result["ok"] is True
    assert result["data"]["status"] == "pending_approval"
    assert result["data"]["order_id"].startswith("po-")
    from app.models.paper_trading import PaperOrder, PaperOrderEvent

    order = (
        db.query(PaperOrder)
        .filter(PaperOrder.order_id == result["data"]["order_id"])
        .one()
    )
    assert order.status == "pending_approval"
    assert order.approval_id is not None
    event = (
        db.query(PaperOrderEvent)
        .filter(PaperOrderEvent.order_id == order.order_id)
        .one()
    )
    assert event.event_type == "proposed"
    assert event.seq == 1


# ---------- 参数校验 ----------

def test_invalid_params_rejected():
    ctx = ToolContext()
    result = DEFAULT_REGISTRY.invoke(
        "market.kline",
        {"stock_code": "sh.600519", "start_date": "bad-date", "end_date": "2026-01-01"},
        ctx,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "validation"


def test_paper_propose_bad_lot_rejected(db):
    from app.models.agent_runtime import AgentRun

    db.add(AgentRun(run_id="run-1", objective="测试"))
    db.add(Stock(code="sh.600519", name="贵州茅台", market="sh"))
    db.commit()
    ctx = ToolContext(
        granted_permissions={"read", "approval"}, run_id="run-1", db=db
    )
    result = DEFAULT_REGISTRY.invoke(
        "execution.paper.propose_order",
        {"stock_code": "sh.600519", "side": "buy", "quantity": 150},
        ctx,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "handler"
    assert "整数倍" in result["error"]["message"]


# ---------- 确定性服务包装 ----------

def test_market_kline_envelope(monkeypatch):
    df = pd.DataFrame(
        {
            "date": ["2026-01-05", "2026-01-06"],
            "close": [10.0, 10.2],
            "open": [9.9, 10.1],
            "high": [10.3, 10.4],
            "low": [9.8, 10.0],
            "volume": [1000, 1100],
        }
    )
    from app.tools import market as market_module

    monkeypatch.setattr(
        market_module.baostock_service, "get_daily_kline", lambda *a, **k: df
    )

    ctx = ToolContext()
    result = DEFAULT_REGISTRY.invoke(
        "market.kline",
        {"stock_code": "SH600519", "start_date": "2026-01-01", "end_date": "2026-01-10"},
        ctx,
    )
    assert result["ok"] is True
    assert result["source_id"].startswith("kline:sh.600519:")
    assert result["as_of"] is not None
    assert result["vendor"] == "backend"
    assert result["data"]["rows"] == 2
    assert result["data"]["kline"][0]["close"] == 10.0


def test_market_kline_empty_data_fails(monkeypatch):
    from app.tools import market as market_module

    monkeypatch.setattr(
        market_module.baostock_service, "get_daily_kline", lambda *a, **k: pd.DataFrame()
    )
    ctx = ToolContext()
    result = DEFAULT_REGISTRY.invoke(
        "market.kline",
        {"stock_code": "sh.600000", "start_date": "2026-01-01", "end_date": "2026-01-10"},
        ctx,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "handler"


def test_market_snapshot_with_db(db):
    _seed_stock_and_klines(db)
    ctx = ToolContext(db=db)
    result = DEFAULT_REGISTRY.invoke(
        "market.snapshot", {"stock_code": "sh600000"}, ctx
    )
    assert result["ok"] is True
    assert result["data"]["latest"]["close"] == 11.4


def test_factor_indicators_with_db(db):
    _seed_stock_and_klines(db)
    ctx = ToolContext(db=db)
    result = DEFAULT_REGISTRY.invoke(
        "factor.indicators", {"stock_code": "sh.600000", "limit": 5}, ctx
    )
    assert result["ok"] is True
    assert result["data"]["rows"] == 5


def test_fundamental_stock_info(db):
    _seed_stock_and_klines(db)
    ctx = ToolContext(db=db)
    result = DEFAULT_REGISTRY.invoke(
        "fundamental.stock_info", {"stock_code": "600000"}, ctx
    )
    assert result["ok"] is True
    assert result["data"]["name"] == "浦发银行"
    assert result["data"]["market"] == "sh"
    assert isinstance(result["data"]["as_of"], str)
    # Agent chat persists the complete tool result in a JSON column.
    json.dumps(result, ensure_ascii=False)


def test_fundamental_unknown_stock_fails(db):
    ctx = ToolContext(db=db)
    result = DEFAULT_REGISTRY.invoke(
        "fundamental.stock_info", {"stock_code": "sh.999999"}, ctx
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "handler"


def test_strategy_list():
    ctx = ToolContext()
    result = DEFAULT_REGISTRY.invoke("strategy.list", {}, ctx)
    assert result["ok"] is True
    assert "ma_cross" in result["data"]["strategies"]


def test_backtest_run_with_db(db):
    _seed_stock_and_klines(db)
    ctx = ToolContext(db=db, granted_permissions={"read", "strategy"})
    result = DEFAULT_REGISTRY.invoke(
        "backtest.run",
        {
            "strategy_name": "ma_cross",
            "stock_code": "sh.600000",
            "start_date": "2024-01-01",
            "end_date": "2024-01-12",
            "parameters": {"short_period": 2, "long_period": 3},
        },
        ctx,
    )
    assert result["ok"] is True
    assert result["data"]["result"]["strategy_name"] == "ma_cross"
    assert result["data"]["result"]["final_capital"] > 0


def test_backtest_run_requires_strategy_permission(db):
    ctx = ToolContext(db=db)  # 只有 read
    result = DEFAULT_REGISTRY.invoke(
        "backtest.run",
        {
            "strategy_name": "ma_cross",
            "stock_code": "sh.600000",
            "start_date": "2024-01-01",
            "end_date": "2024-01-12",
        },
        ctx,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "permission_denied"


# ---------- 组合硬约束 ----------

def test_portfolio_constraints_ok():
    ctx = ToolContext()
    result = DEFAULT_REGISTRY.invoke(
        "portfolio.constraints",
        {
            "positions": [
                {"code": "600000", "action": "buy", "weight": 0.3, "shares": 100},
                {"code": "000001", "action": "buy", "weight": 0.3, "shares": 200},
            ]
        },
        ctx,
    )
    assert result["ok"] is True
    assert result["data"]["passed"] is True


def test_portfolio_constraints_weight_over_one():
    ctx = ToolContext()
    result = DEFAULT_REGISTRY.invoke(
        "portfolio.constraints",
        {
            "positions": [
                {"code": "600000", "action": "buy", "weight": 0.6},
                {"code": "000001", "action": "buy", "weight": 0.6},
            ]
        },
        ctx,
    )
    assert result["ok"] is True
    assert result["data"]["passed"] is False
    assert result["data"]["rejected"] is True


def test_portfolio_constraints_lot_and_t_plus_1():
    ctx = ToolContext()
    result = DEFAULT_REGISTRY.invoke(
        "portfolio.constraints",
        {
            "positions": [
                {"code": "sh600000", "action": "buy", "weight": 0.2, "shares": 150},
                {"code": "600000", "action": "sell", "weight": 0.1, "shares": 100},
            ]
        },
        ctx,
    )
    assert result["ok"] is True
    assert result["data"]["passed"] is False
    rules = {r["rule"] for r in result["data"]["constraints"]}
    assert {"lot_size", "t_plus_1"} <= rules


# ---------- tool_calls 事实记录 ----------

def test_tool_call_recorded_when_stores_provided():
    session = sessionmaker(bind=_engine())()
    stores = create_stores(session)
    stores.runs.create_run(run_id="run-9", objective="网关测试")
    ctx = ToolContext(stores=stores, run_id="run-9")

    result = DEFAULT_REGISTRY.invoke("strategy.list", {}, ctx)
    assert result["ok"] is True

    calls = stores.tool_calls.list_tool_calls("run-9")
    assert len(calls) == 1
    assert calls[0]["tool_name"] == "strategy.list"
    assert calls[0]["permission"] == "read"
    assert calls[0]["status"] == "ok"
    assert calls[0]["params_hash"] == hashlib.sha256(b"{}").hexdigest()
    session.close()


def test_stock_tool_normalizes_input_and_audit_params(db):
    _seed_stock_and_klines(db)
    stores = create_stores(db)
    stores.runs.create_run(run_id="run-stock-code", objective="研究 sh.600000")
    ctx = ToolContext(db=db, stores=stores, run_id="run-stock-code")

    result = DEFAULT_REGISTRY.invoke(
        "fundamental.stock_info", {"stock_code": "SH600000"}, ctx
    )

    assert result["ok"] is True
    assert result["data"]["code"] == "sh.600000"
    call = stores.tool_calls.list_tool_calls("run-stock-code")[0]
    assert call["params_json"] == {"stock_code": "sh.600000"}


def test_denied_tool_recorded_as_denied():
    session = sessionmaker(bind=_engine())()
    stores = create_stores(session)
    stores.runs.create_run(run_id="run-10", objective="权限测试")
    ctx = ToolContext(stores=stores, run_id="run-10")

    result = DEFAULT_REGISTRY.invoke(
        "backtest.run",
        {"strategy_name": "ma_cross", "stock_code": "sh.600000",
         "start_date": "2024-01-01", "end_date": "2024-01-12"},
        ctx,
    )
    assert result["ok"] is False
    calls = stores.tool_calls.list_tool_calls("run-10")
    assert calls[0]["status"] == "denied"
    session.close()
