"""研究数据层测试（规格 v2 决策 17-18；切片 01）。

akshare/baostock 全部 mock；缓存命中/失效；证据五元组；失败路径显式报错。
"""

import pandas as pd
import pytest

from app.services import research_data
from app.services.baostock_service import baostock_service
from app.tools.base import ToolContext
from app.tools.registry import DEFAULT_REGISTRY

RESEARCH_TOOLS = (
    "event.news",
    "event.announcement",
    "fundamental.financials",
    "market.index_kline",
)


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """每个测试使用独立缓存库，避免串扰。"""
    monkeypatch.setattr(research_data, "_CACHE_DB", str(tmp_path / "cache.db"))
    yield


def _news_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "关键词": "业绩",
                "新闻标题": "标题A",
                "新闻内容": "内容A" * 200,
                "发布时间": "2026-08-14 09:00:00",
                "文章来源": "东方财富",
                "新闻链接": "http://example.com/a",
            }
        ]
    )


def _announcement_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "代码": "600000",
                "名称": "浦发银行",
                "公告标题": "定期报告",
                "公告类型": "年报",
                "公告日期": "2026-08-14",
                "网址": "http://example.com/n",
            }
        ]
    )


def _financial_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{"报告期": "20260331", "净利润": 100.0, "净利润同比增长率": 5.0}]
    )


def _index_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-08-14",
                "open": 4000.0,
                "high": 4010.0,
                "low": 3990.0,
                "close": 4005.0,
                "volume": 1,
                "amount": 2,
                "stock_code": "sh.000300",
            }
        ]
    )


def test_registry_exposes_read_tools():
    by_name = {t["name"]: t for t in DEFAULT_REGISTRY.list_tools()}
    for name in RESEARCH_TOOLS:
        assert name in by_name, f"缺少工具 {name}"
        assert by_name[name]["permission"] == "read", f"{name} 应为只读权限"


def test_news_fetch_envelope(monkeypatch):
    monkeypatch.setattr(research_data.ak, "stock_news_em", lambda symbol: _news_df())
    env = DEFAULT_REGISTRY.invoke(
        "event.news", {"stock_code": "sh.600000", "limit": 5}, ToolContext()
    )
    assert env["ok"] is True
    assert env["source_id"] == "news:600000"
    assert env["as_of"]
    assert env["data"]["vendor"] == "akshare"
    assert env["data"]["data_version"] == research_data.DATA_VERSION
    assert env["data"]["rows"] == 1


def test_news_cache_hit_avoids_refetch(monkeypatch):
    calls = {"n": 0}

    def fake(symbol):
        calls["n"] += 1
        return _news_df()

    monkeypatch.setattr(research_data.ak, "stock_news_em", fake)
    ctx = ToolContext()
    env1 = DEFAULT_REGISTRY.invoke(
        "event.news", {"stock_code": "sh.600000", "limit": 5}, ctx
    )
    env2 = DEFAULT_REGISTRY.invoke(
        "event.news", {"stock_code": "sh.600000", "limit": 5}, ctx
    )
    assert env1["ok"] is True and env2["ok"] is True
    assert calls["n"] == 1, "缓存命中不应再次外呼"
    assert env1["data"]["news"] == env2["data"]["news"]


def test_news_failure_is_explicit(monkeypatch):
    def boom(symbol):
        raise RuntimeError("network down")

    monkeypatch.setattr(research_data.ak, "stock_news_em", boom)
    env = DEFAULT_REGISTRY.invoke(
        "event.news", {"stock_code": "600000"}, ToolContext()
    )
    assert env["ok"] is False
    assert env["error"]["code"] == "handler"
    assert "network down" in env["error"]["message"]


def test_announcement_tool(monkeypatch):
    monkeypatch.setattr(
        research_data.ak,
        "stock_notice_report",
        lambda symbol, date: _announcement_df(),
    )
    env = DEFAULT_REGISTRY.invoke(
        "event.announcement",
        {"stock_code": "sh.600000", "date": "2026-08-14"},
        ToolContext(),
    )
    assert env["ok"] is True
    assert env["source_id"] == "notice:600000:2026-08-14"
    assert env["data"]["rows"] == 1


def test_financials_tool(monkeypatch):
    monkeypatch.setattr(
        research_data.ak, "stock_financial_abstract", lambda symbol: _financial_df()
    )
    env = DEFAULT_REGISTRY.invoke(
        "fundamental.financials",
        {"stock_code": "sh.600000", "periods": 3},
        ToolContext(),
    )
    assert env["ok"] is True
    assert env["data"]["vendor"] == "akshare"
    assert env["data"]["rows"] == 1


def test_index_kline_tool(monkeypatch):
    monkeypatch.setattr(
        baostock_service,
        "get_index_daily_kline",
        lambda code, s, e: _index_df(),
    )
    env = DEFAULT_REGISTRY.invoke(
        "market.index_kline",
        {"index_code": "sh.000300", "start_date": "2026-08-01", "end_date": "2026-08-14"},
        ToolContext(),
    )
    assert env["ok"] is True
    assert env["data"]["rows"] == 1
    assert env["data"]["index_code"] == "sh.000300"


def test_validation_rejects_empty_code():
    env = DEFAULT_REGISTRY.invoke("event.news", {"stock_code": ""}, ToolContext())
    assert env["ok"] is False
    assert env["error"]["code"] == "validation"


def test_normalize_code():
    assert research_data._normalize_code("sh.600000") == "600000"
    assert research_data._normalize_code("600000") == "600000"
    assert research_data._normalize_code("sz.000001") == "000001"
