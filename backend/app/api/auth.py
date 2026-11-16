"""认证端点：登录换取短期 HttpOnly session、登出、会话探测。

登录支持两种凭证：
1. 账号 + 密码（浏览器登录页使用，校验 users 表中的 PBKDF2 哈希）
2. API Key（旧客户端 / 脚本兼容；前端 bundle 中不含任何密钥）

凭证只在登录请求中出现一次，随后即被丢弃；后续请求只携带 HttpOnly
session cookie，状态变更请求再携带 csrf_token cookie（double-submit，
见 CsrfMiddleware）。
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import AuthError, authenticate_user, validate_api_key
from app.config import get_db, settings
from app.limiter import limiter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

SESSION_COOKIE = "session"
CSRF_COOKIE = "csrf_token"


class SessionRequest(BaseModel):
    """登录请求体。账号密码优先，未提供时回退到 API Key。"""

    username: str | None = None
    password: str | None = None
    api_key: str | None = None


def _resolve_principal(db: Session, body: SessionRequest) -> str:
    """Return the authenticated principal name for the session."""
    if body.username is not None or body.password is not None:
        username = (body.username or "").strip()
        password = body.password or ""
        if not username or not password:
            raise AuthError("Invalid username or password")
        return authenticate_user(db, username, password).username

    validate_api_key(body.api_key or "")
    return "session_user"


@router.post("/session")
@limiter.limit("10/minute")
async def create_session(
    request: Request,
    body: SessionRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Exchange credentials for a short-lived HTTP-only session cookie.

    Rate-limited (10/minute) to slow down brute force. Issues a CSRF token
    cookie (non-HttpOnly, read by the frontend) alongside the session cookie
    for the double-submit CSRF check on cookie-authenticated mutations.
    """
    principal = _resolve_principal(db, body)
    # 清空旧会话再写入，防止 session fixation。
    request.session.clear()
    request.session["authenticated"] = True
    request.session["username"] = principal
    csrf_token = secrets.token_hex(32)
    response = JSONResponse({"success": True, "username": principal})
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        samesite=settings.SESSION_SAMESITE,
        secure=settings.SESSION_HTTPS_ONLY,
        max_age=settings.SESSION_MAX_AGE_S,
    )
    return response


@router.post("/logout")
def logout_session(request: Request) -> JSONResponse:
    """Clear the session and CSRF cookies."""
    request.session.clear()
    response = JSONResponse({"success": True})
    response.delete_cookie(SESSION_COOKIE, samesite=settings.SESSION_SAMESITE)
    response.delete_cookie(CSRF_COOKIE, samesite=settings.SESSION_SAMESITE)
    return response


@router.get("/me")
def auth_status(request: Request) -> JSONResponse:
    """Return whether the current request carries a valid session."""
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return JSONResponse({"authenticated": True})
