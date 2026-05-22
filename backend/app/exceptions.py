"""Unified error classes for the Backing API.

All API routes should raise one of these (or a standard HTTPException) and the
global handlers in error_handlers.py will convert them to structured JSON.
"""

from fastapi import HTTPException, status
from typing import Any, Optional


class AppError(HTTPException):
    """Base application error — all custom errors inherit from this."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error"
    error_code: str = "internal_error"

    def __init__(
        self,
        detail: Optional[str] = None,
        error_code: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(
            status_code=self.status_code,
            detail=detail or self.detail,
            headers=headers,
        )
        self.error_code = error_code or self.error_code


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
    """External service failure (baostock, mootdx, etc.)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "External service error"
    error_code = "service_error"