"""确定性研究数据层（规格 v2 决策 17-18；US-2.6）。

数据源：akshare（个股新闻/公告/财报摘要）、baostock（基准指数日线）。
证据语义：每条数据携带 source_id/as_of/vendor/data_version；LLM 只消费
本层证据，禁止凭空陈述事实；无法获取时必须显式报错，不伪造数据。

缓存：独立 SQLite 库 backend/data/research_cache.db，与主业务库完全隔离
（不建 Alembic 迁移），键控 (tool, params_hash)；命中返回原证据五元组，
未命中外呼后写入。缓存库线程安全（check_same_thread=False + WAL）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

import akshare as ak
import pandas as pd

from app.services.baostock_service import baostock_service

logger = logging.getLogger(__name__)

DATA_VERSION = "1.0.0"

_BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_CACHE_DIR = os.path.join(_BACKEND_DIR, "data")
_CACHE_DB = os.path.join(_CACHE_DIR, "research_cache.db")
_CACHE_LOCK = threading.Lock()

_NEWS_CONTENT_LIMIT = 400


def _normalize_code(stock_code: str) -> str:
    """'sh.600000' -> '600000'（akshare 使用 6 位纯代码）。"""
    return stock_code.split(".")[-1].strip()


def _as_of() -> str:
    return datetime.now(timezone.utc).isoformat()


def _params_hash(params: dict[str, Any]) -> str:
    canonical = json.dumps(params, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _connect() -> sqlite3.Connection:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    conn = sqlite3.connect(_CACHE_DB, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS research_cache (
            tool TEXT NOT NULL,
            params_hash TEXT NOT NULL,
            payload TEXT NOT NULL,
            source_id TEXT,
            as_of TEXT,
            vendor TEXT,
            data_version TEXT,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (tool, params_hash)
        )
        """
    )
    conn.commit()
    return conn


def cache_get(tool: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """命中返回 {payload, source_id, as_of, vendor, data_version}；未命中 None。"""
    ph = _params_hash(params)
    with _CACHE_LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT payload, source_id, as_of, vendor, data_version "
                "FROM research_cache WHERE tool = ? AND params_hash = ?",
                (tool, ph),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None
    return {
        "payload": json.loads(row[0]),
        "source_id": row[1],
        "as_of": row[2],
        "vendor": row[3],
        "data_version": row[4],
    }


def cache_put(
    tool: str,
    params: dict[str, Any],
    payload: Any,
    *,
    source_id: str,
    as_of: str,
    vendor: str,
    data_version: str,
) -> None:
    ph = _params_hash(params)
    with _CACHE_LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO research_cache "
                "(tool, params_hash, payload, source_id, as_of, vendor, "
                " data_version, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tool,
                    ph,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    source_id,
                    as_of,
                    vendor,
                    data_version,
                    _as_of(),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def _clean_news_records(df: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    records = df.head(limit).to_dict(orient="records")
    cleaned: list[dict[str, Any]] = []
    for rec in records:
        item = dict(rec)
        content = item.get("新闻内容") or ""
        if isinstance(content, str) and len(content) > _NEWS_CONTENT_LIMIT:
            item["新闻内容"] = content[:_NEWS_CONTENT_LIMIT] + "…"
        cleaned.append(item)
    return cleaned


def fetch_stock_news(stock_code: str, limit: int = 10) -> dict[str, Any]:
    """个股新闻（akshare stock_news_em）。返回证据五元组 dict。"""
    tool = "event.news"
    params = {"stock_code": stock_code, "limit": limit}
    hit = cache_get(tool, params)
    if hit is not None:
        return hit
    code = _normalize_code(stock_code)
    try:
        df = ak.stock_news_em(symbol=code)
    except Exception as exc:
        raise ValueError(f"新闻获取失败（{code}）: {exc}") from exc
    if df is None or df.empty:
        raise ValueError(f"无新闻数据: {code}")
    payload = {
        "stock_code": stock_code,
        "rows": len(df.head(limit)),
        "news": _clean_news_records(df, limit),
    }
    entry = {
        "payload": payload,
        "source_id": f"news:{code}",
        "as_of": _as_of(),
        "vendor": "akshare",
        "data_version": DATA_VERSION,
    }
    cache_put(tool, params, **entry)
    return entry


def fetch_announcements(stock_code: str, date: str) -> dict[str, Any]:
    """指定日期的个股公告（akshare stock_notice_report）。"""
    tool = "event.announcement"
    params = {"stock_code": stock_code, "date": date}
    hit = cache_get(tool, params)
    if hit is not None:
        return hit
    code = _normalize_code(stock_code)
    compact_date = date.replace("-", "")
    try:
        df = ak.stock_notice_report(symbol=code, date=compact_date)
    except Exception as exc:
        raise ValueError(f"公告获取失败（{code} {date}）: {exc}") from exc
    if df is None or df.empty:
        raise ValueError(f"无公告数据: {code} {date}")
    payload = {
        "stock_code": stock_code,
        "date": date,
        "rows": len(df),
        "announcements": df.to_dict(orient="records"),
    }
    entry = {
        "payload": payload,
        "source_id": f"notice:{code}:{date}",
        "as_of": _as_of(),
        "vendor": "akshare",
        "data_version": DATA_VERSION,
    }
    cache_put(tool, params, **entry)
    return entry


def fetch_financials_summary(stock_code: str, periods: int = 5) -> dict[str, Any]:
    """财报摘要（akshare stock_financial_abstract），取最近 periods 个报告期。"""
    tool = "fundamental.financials"
    params = {"stock_code": stock_code, "periods": periods}
    hit = cache_get(tool, params)
    if hit is not None:
        return hit
    code = _normalize_code(stock_code)
    try:
        df = ak.stock_financial_abstract(symbol=code)
    except Exception as exc:
        raise ValueError(f"财报摘要获取失败（{code}）: {exc}") from exc
    if df is None or df.empty:
        raise ValueError(f"无财报摘要数据: {code}")
    payload = {
        "stock_code": stock_code,
        "rows": len(df.head(periods)),
        "financials": df.head(periods).to_dict(orient="records"),
    }
    entry = {
        "payload": payload,
        "source_id": f"financials:{code}",
        "as_of": _as_of(),
        "vendor": "akshare",
        "data_version": DATA_VERSION,
    }
    cache_put(tool, params, **entry)
    return entry


def fetch_index_kline(
    index_code: str, start_date: str, end_date: str
) -> dict[str, Any]:
    """基准指数日线（baostock get_index_daily_kline，只读）。"""
    tool = "market.index_kline"
    params = {
        "index_code": index_code,
        "start_date": start_date,
        "end_date": end_date,
    }
    hit = cache_get(tool, params)
    if hit is not None:
        return hit
    try:
        df = baostock_service.get_index_daily_kline(
            index_code, start_date, end_date
        )
    except Exception as exc:
        raise ValueError(f"指数行情获取失败（{index_code}）: {exc}") from exc
    if df is None or df.empty:
        raise ValueError(f"无指数行情数据: {index_code}")
    payload = {
        "index_code": index_code,
        "rows": len(df),
        "kline": df.to_dict(orient="records"),
    }
    entry = {
        "payload": payload,
        "source_id": f"index:{index_code}:{start_date}:{end_date}",
        "as_of": _as_of(),
        "vendor": "baostock",
        "data_version": DATA_VERSION,
    }
    cache_put(tool, params, **entry)
    return entry
