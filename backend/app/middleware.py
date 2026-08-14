"""HTTP middleware: request correlation logging and CSRF protection.

* ``RequestLoggingMiddleware`` — request id (``X-Request-Id``) + one summary
  log line per request (method/path/status/duration_ms). 5xx tracebacks are
  logged only by the global exception handler — never duplicated here.
* ``CsrfMiddleware`` — double-submit CSRF protection for cookie-authenticated
  state-changing requests: when a session cookie is present, POST/PUT/PATCH/
  DELETE must carry an ``X-CSRF-Token`` header matching the ``csrf_token``
  cookie issued at login. Requests authenticated via the ``X-API-Key`` header
  (no session cookie) are unaffected.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging_config import request_id_var

logger = logging.getLogger("backing.request")

_SESSION_COOKIE = "session"
_CSRF_COOKIE = "csrf_token"
_CSRF_HEADER = "X-CSRF-Token"
_STATE_CHANGING = {"POST", "PUT", "PATCH", "DELETE"}


class CsrfMiddleware(BaseHTTPMiddleware):
    """Reject cookie-authenticated mutations without a matching CSRF token."""

    async def dispatch(self, request: Request, call_next):
        if (
            request.method in _STATE_CHANGING
            and _SESSION_COOKIE in request.cookies
        ):
            token = request.headers.get(_CSRF_HEADER, "")
            cookie_token = request.cookies.get(_CSRF_COOKIE, "")
            if not token or not cookie_token or token != cookie_token:
                logger.warning(
                    "csrf rejection: %s %s",
                    request.method,
                    request.url.path,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "csrf_failed",
                            "message": "CSRF token missing or invalid",
                        }
                    },
                )
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assign request ids and log one structured summary per request."""

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "http_request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            request_id_var.reset(token)
