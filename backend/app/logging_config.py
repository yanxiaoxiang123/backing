"""Structured JSON logging for the Backing backend.

* Emits single-line JSON records using only the standard library — no
  third-party dependency required.
* Carries ``request_id`` / ``job_id`` context via contextvars so every log
  line emitted inside a request or background job is correlated.
* Redacts sensitive keys and truncates oversized values: never log API keys,
  tokens, passwords, or full model inputs.

Usage::

    from app.logging_config import setup_logging, request_id_var, job_id_var

    setup_logging()
    token = request_id_var.set("abc123")
    logger.info("hello")            # -> {"level":"INFO","request_id":"abc123",...}
    request_id_var.reset(token)
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Context variables — inherited by every log record inside a request/job
# ---------------------------------------------------------------------------

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
job_id_var: ContextVar[str] = ContextVar("job_id", default="")

# Structured fields copied from record extras / contextvars into the JSON line.
_STRUCTURED_FIELDS = (
    "request_id",
    "job_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "provider",
    "job_type",
    "error_code",
    "retryable",
    "task_event",
)

# Keys whose values must never be logged verbatim (case-insensitive substring).
_SENSITIVE_SUBSTRINGS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
    "cookie",
    "credential",
    "private_key",
)

# Long values (e.g. full model inputs) are truncated to this many characters.
_MAX_VALUE_CHARS = 2000


def is_sensitive_key(key: str) -> bool:
    """Return True when *key* looks like a secret and must be masked."""
    lowered = key.lower()
    return any(sub in lowered for sub in _SENSITIVE_SUBSTRINGS)


def redact(obj: Any) -> Any:
    """Return a redacted deep copy of *obj*.

    Dict values whose key looks sensitive are masked with ``***``; strings
    longer than ``_MAX_VALUE_CHARS`` are truncated.
    """
    if isinstance(obj, dict):
        return {
            key: ("***" if is_sensitive_key(str(key)) else redact(value))
            for key, value in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [redact(value) for value in obj]
    if isinstance(obj, str):
        if len(obj) > _MAX_VALUE_CHARS:
            return obj[:_MAX_VALUE_CHARS] + f"...[truncated {len(obj) - _MAX_VALUE_CHARS} chars]"
        return obj
    return obj


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)

        # Extra fields attached by callers (logger.info("...", extra={...}))
        for key in _STRUCTURED_FIELDS:
            value = getattr(record, key, None)
            if value is not None and value != "":
                data[key] = value

        # contextvars fallback for request / job correlation
        rid = request_id_var.get()
        if rid and "request_id" not in data:
            data["request_id"] = rid
        jid = job_id_var.get()
        if jid and "job_id" not in data:
            data["job_id"] = jid

        return json.dumps(redact(data), ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root + uvicorn loggers with the JSON formatter on stdout.

    Call once at process start (``backend/main.py`` or the task worker entry).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    # Route uvicorn's own loggers through the same JSON handler so every
    # process log line stays machine-parseable.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        lg = logging.getLogger(name)
        lg.handlers[:] = [handler]
        lg.propagate = False
