"""账号 + 密码登录：真实用户表校验、旧 API Key 兼容、会话主体。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.config import Base, get_db, settings
from app.error_handlers import register_error_handlers
from app.limiter import limiter
from app.middleware import CsrfMiddleware
from app.models.models import User
from app.passwords import hash_password


@pytest.fixture(autouse=True)
def _reset_limiter():
    yield
    limiter.reset()


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = factory()
    db.add(
        User(username="analyst", password_hash=hash_password("correct-horse"))
    )
    db.commit()
    db.close()
    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    app = FastAPI()
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret",
        max_age=3600,
        same_site="lax",
        https_only=False,
    )
    app.add_middleware(CsrfMiddleware)
    app.include_router(auth_router)
    register_error_handlers(app)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    original_key = settings.API_KEY
    settings.API_KEY = "legacy-api-key"
    yield TestClient(app, raise_server_exceptions=False)
    settings.API_KEY = original_key
    app.dependency_overrides.clear()


class TestCredentialLogin:
    def test_login_with_username_and_password(self, client):
        resp = client.post(
            "/api/v1/auth/session",
            json={"username": "analyst", "password": "correct-horse"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert client.get("/api/v1/auth/me").status_code == 200

    def test_rejects_wrong_password(self, client):
        resp = client.post(
            "/api/v1/auth/session",
            json={"username": "analyst", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_rejects_unknown_user_with_same_error(self, client):
        unknown = client.post(
            "/api/v1/auth/session",
            json={"username": "nobody", "password": "correct-horse"},
        )
        wrong = client.post(
            "/api/v1/auth/session",
            json={"username": "analyst", "password": "wrong"},
        )
        assert unknown.status_code == 401
        assert wrong.status_code == 401
        # 同样的错误文案：不泄露账号是否存在
        assert unknown.json() == wrong.json()

    def test_rejects_blank_credentials(self, client):
        resp = client.post(
            "/api/v1/auth/session", json={"username": "", "password": ""}
        )
        assert resp.status_code == 401

    def test_replaces_existing_session_on_login(self, client):
        client.post("/api/v1/auth/session", json={"api_key": "legacy-api-key"})
        resp = client.post(
            "/api/v1/auth/session",
            json={"username": "analyst", "password": "correct-horse"},
        )
        assert resp.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 200


class TestLegacyApiKeyLogin:
    def test_api_key_still_works(self, client):
        resp = client.post(
            "/api/v1/auth/session", json={"api_key": "legacy-api-key"}
        )
        assert resp.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 200

    def test_invalid_api_key_rejected(self, client):
        resp = client.post("/api/v1/auth/session", json={"api_key": "nope"})
        assert resp.status_code == 401
