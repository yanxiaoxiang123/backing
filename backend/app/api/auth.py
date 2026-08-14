"""认证端点：登录换取短期 HttpOnly session、登出、会话探测。

API key 只在登录时经一次 POST 提交，随后被丢弃——浏览器 bundle 不包含
任何密钥（前端没有 VITE_API_KEY）；后续请求只携带 HttpOnly session cookie，
状态变更请求再携带 csrf_token cookie（double-submit，见 CsrfMiddleware）。
"""

import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth import validate_api_key
from app.config import settings
from app.limiter import limiter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

SESSION_COOKIE = "session"
CSRF_COOKIE = "csrf_token"


@router.post("/session")
@limiter.limit("10/minute")
async def create_session(request: Request) -> JSONResponse:
    """Exchange an API key for a short-lived HTTP-only session cookie.

    Rate-limited (10/minute) to slow down brute force. Issues a CSRF token
    cookie (non-HttpOnly, read by the frontend) alongside the session cookie
    for the double-submit CSRF check on cookie-authenticated mutations.
    """
    body = await request.json()
    validate_api_key(body.get("api_key", ""))
    request.session["authenticated"] = True
    csrf_token = secrets.token_hex(32)
    response = JSONResponse({"success": True})
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
