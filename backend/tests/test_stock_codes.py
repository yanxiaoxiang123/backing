from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.domain.stock_codes import (
    StockCodeError,
    canonicalize_stock_code_in_text,
    normalize_stock_code,
    stock_code_from_text,
)
from app.models.models import Stock


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.parametrize(
    "raw",
    ["sh.600000", "sh600000", "SH600000", "600000"],
)
def test_normalize_stock_code_supported_forms(raw):
    assert normalize_stock_code(raw) == "sh.600000"


def test_stock_code_text_extraction_without_leading_space():
    assert stock_code_from_text("分析一下sh600000") == "sh.600000"
    assert canonicalize_stock_code_in_text("分析一下SH600000") == "分析一下sh.600000"


def test_bare_code_prefers_unique_database_match(db):
    db.add(Stock(code="sh.000001", name="测试标的", market="sh"))
    db.commit()

    assert normalize_stock_code("000001", db=db) == "sh.000001"


def test_bare_code_rejects_ambiguous_database_match(db):
    db.add_all(
        [
            Stock(code="sh.123456", name="上海测试", market="sh"),
            Stock(code="sz.123456", name="深圳测试", market="sz"),
        ]
    )
    db.commit()

    with pytest.raises(StockCodeError, match="匹配多个市场"):
        normalize_stock_code("123456", db=db)


@pytest.mark.parametrize("raw", ["", "abc", "60000", "xx600000", "700000"])
def test_invalid_stock_codes_fail_clearly(raw):
    with pytest.raises(StockCodeError):
        normalize_stock_code(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("000001.sz", "sz.000001"),
        ("000001.SZ", "sz.000001"),
        ("600000.sh", "sh.600000"),
        ("430047.BJ", "bj.430047"),
        ("000001.sh", "sh.000001"),
        ("SH.000001", "sh.000001"),
    ],
)
def test_explicit_stock_forms_preserve_exchange_and_are_idempotent(raw, expected):
    assert normalize_stock_code(raw) == expected
    assert normalize_stock_code(normalize_stock_code(raw)) == expected


def test_suffix_extraction_consumes_full_reference_and_preserves_punctuation():
    assert canonicalize_stock_code_in_text("请分析000001.SZ，最近走势？") == "请分析sz.000001，最近走势？"
    assert stock_code_from_text("查询000001.sh。") == "sh.000001"


@pytest.mark.parametrize(
    "text",
    ["1234567", "abc000001", "foo_sz000001", "000001.xyz", "sz000001xyz", "000001_foo", "000001.sz.xyz"],
)
def test_text_extraction_rejects_partial_tokens(text):
    assert stock_code_from_text(text) is None
    assert canonicalize_stock_code_in_text(text) == text


def test_find_all_references_retains_full_spans_and_repeated_aliases():
    from app.domain import stock_codes

    text = "比较000001.sz和SH600000，以及sz.000001"
    refs = stock_codes.find_stock_references(text)
    assert [ref.code for ref in refs] == ["sz.000001", "sh.600000", "sz.000001"]
    assert [text[ref.start:ref.end] for ref in refs] == ["000001.sz", "SH600000", "sz.000001"]
