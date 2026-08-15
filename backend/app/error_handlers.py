"""Global FastAPI exception handlers.

Registers structured JSON error responses for all exception types so the
frontend always receives ``{ "error": { "code": str, "message": str } }``.
5xx tracebacks are logged exactly once here (the request middleware logs only
a summary line), and external-dependency errors carry ``provider`` and
``retryable`` fields.
"""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions import AppError, ExternalServiceError
from app.logging_config import request_id_var

logger = logging.getLogger(__name__)


def _build_error_body(
    code: str,
    message: str,
    detail: str | list | dict | None = None,
    provider: str | None = None,
    retryable: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> dict:
    """Return a consistent ``{ "error": { "code", "message" } }`` body."""
    body: dict = {"error": {"code": code, "message": message}}
    if detail is not None:
        body["error"]["detail"] = detail
    if provider is not None:
        body["error"]["provider"] = provider
    if retryable is not None:
        body["error"]["retryable"] = retryable
    if extra:
        body["error"].update(extra)
    return body


def _log_warning(
    request: Request,
    status_code: int,
    message: str,
    *,
    code: str | None = None,
    provider: str | None = None,
) -> None:
    """Log a concise structured warning line for non-5xx errors."""
    logger.warning(
        "http_error: %s", message,
        extra={
            "request_id": request_id_var.get(),
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "error_code": code,
            "provider": provider,
        },
    )


def _log_error(
    request: Request,
    status_code: int,
    exc: Exception,
    *,
    code: str | None = None,
    provider: str | None = None,
) -> None:
    """Log a full traceback for 5xx errors (single place, no duplication)."""
    logger.error(
        "http_error: %s", str(exc) or exc.__class__.__name__,
        exc_info=exc,
        extra={
            "request_id": request_id_var.get(),
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "error_code": code,
            "provider": provider,
        },
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom AppError subclasses."""
    provider = getattr(exc, "provider", None)
    retryable = exc.retryable
    extra = getattr(exc, "extra", None)
    if exc.status_code >= 500:
        _log_error(
            request, exc.status_code, exc,
            code=exc.error_code, provider=provider,
        )
    else:
        _log_warning(
            request, exc.status_code, exc.detail,
            code=exc.error_code, provider=provider,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_body(
            code=exc.error_code,
            message=exc.detail,
            provider=provider if isinstance(exc, ExternalServiceError) else None,
            retryable=retryable if isinstance(exc, ExternalServiceError) else None,
            extra=extra if isinstance(exc, ExternalServiceError) else None,
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle vanilla HTTPException (including AuthError from auth.py)."""
    status_code = exc.status_code
    if status_code >= 500:
        _log_error(request, status_code, exc)
    else:
        _log_warning(request, status_code, str(exc.detail))

    # Map common status codes to short codes
    code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
    }
    return JSONResponse(
        status_code=status_code,
        content=_build_error_body(
            code=code_map.get(status_code, f"http_{status_code}"),
            message=str(exc.detail) if exc.detail else "HTTP error",
        ),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic request validation errors (422)."""
    errors = exc.errors()
    first_msg = errors[0]["msg"] if errors else "Request validation failed"
    _log_warning(request, 422, first_msg, code="validation_error")
    return JSONResponse(
        status_code=422,
        content=_build_error_body(
            code="validation_error",
            message=first_msg,
            detail=errors,
        ),
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Last-resort catch-all for anything that escaped the handlers above."""
    _log_error(request, 500, exc, code="internal_error")
    return JSONResponse(
        status_code=500,
        content=_build_error_body(
            code="internal_error",
            message="Internal server error",
        ),
    )


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_error_handlers(app: FastAPI) -> None:
    """Add all exception handlers to a FastAPI application instance.

    Call this once during app construction, e.g.::

        app = FastAPI(...)
        register_error_handlers(app)
    """
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    # The generic Exception handler must be registered LAST so it doesn't
    # shadow more specific handlers.
    app.add_exception_handler(Exception, unhandled_exception_handler)
