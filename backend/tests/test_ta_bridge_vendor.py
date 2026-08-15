"""TradingAgents gateway vendor 测试（规格 v2 决策 19-20；US-2.7）。

覆盖：gateway 注册与配置切换、方法经网关路由、未接入方法显式失败
（不回退直连）、代码归一化、无 run 上下文报错。
"""

import pytest
from tradingagents.dataflows import interface as ta_interface
from tradingagents.dataflows.config import get_config

from app.agent_runtime.ta_bridge import vendor
from app.tools.base import ToolContext


@pytest.fixture(autouse=True)
def _installed():
    vendor.install_gateway_vendor()
    yield
    vendor.clear_gateway_context()


def _fake_env(tool):
    def fake_invoke(name, params, context):
        assert name == tool
        return {
            "ok": True,
            "tool": name,
            "source_id": f"{tool}:test",
            "as_of": "2026-08-14T00:00:00+00:00",
            "vendor": "backend",
            "data": {
                "source_id": f"{tool}:test",
                "as_of": "2026-08-14T00:00:00+00:00",
                "vendor": "backend",
                "data_version": "1.0.0",
                "stock_code": params.get("stock_code"),
                "rows": 1,
                "kline": [{"date": "2026-08-14", "close": 10.0}],
            },
        }

    return fake_invoke


class TestInstall:
    def test_gateway_registered_and_configured(self):
        assert "gateway" in ta_interface.VENDOR_METHODS["get_stock_data"]
        assert "gateway" in ta_interface.VENDOR_METHODS["get_balance_sheet"]
        config = get_config()
        for category in ta_interface.TOOLS_CATEGORIES:
            assert config["data_vendors"][category] == "gateway"

    def test_install_is_idempotent(self):
        vendor.install_gateway_vendor()
        vendor.install_gateway_vendor()
        assert "gateway" in ta_interface.VENDOR_METHODS["get_stock_data"]


class TestRouting:
    def test_get_stock_data_routes_through_gateway(self, monkeypatch):
        captured = {}

        def fake_invoke(name, params, context):
            captured["name"] = name
            captured["params"] = params
            return _fake_env("market.kline")(name, params, context)

        monkeypatch.setattr(vendor.DEFAULT_REGISTRY, "invoke", fake_invoke)
        vendor.set_gateway_context(ToolContext())
        result = ta_interface.route_to_vendor(
            "get_stock_data", "sh.600000", "2026-01-01", "2026-08-14"
        )
        assert captured["name"] == "market.kline"
        assert captured["params"]["stock_code"] == "sh.600000"
        assert captured["params"]["start_date"] == "2026-01-01"
        assert "market.kline" in result
        assert "sh.600000" in result

    def test_news_routes_through_gateway(self, monkeypatch):
        captured = {}

        def fake_invoke(name, params, context):
            captured["params"] = params
            return _fake_env("event.news")(name, params, context)

        monkeypatch.setattr(vendor.DEFAULT_REGISTRY, "invoke", fake_invoke)
        vendor.set_gateway_context(ToolContext())
        ta_interface.route_to_vendor("get_news", "600000", "2026-08-01", "2026-08-14")
        assert captured["params"]["stock_code"] == "sh.600000"

    def test_unconnected_method_fails_explicitly(self):
        vendor.set_gateway_context(ToolContext())
        with pytest.raises(ValueError, match="未接入"):
            ta_interface.route_to_vendor("get_balance_sheet", "600000")

    def test_missing_context_raises(self):
        vendor.clear_gateway_context()
        with pytest.raises(ValueError, match="未初始化"):
            ta_interface.route_to_vendor("get_stock_data", "600000", "a", "b")


class TestNormalizeCode:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("sh.600000", "sh.600000"),
            ("600000", "sh.600000"),
            ("SH600000", "sh.600000"),
            ("000001", "sz.000001"),
            ("300750", "sz.300750"),
            ("688017", "sh.688017"),
            ("bj.830799", "bj.830799"),
            ("830799", "bj.830799"),
        ],
    )
    def test_normalize(self, raw, expected):
        assert vendor.normalize_code(raw) == expected
