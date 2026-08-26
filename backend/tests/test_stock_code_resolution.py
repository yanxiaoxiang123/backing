from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes import _resolve_stock_code
from app.models.models import Stock


@pytest.fixture
def stock_session():
    engine = create_engine("sqlite:///:memory:")
    Stock.__table__.create(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Stock(code="sh.600036", name="招商银行", market="sh"),
                Stock(code="sz.000001", name="平安银行", market="sz"),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


def test_resolves_legacy_six_digit_code(stock_session: Session):
    assert _resolve_stock_code(stock_session, "600036") == "sh.600036"


def test_preserves_canonical_code(stock_session: Session):
    assert _resolve_stock_code(stock_session, "SZ.000001") == "sz.000001"


def test_unknown_six_digit_code_returns_not_found(stock_session: Session):
    with pytest.raises(HTTPException) as exc_info:
        _resolve_stock_code(stock_session, "999999")

    assert exc_info.value.status_code == 404
