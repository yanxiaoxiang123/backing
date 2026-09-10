"""A-share stock-code parsing and canonicalization.

The canonical form used by the database and deterministic tools is
``sh.600000`` (exchange, dot, six digits).  User-facing boundaries also accept
compact and bare forms such as ``SH600000`` and ``600000``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class StockCodeError(ValueError):
    """Raised when a value cannot be resolved to one A-share stock code."""


@dataclass(frozen=True)
class StockReference:
    """A stock-code occurrence extracted from free text."""

    code: str
    start: int
    end: int


_EXPLICIT_CODE = re.compile(r"^(sh|sz|bj)\.?([0-9]{6})$", re.IGNORECASE)
_BARE_CODE = re.compile(r"^[0-9]{6}$")
_TEXT_CODE = re.compile(
    r"(?<![A-Za-z0-9_])(?:(?:sh|sz|bj)\.?[0-9]{6}|[0-9]{6})(?![0-9])",
    re.IGNORECASE,
)


def _database_match(digits: str, db: Any | None) -> str | None:
    if db is None:
        return None

    from app.models.models import Stock

    matches = (
        db.query(Stock.code)
        .filter(Stock.code.like(f"%.{digits}"))
        .limit(2)
        .all()
    )
    codes = [str(row[0]) for row in matches]
    if len(codes) > 1:
        raise StockCodeError(f"股票代码 {digits} 匹配多个市场，请提供交易所前缀")
    return codes[0].lower() if codes else None


def _infer_exchange(digits: str) -> str:
    if digits.startswith(("5", "6", "9")):
        return "sh"
    if digits.startswith(("4", "8")):
        return "bj"
    if digits.startswith(("0", "1", "2", "3")):
        return "sz"
    raise StockCodeError(f"无法从裸代码 {digits} 判断交易所，请提供 sh/sz/bj 前缀")


def normalize_stock_code(value: str, *, db: Any | None = None) -> str:
    """Return one stock code in canonical ``exchange.######`` form."""

    raw = str(value or "").strip()
    if not raw:
        raise StockCodeError("股票代码不能为空")

    explicit = _EXPLICIT_CODE.fullmatch(raw)
    if explicit:
        return f"{explicit.group(1).lower()}.{explicit.group(2)}"
    if not _BARE_CODE.fullmatch(raw):
        raise StockCodeError(
            f"无法解析股票代码 {value!r}，请使用 sh.600000、sh600000 或 600000"
        )

    database_code = _database_match(raw, db)
    if database_code:
        return database_code
    return f"{_infer_exchange(raw)}.{raw}"


def find_stock_reference(text: str, *, db: Any | None = None) -> StockReference | None:
    """Find and normalize the first A-share stock code in free text."""

    match = _TEXT_CODE.search(text or "")
    if match is None:
        return None
    return StockReference(
        code=normalize_stock_code(match.group(0), db=db),
        start=match.start(),
        end=match.end(),
    )


def stock_code_from_text(text: str, *, db: Any | None = None) -> str | None:
    """Return the first normalized stock code in text, if present."""

    reference = find_stock_reference(text, db=db)
    return reference.code if reference else None


def canonicalize_stock_code_in_text(text: str, *, db: Any | None = None) -> str:
    """Replace the first stock-code occurrence in text with canonical form."""

    reference = find_stock_reference(text, db=db)
    if reference is None:
        return text
    return f"{text[:reference.start]}{reference.code}{text[reference.end:]}"
