from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.models import Stock
from app.tools.base import ToolContext
from app.tools.registry import DEFAULT_REGISTRY


@pytest.fixture()
def context():
    engine = create_engine("sqlite://")
    Stock.__table__.create(engine)
    with Session(engine) as session:
        session.add_all([
            Stock(code="sz.000001", name="平安银行", market="sz"),
            Stock(code="sh.600000", name="浦发银行", market="sh"),
            Stock(code="sh.600001", name="平安银行测试", market="sh"),
            Stock(code="sh.600002", name="含%符号", market="sh"),
            Stock(code="sh.600003", name="含_符号", market="sh"),
        ])
        session.commit()
        yield ToolContext(db=session, as_of=datetime(2026, 10, 30, tzinfo=timezone.utc))
    engine.dispose()


def search(context, query, limit=10):
    return DEFAULT_REGISTRY.invoke("market.search", {"query": query, "limit": limit}, context)


@pytest.mark.parametrize("query", ["000001.sz", "SZ000001", "sz.000001", "000001"])
def test_code_search_returns_canonical_identity(context, query):
    result = search(context, query)
    assert result["ok"] is True
    assert result["data"]["matches"] == [{"code": "sz.000001", "name": "平安银行", "market": "sz"}]
    assert result["source_id"]
    assert result["as_of"]


def test_exact_name_short_circuits_contains_matches(context):
    result = search(context, " 平安银行 ")["data"]
    assert result["query"] == "平安银行"
    assert result["total"] == 1
    assert result["matches"][0]["code"] == "sz.000001"
    assert result["truncated"] is False


def test_contains_search_orders_and_reports_true_total(context):
    result = search(context, "银行", limit=1)["data"]
    assert result["total"] == 3
    assert result["truncated"] is True
    assert [row["code"] for row in result["matches"]] == ["sh.600000"]


@pytest.mark.parametrize(("query", "expected"), [("%", "sh.600002"), ("_", "sh.600003")])
def test_search_treats_like_wildcards_literally(context, query, expected):
    result = search(context, query)["data"]
    assert result["total"] == 1
    assert result["matches"][0]["code"] == expected


@pytest.mark.parametrize("query", ["不存在", "000001.sh", "000001.xyz"])
def test_unknown_queries_do_not_return_other_stock(context, query):
    result = search(context, query)["data"]
    assert result["matches"] == []
    assert result["total"] == 0
    assert result["truncated"] is False


@pytest.mark.parametrize("params", [{"query": " "}, {"query": "x" * 101}, {"query": "银行", "limit": 0}, {"query": "银行", "limit": 21}])
def test_search_validates_bounded_inputs(context, params):
    result = DEFAULT_REGISTRY.invoke("market.search", params, context)
    assert result["ok"] is False
    assert result["error"]["code"] == "validation"


def test_search_requires_read_permission(context):
    context.granted_permissions = set()
    result = search(context, "银行")
    assert result["ok"] is False
    assert result["error"]["code"] == "permission_denied"
