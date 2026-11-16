from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.models.models import DailyKline, Stock
from app.services.data_quality import coverage_report


def test_missing_and_invalid_bars_are_visible():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add_all([Stock(code="sh.600000", name="A", market="sh"),
                    Stock(code="sz.000001", name="B", market="sz")])
        db.flush()
        db.add(DailyKline(stock_code="sh.600000", date=date(2024, 1, 2),
                          open=10, high=9, low=8, close=10, volume=1000))
        db.commit()
        report = coverage_report(db, limit=1)
        assert report["coverage_pct"] == 50
        assert report["missing_stocks"] == 1
        assert report["invalid_bars"] == 1
        assert report["items"][0]["stock_code"] == "sz.000001"
        assert report["calendar_verified"] is False
    engine.dispose()


def test_empty_database_has_finite_coverage():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        assert coverage_report(db)["coverage_pct"] == 0
    engine.dispose()


def test_quality_endpoint_requires_authentication(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.sessions import SessionMiddleware

    from app.api.data_quality import router
    from app.config import settings

    monkeypatch.setattr(settings, "API_KEY", "expected")
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-only")
    app.include_router(router)
    assert TestClient(app).get("/api/v1/data/quality").status_code == 401
