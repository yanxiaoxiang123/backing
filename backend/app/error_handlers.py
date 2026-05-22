"""Global FastAPI exception handlers.

Registers structured JSON error responses for all exception types so the
frontend always receives ``{ "error": { "code": str, "message": str } }``.
"""

import logging
from typing import Union

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions import AppError

logger = logging.getLogger(__name__)


def _build_error_body(
    code: str,
    message: str,
    detail: Union[str, list, dict, None] = None,
) -> dict:
    """Return a consistent ``{ "error": { "code", "message" } }`` body."""
    body: dict = {"error": {"code": code, "message": message}}
    if detail is not None:
        body["error"]["detail"] = detail
    return body


async def _log_warning(request: Request, status_code: int, message: str) -> None:
    """Log a concise warning line for non‑5xx errors."""
    logger.warning(
        "%s %s -> %d: %s", request.method, request.url.path, status_code, message
    )


async def _log_error(request: Request, status_code: int, exc: Exception) -> None:
    """Log a full traceback for 5xx errors."""
    logger.error(
        "%s %s -> %d", request.method, request.url.path, status_code, exc_info=exc
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom AppError subclasses."""
    await _log_warning(request, exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_body(
            code=exc.error_code,
            message=exc.detail,
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle vanilla HTTPException (including AuthError from auth.py)."""
    status_code = exc.status_code
    if status_code >= 500:
        await _log_error(request, status_code, exc)
    else:
        await _log_warning(request, status_code, str(exc.detail))

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
    await _log_warning(request, 422, first_msg)
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
    """Last‑resort catch‑all for anything that escaped the handlers above."""
    await _log_error(request, 500, exc)
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