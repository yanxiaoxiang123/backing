"""会话认证与 CSRF 测试：登录换 HttpOnly cookie、me/logout、double-submit
CSRF 防护、登录限流、生产默认密钥守卫。
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.config import (
    DEV_SESSION_SECRET,
    Settings,
    assert_safe_production_settings,
    settings,
)
from app.error_handlers import register_error_handlers
from app.limiter import limiter
from app.middleware import CsrfMiddleware


@pytest.fixture(autouse=True)
def _reset_limiter():
    """每个测试后重置共享限流计数，避免限流测试污染后续用例。"""
    yield
    limiter.reset()


@pytest.fixture()
def client():
    """Mini app：真实 auth 路由 + 与生产一致的中间件栈。"""
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

    @app.post("/protected")
    def protected(request: Request) -> JSONResponse:
        """会话认证下的状态变更端点（CSRF 校验目标）。"""
        return JSONResponse({"ok": True})

    @app.get("/session-only")
    def session_only(request: Request) -> JSONResponse:
        return JSONResponse({"session": request.session.get("authenticated")})

    original_key = settings.API_KEY
    original_samesite = settings.SESSION_SAMESITE
    settings.API_KEY = "test-secret"
    settings.SESSION_SAMESITE = "lax"
    yield TestClient(app, raise_server_exceptions=False)
    settings.API_KEY = original_key
    settings.SESSION_SAMESITE = original_samesite


class TestLoginFlow:
    def test_login_sets_session_and_csrf_cookies(self, client):
        resp = client.post("/api/v1/auth/session", json={"api_key": "test-secret"})
        assert resp.status_code == 200
        cookies = {c.name: c for c in resp.cookies.jar}
        assert "session" in cookies
        assert "csrf_token" in cookies
        set_cookie = resp.headers.get("set-cookie", "").lower()
        # session cookie 为 HttpOnly；csrf_token cookie 必须可被 JS 读取（非 HttpOnly）
        session_part = set_cookie.split("session=")[-1]
        assert "httponly" in session_part
        csrf_part = set_cookie.split("csrf_token=")[0]
        assert "httponly" not in csrf_part

    def test_login_rejects_invalid_key(self, client):
        resp = client.post("/api/v1/auth/session", json={"api_key": "wrong"})
        assert resp.status_code == 401

    def test_login_rate_limited(self, client):
        """登录限流：10/minute 后 429。"""
        for _ in range(10):
            client.post("/api/v1/auth/session", json={"api_key": "bad"})
        resp = client.post("/api/v1/auth/session", json={"api_key": "bad"})
        assert resp.status_code == 429

    def test_me_requires_session(self, client):
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_me_after_login(self, client):
        client.post("/api/v1/auth/session", json={"api_key": "test-secret"})
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": True}

    def test_login_can_replace_stale_session_without_csrf(self, client):
        """旧会话残留时，用户仍能重新登录而不会被旧 CSRF 状态锁死。"""
        first = client.post("/api/v1/auth/session", json={"api_key": "test-secret"})
        assert first.status_code == 200
        client.cookies.set("csrf_token", "stale-token")
        resp = client.post("/api/v1/auth/session", json={"api_key": "test-secret"})
        assert resp.status_code == 200

    def test_logout_clears_session(self, client):
        login = client.post("/api/v1/auth/session", json={"api_key": "test-secret"})
        token = login.cookies.get("csrf_token")
        assert client.get("/api/v1/auth/me").status_code == 200
        resp = client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": token}
        )
        assert resp.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401


class TestCsrf:
    def test_mutation_without_csrf_token_rejected(self, client):
        client.post("/api/v1/auth/session", json={"api_key": "test-secret"})
        resp = client.post("/protected")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "csrf_failed"

    def test_mutation_with_wrong_csrf_token_rejected(self, client):
        client.post("/api/v1/auth/session", json={"api_key": "test-secret"})
        resp = client.post("/protected", headers={"X-CSRF-Token": "wrong"})
        assert resp.status_code == 403

    def test_mutation_with_matching_csrf_token_allowed(self, client):
        login = client.post("/api/v1/auth/session", json={"api_key": "test-secret"})
        token = login.cookies.get("csrf_token")
        resp = client.post("/protected", headers={"X-CSRF-Token": token})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_get_requests_not_csrf_checked(self, client):
        client.post("/api/v1/auth/session", json={"api_key": "test-secret"})
        assert client.get("/session-only").status_code == 200

    def test_header_auth_without_session_not_csrf_checked(self, client):
        """X-API-Key 认证（无 session cookie）不受 CSRF 限制。"""
        resp = client.post("/protected")
        # 无 session cookie → 中间件放行（认证由路由层处理）
        assert resp.status_code != 403


class TestProductionGuard:
    def test_default_secret_refused_in_production(self):
        s = Settings(
            _env_file=None,
            APP_ENV="production",
            API_KEY=None,
            SESSION_SECRET=None,
        )
        with pytest.raises(RuntimeError, match="SESSION_SECRET"):
            assert_safe_production_settings(s)

    def test_https_only_required_in_production(self):
        s = Settings(
            _env_file=None,
            APP_ENV="production",
            SESSION_SECRET="real-secret",
            SESSION_HTTPS_ONLY=False,
        )
        with pytest.raises(RuntimeError, match="SESSION_HTTPS_ONLY"):
            assert_safe_production_settings(s)

    def test_secure_production_settings_pass(self):
        s = Settings(
            _env_file=None,
            APP_ENV="production",
            SESSION_SECRET="real-secret",
            SESSION_HTTPS_ONLY=True,
        )
        assert_safe_production_settings(s)  # 不抛错

    def test_development_never_blocked(self):
        s = Settings(_env_file=None, APP_ENV="development")
        assert_safe_production_settings(s)

    def test_dev_secret_constant_is_stable(self):
        assert DEV_SESSION_SECRET == "dev-session-secret-do-not-use-in-prod"
