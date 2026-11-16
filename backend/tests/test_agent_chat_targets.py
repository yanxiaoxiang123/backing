"""Deterministic target resolution: no model, providers or network."""

import pytest

from app.agent_chat.targets import resolve_target


STOCKS = {
    "sz.000001": {"code": "sz.000001", "name": "平安银行"},
    "sh.600000": {"code": "sh.600000", "name": "浦发银行"},
}


def invoke(name, params):
    if name == "fundamental.stock_info":
        row = STOCKS.get(params["stock_code"])
        return {"ok": bool(row), "data": row, "error": {"message": "未找到股票"}}
    query = params["query"]
    matches = [row for row in STOCKS.values() if query in row["name"]]
    return {"ok": True, "data": {"matches": matches, "total": len(matches), "truncated": False}}


@pytest.mark.parametrize("text", ["000001.sz", "查询000001.sz", "分析000001.SZ"])
def test_suffix_resolves_verified_stock(text):
    result = resolve_target(text, None, None, invoke)
    assert result.stock_code == "sz.000001"
    assert result.explicit is True
    assert result.message is None


@pytest.mark.parametrize("text", ["平安银行", "搜索平安银行", "分析平安银行", "查看平安银行财报"])
def test_unique_name_resolves(text):
    assert resolve_target(text, None, None, invoke).stock_code == "sz.000001"


@pytest.mark.parametrize("text", ["查询不存在银行", "000001.xyz", "000001.sh", "1234567"])
def test_bad_new_target_does_not_reuse_previous(text):
    result = resolve_target(text, "sz.000001", None, invoke)
    assert result.stock_code is None
    assert result.message
    assert result.explicit is True


@pytest.mark.parametrize("text", ["最近有什么新闻", "看一下财报", "分析一下", "回测均线策略"])
def test_followup_uses_previous_target(text):
    result = resolve_target(text, "sh.600000", None, invoke)
    assert result.stock_code == "sh.600000"
    assert result.explicit is False


@pytest.mark.parametrize("text", ["看看最近怎么样", "它最近表现如何", "这只股票最近如何"])
def test_chatty_followup_is_not_treated_as_stock_name(text):
    result = resolve_target(text, "sh.600000", None, invoke)
    assert result.stock_code == "sh.600000"
    assert result.message is None


def test_chatty_text_without_history_asks_instead_of_claiming_missing_name():
    calls = []

    def recording(name, params):
        calls.append(name)
        return invoke(name, params)

    for text in ("研究助手你好", "帮我分析一下最近的市场"):
        result = resolve_target(text, None, None, recording)
        assert result.stock_code is None
        assert result.message is not None
        assert "未找到" not in result.message
    assert "market.search" not in calls


def test_multiple_codes_require_choice():
    result = resolve_target("比较000001.sz与600000.sh", "sz.000001", None, invoke)
    assert result.stock_code is None
    assert "选择" in result.message


def test_same_code_aliases_are_one_target():
    assert resolve_target("查询000001.sz（sz000001）", None, None, invoke).stock_code == "sz.000001"


def test_context_requires_verified_stock_entity():
    assert resolve_target("查看财报", None, {"entity_type": "stock", "entity_id": "000001.sz"}, invoke).stock_code == "sz.000001"
    assert resolve_target("查看财报", None, {"entity_type": "page", "entity_id": "000001.sz"}, invoke).stock_code is None
    assert resolve_target("查看财报", None, {"entity_type": "stock", "entity_id": "000001.sh"}, invoke).stock_code is None


def test_truncated_single_match_is_not_unique():
    def truncated(name, params):
        return {"ok": True, "data": {"matches": [STOCKS["sz.000001"]], "total": 2, "truncated": True}}

    result = resolve_target("搜索银行", "sh.600000", None, truncated)
    assert result.stock_code is None
    assert "选择" in result.message


def test_unknown_name_and_comparison_do_not_fall_back():
    assert resolve_target("比较平安银行和浦发银行", "sz.000001", None, invoke).stock_code is None
    assert resolve_target("查询不存在银行", "sz.000001", None, invoke).stock_code is None
