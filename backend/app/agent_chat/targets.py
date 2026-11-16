"""Resolve conversational stock targets through the typed gateway only."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from app.domain.stock_codes import StockCodeError, find_stock_references, normalize_stock_code

Invoke = Callable[[str, dict[str, Any]], dict[str, Any]]
_COMPARE = re.compile(r"比较|对比|分别|哪[只个].*更|vs\.?", re.IGNORECASE)
_CODE_LIKE = re.compile(r"[A-Za-z]*\.?[0-9]{5,}|[0-9]+\.[A-Za-z]+")
_INTENT = re.compile(r"查询|搜索|查找|查看|获取|拉取|分析|研究|回测|预测|优化|看看|看|帮我|请|一下|最近|近期|今天|有什么|哪些|的|这只|该股|它|股票|一只|个股|行情|基本信息|基础信息|基本面|财务报表|财报|财务|新闻|公告|快照|数据来源|均线策略|均线|策略|风险|收益|信号|数据|K\s*线|kline", re.IGNORECASE)
# Residual chatter that is never a company name. Without this, follow-ups like
# “看看最近怎么样” would be searched as if the user had named a stock.
_NOT_NAME = re.compile(
    r"怎么样|怎么|如何|什么|哪些|哪个|咋样|情况|市场|大盘|表现|走势|消息|机会|"
    r"风险|策略|股票|个股|它|这只|该股|你好|您好|助手|谢谢|公司|板块|行业|"
    r"指数|自选|操作|建议|一下|看看",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TargetResolution:
    stock_code: str | None = None
    message: str | None = None
    explicit: bool = False


def name_query(message: str) -> str:
    return _INTENT.sub("", message).strip(" \t\n，。！？?!：:（）()")


def _verify(code: str, explicit: bool, invoke: Invoke) -> TargetResolution:
    result = invoke("fundamental.stock_info", {"stock_code": code})
    if result.get("ok"):
        return TargetResolution(code, explicit=explicit)
    return TargetResolution(message=f"未找到股票 {code}，当前股票库可能尚未收录；请确认股票代码。", explicit=explicit)


def resolve_target(
    message: str,
    previous_stock: str | None,
    context: dict[str, Any] | None,
    invoke: Invoke,
) -> TargetResolution:
    text = message.strip()
    if _COMPARE.search(text):
        return TargetResolution(message="本轮请先选择一只股票，再进行查询或研究。", explicit=True)
    try:
        references = find_stock_references(text)
    except StockCodeError as exc:
        return TargetResolution(message=str(exc), explicit=True)
    codes = list(dict.fromkeys(reference.code for reference in references))
    if len(codes) > 1:
        return TargetResolution(message="检测到多个股票代码，请选择本次查询或研究的一只股票。", explicit=True)
    # Reject malformed symbol tokens even when another valid code is present.
    stripped = text
    for reference in reversed(references):
        stripped = stripped[:reference.start] + stripped[reference.end:]
    if _CODE_LIKE.search(stripped):
        return TargetResolution(message="股票代码格式无法识别，请使用 000001.sz 或 sz.000001。", explicit=True)
    if codes:
        return _verify(codes[0], True, invoke)
    query = name_query(text)
    # Stock names are matched from the local catalog only; Latin-only tokens
    # such as strategy ids (ma_cross) are not company names and must not be
    # searched as one.
    if (
        query
        and re.fullmatch(r"[㐀-鿿A-Za-z0-9*%_]{2,30}", query)
        and re.search(r"[㐀-鿿]", query)
        and not _NOT_NAME.search(query)
    ):
        result = invoke("market.search", {"query": query})
        data = result.get("data") or {}
        matches = data.get("matches") or []
        if result.get("ok") and data.get("total") == 1 and not data.get("truncated") and len(matches) == 1:
            return _verify(matches[0]["code"], True, invoke)
        if result.get("ok") and data.get("total", 0) > 1:
            candidates = "、".join(f"{row['name']}（{row['code']}）" for row in matches)
            return TargetResolution(message=f"找到多个候选，请选择一只股票：{candidates}", explicit=True)
        return TargetResolution(message=f"当前股票库未找到“{query}”，请提供股票代码或完整名称。", explicit=True)
    if previous_stock:
        return _verify(previous_stock, False, invoke)
    if context and context.get("entity_type") == "stock":
        try:
            code = normalize_stock_code(context.get("entity_id"))
        except StockCodeError:
            return TargetResolution(message="当前页面的股票代码无效，请提供股票代码。")
        return _verify(code, False, invoke)
    return TargetResolution(message="请提供股票代码或名称，例如 000001.sz 或平安银行。")


def is_lookup_message(message: str) -> bool:
    """Only plain identity/quote lookups automatically fetch a live snapshot."""
    return not re.search(r"新闻|公告|财报|财务|基本信息|基础信息|基本面|K\s*线|kline", message, re.IGNORECASE)
