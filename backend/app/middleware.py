"""HTTP middleware: request ID correlation and per-request duration logging.

Every HTTP request gets a short request id (exposed via the ``X-Request-Id``
response header) and emits exactly one summary log line carrying method,
path, status code and duration. 5xx tracebacks are logged only by the global
exception handler (``app/error_handlers.py``) — never duplicated here.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging_config import request_id_var

logger = logging.getLogger("backing.request")


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
