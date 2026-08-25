"""Deterministic tool-admission policy for the native chat runtime.

The model remains responsible for wording the answer, but this policy decides
which tools are even visible for a turn.  That makes a greeting incapable of
creating a quant run, regardless of an occasional model tool-call mistake.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ToolScope(StrEnum):
    NONE = "none"
    READ = "read"
    ANALYSIS = "analysis"


_SOCIAL = re.compile(
    r"^(?:你好|您好|嗨|哈喽|hello|hi|hey|谢谢|感谢|拜拜|再见|晚安|早上好|下午好|晚上好)"
    r"[\s!！,.。?？~～]*$",
    re.IGNORECASE,
)
_CAPABILITY = re.compile(r"(?:你能做什么|你会什么|有什么功能|怎么使用|帮助|help|capabilit)", re.IGNORECASE)
_READ = re.compile(r"(?:查询|查看|获取|拉取|行情|k\s*线|kline|财报|基本面|快照|数据来源)", re.IGNORECASE)
_ANALYSIS = re.compile(
    r"(?:分析|研究|回测|策略|选股|预测|信号|ma[_ -]?cross|收益|风险|组合|优化|验证)",
    re.IGNORECASE,
)
_STOCK = re.compile(r"(?:\b(?:sh|sz|bj)\.\d{6}\b|\b\d{6}\b|上证|深证|创业板|科创板)", re.IGNORECASE)


@dataclass(frozen=True)
class ToolAdmission:
    scope: ToolScope
    reason: str

    @property
    def allow_analysis(self) -> bool:
        return self.scope is ToolScope.ANALYSIS


class TurnToolPolicy:
    """Decide the safe tool scope from the current turn and prior context."""

    def classify(self, message: str, history_text: str = "") -> ToolAdmission:
        text = message.strip()
        if not text or _SOCIAL.fullmatch(text) or _CAPABILITY.search(text):
            return ToolAdmission(ToolScope.NONE, "social_or_capability")

        combined = f"{history_text}\n{text}"
        has_stock = bool(_STOCK.search(combined))
        has_read_intent = bool(_READ.search(text))
        has_analysis_intent = bool(_ANALYSIS.search(text))

        if has_analysis_intent and has_stock:
            return ToolAdmission(ToolScope.ANALYSIS, "explicit_analysis_with_target")
        if has_read_intent and has_stock:
            return ToolAdmission(ToolScope.READ, "explicit_read_query")
        if has_analysis_intent:
            return ToolAdmission(ToolScope.NONE, "analysis_target_missing")
        return ToolAdmission(ToolScope.NONE, "general_conversation")


def stock_reference(text: str) -> str | None:
    """Return a normalized A-share reference when one is present."""

    match = re.search(r"\b(sh|sz|bj)\.(\d{6})\b", text, re.IGNORECASE)
    if match:
        return f"{match.group(1).lower()}.{match.group(2)}"
    match = re.search(r"\b(\d{6})\b", text)
    return match.group(1) if match else None
