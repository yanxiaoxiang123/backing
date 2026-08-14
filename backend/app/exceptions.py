"""Unified error classes for the Backing API.

All API routes should raise one of these (or a standard HTTPException) and the
global handlers in error_handlers.py will convert them to structured JSON
``{ "error": { "code", "message", ... } }`` responses.

External dependencies (stock data providers, LLM services, search APIs) must
raise ``ExternalServiceError`` subclasses so the client receives a stable
502/503 with a machine-readable code instead of a generic 500, and so the task
executor can decide whether the failure is retryable.
"""

from typing import Any

from fastapi import HTTPException, status


class AppError(HTTPException):
    """Base application error — all custom errors inherit from this."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error"
    error_code: str = "internal_error"
    retryable: bool = False

    def __init__(
        self,
        detail: str | None = None,
        error_code: str | None = None,
        headers: dict[str, str] | None = None,
        *,
        retryable: bool | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=self.status_code,
            detail=detail or self.detail,
            headers=headers,
        )
        self.error_code = error_code or self.error_code
        self.retryable = self.retryable if retryable is None else retryable
        self.extra = extra or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"
    error_code = "not_found"


class ValidationError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Validation failed"
    error_code = "validation_error"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource already exists"
    error_code = "conflict"


class ServiceError(AppError):
    """Backward-compatible alias: external service failure (502)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "External service error"
    error_code = "service_error"


class ExternalServiceError(AppError):
    """Base class for failures caused by an external dependency.

    ``provider`` names the dependency (e.g. ``baostock``, ``mootdx``,
    ``deepseek``, ``tavily``). Failures that may succeed on retry should pass
    ``retryable=True`` (default for the subclasses below).
    """

    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "External service error"
    error_code = "external_service_error"
    provider: str = "unknown"

    def __init__(
        self,
        detail: str | None = None,
        *,
        provider: str | None = None,
        error_code: str | None = None,
        retryable: bool | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            detail=detail,
            error_code=error_code,
            headers=headers,
            retryable=retryable,
            extra=extra,
        )
        if provider is not None:
            self.provider = provider


class ProviderUnavailableError(ExternalServiceError):
    """Dependency could not be reached (connection refused, DNS, no key)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Service unavailable"
    error_code = "provider_unavailable"
    retryable = True


class ProviderTimeoutError(ExternalServiceError):
    """Dependency did not answer within the timeout."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Service timed out"
    error_code = "provider_timeout"
    retryable = True
