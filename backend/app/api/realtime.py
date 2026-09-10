import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import AuthError, get_current_api_key, validate_api_key
from app.config import get_db, settings
from app.exceptions import ProviderUnavailableError
from app.models.models import DailyKline, Stock
from app.services.realtime_service import FetchResult, realtime_service

logger = logging.getLogger(__name__)
router = APIRouter()

# WebSocket 连接频率追踪（每 IP 最多 5 条并发连接，超量拒绝）
_ws_conn_tracker: dict[str, int] = defaultdict(int)


@dataclass
class _RealtimeChannel:
    queues: set[asyncio.Queue[dict]] = field(default_factory=set)
    task: asyncio.Task[None] | None = None


class _RealtimeHub:
    """One tail poller per stock/period, fanning updates to WS subscribers."""

    def __init__(self) -> None:
        self._channels: dict[tuple[str, str], _RealtimeChannel] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, symbol: str, period: str) -> asyncio.Queue[dict]:
        key = (symbol, period)
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=2)
        async with self._lock:
            channel = self._channels.setdefault(key, _RealtimeChannel())
            channel.queues.add(queue)
            if channel.task is None or channel.task.done():
                channel.task = asyncio.create_task(self._poll(key, channel))
        return queue

    async def unsubscribe(self, symbol: str, period: str, queue: asyncio.Queue[dict]) -> None:
        key = (symbol, period)
        async with self._lock:
            channel = self._channels.get(key)
            if channel is None:
                return
            channel.queues.discard(queue)
            if not channel.queues:
                # Let a short-lived task finish its current provider call; the
                # next loop sees the empty subscriber set and exits.
                self._channels.pop(key, None)

    async def _poll(self, key: tuple[str, str], channel: _RealtimeChannel) -> None:
        symbol, period = key
        try:
            while channel.queues:
                await asyncio.sleep(settings.REALTIME_WS_POLL_S)
                if not channel.queues:
                    return
                result = await asyncio.to_thread(
                    realtime_service.fetch_bars_tail, symbol, period
                )
                message = {
                    "type": "update",
                    "data": result.data,
                    "status": result.status,
                    "stale": result.stale,
                    "cache_age_ms": result.cache_age_ms,
                    "fetched_at": result.fetched_at,
                    "market_at": result.market_at,
                    "reason": result.reason,
                }
                for queue in tuple(channel.queues):
                    try:
                        queue.put_nowait(message)
                    except asyncio.QueueFull:
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        queue.put_nowait(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("realtime shared poller failed for %s/%s", symbol, period)


_realtime_hub = _RealtimeHub()


class RealtimeBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    symbol: str


class RealtimeBarsResponse(BaseModel):
    success: bool
    code: str
    data: list[RealtimeBar]
    status: str | None = None
    provider: str | None = None
    served_at: float | None = None
    fetched_at: float | None = None
    market_at: str | None = None
    cache_age_ms: int | None = None
    stale: bool | None = None
    cache_source: str | None = None
    reason: str | None = None


class RealtimeQuote(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    change: float
    change_percent: float
    prev_close: float


class RealtimeIndex(BaseModel):
    symbol: str
    name: str
    close: float
    change: float
    change_percent: float
    prev_close: float


class RealtimeQuotesResponse(BaseModel):
    success: bool
    data: list[RealtimeQuote]
    status: str | None = None
    provider: str | None = None
    served_at: float | None = None
    fetched_at: float | None = None
    cache_age_ms: int | None = None
    stale: bool | None = None
    cache_source: str | None = None
    reason: str | None = None


class RealtimeIndicesResponse(BaseModel):
    success: bool
    data: list[RealtimeIndex]
    status: str | None = None
    provider: str | None = None
    served_at: float | None = None
    fetched_at: float | None = None
    cache_age_ms: int | None = None
    stale: bool | None = None
    cache_source: str | None = None
    reason: str | None = None


def _raise_if_unavailable(result: FetchResult, *, endpoint: str) -> None:
    """Convert an unavailable envelope into a structured 503 error.

    The frontend uses ``retryable`` + ``reason`` to decide whether to
    surface a retry button vs. a one-shot toast. ``ok`` and ``empty``
    envelopes fall through (graceful degrade → 200 + empty data).
    """
    if result.status != "unavailable":
        return
    raise ProviderUnavailableError(
        detail="Realtime provider unavailable",
        provider=result.provider,
        error_code="provider_unavailable",
        extra={
            "reason": result.reason,
            "endpoint": endpoint,
            "selected_server": (
                {"host": result.selected_server[0], "port": result.selected_server[1]}
                if result.selected_server
                else None
            ),
        },
    )


def _cache_daily_bars_for_research(
    db: Session, stock_code: str, bars: list[dict]
) -> int:
    """Upsert mootdx daily bars used by the strategy engine.

    Realtime quotes remain read-only by default.  The strategy page opts into
    this cache so its existing backtest/optimizer services all consume the
    exact same mootdx snapshot shown in the chart.
    """
    stock = db.query(Stock).filter(Stock.code == stock_code).first()
    if stock is None:
        return 0

    parsed: dict[date, dict] = {}
    for bar in bars:
        try:
            bar_date = date.fromisoformat(str(bar.get("date", ""))[:10])
            values = {
                "open": float(bar.get("open", 0) or 0),
                "high": float(bar.get("high", 0) or 0),
                "low": float(bar.get("low", 0) or 0),
                "close": float(bar.get("close", 0) or 0),
                "volume": float(bar.get("volume", 0) or 0),
                "amount": float(bar.get("amount", 0) or 0),
            }
        except (TypeError, ValueError):
            continue
        if values["close"] <= 0:
            continue
        parsed[bar_date] = values

    if not parsed:
        return 0

    existing = {
        item.date: item
        for item in db.query(DailyKline)
        .filter(
            DailyKline.stock_code == stock_code,
            DailyKline.date.in_(parsed.keys()),
        )
        .all()
    }
    for bar_date, values in parsed.items():
        item = existing.get(bar_date)
        if item is None:
            db.add(DailyKline(stock_code=stock_code, date=bar_date, **values))
        else:
            for field, value in values.items():
                setattr(item, field, value)
    db.commit()
    return len(parsed)


@router.get('/realtime/health', response_model=dict)
def get_realtime_health(_: str = Depends(get_current_api_key)) -> dict:
    """Provider health snapshot: selected node, healthy pool size, counters.

    Used by the Dashboard to render a "data feed" badge and by ops to
    verify failover after a configuration change.
    """
    return realtime_service.get_provider_health()


@router.get('/realtime/quotes', response_model=RealtimeQuotesResponse, response_model_exclude_none=True)
def get_realtime_quotes(
    codes: str = Query(..., description="股票代码，逗号分隔，如 600036,000001,sh.600036"),
    _: str = Depends(get_current_api_key),
):
    """批量获取股票实时行情（最新价格/涨跌幅）

    Provider 不可达时返回 503 + ``{code: provider_unavailable,
    provider: mootdx, retryable: true, reason}``。Provider 可达但
    markets closed / 无报价时返回 200 + ``data: []``。
    """
    # Strip market prefix (sh./sz./bj.) as mootdx expects raw 6-digit codes
    symbol_list = [s.strip().split('.')[-1] if '.' in s else s for s in codes.split(',') if s.strip()]
    result = realtime_service.fetch_quotes(symbol_list)
    _raise_if_unavailable(result, endpoint="quotes")
    return RealtimeQuotesResponse(
        success=True,
        data=[RealtimeQuote(**item) for item in result.data],
        status=result.status,
        provider=result.provider,
        served_at=result.served_at,
        fetched_at=result.fetched_at,
        cache_age_ms=result.cache_age_ms,
        stale=result.stale,
        cache_source=result.cache_source,
        reason=result.reason,
    )


@router.get('/realtime/indices', response_model=RealtimeIndicesResponse, response_model_exclude_none=True)
def get_realtime_indices(
    _: str = Depends(get_current_api_key),
):
    """获取主要指数实时行情。

    与 ``/realtime/quotes`` 同等契约：provider 不可达 → 503；可达但
    无数据 → 200 + 空 data。
    """
    result = realtime_service.fetch_indices()
    _raise_if_unavailable(result, endpoint="indices")
    return RealtimeIndicesResponse(
        success=True,
        data=[RealtimeIndex(**item) for item in result.data],
        status=result.status,
        provider=result.provider,
        served_at=result.served_at,
        fetched_at=result.fetched_at,
        cache_age_ms=result.cache_age_ms,
        stale=result.stale,
        cache_source=result.cache_source,
        reason=result.reason,
    )


@router.get('/realtime/{code}', response_model=RealtimeBarsResponse, response_model_exclude_none=True)
def get_realtime_bars(
    code: str,
    period: str = Query('daily', description="daily|weekly|monthly"),
    cache_for_research: bool = Query(False),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """获取股票实时K线数据（日/周/月）

    Provider 不可达时返回 503 + 结构化错误体；Provider 可达但市场
    关闭 / 无 K 线数据时返回 200 + ``data: []``，与历史合约一致。
    """
    # 去掉市场前缀 (sh.600036 -> 600036)
    symbol = code.split('.')[-1] if '.' in code else code

    try:
        result = realtime_service.fetch_bars(symbol, period)
    except Exception:
        logger.exception(
            "realtime bars fetch failed for %s (period=%s)", code, period,
        )
        # Treat unhandled exceptions as provider outage (mirrors fetch_bars'
        # own unavailable branch).
        raise ProviderUnavailableError(
            detail="Realtime provider unavailable",
            provider="mootdx",
            error_code="provider_unavailable",
            extra={"endpoint": "bars", "code": code, "period": period},
        )

    # Compatibility for lightweight integrations that replace the service
    # with a legacy list-returning mock.
    if not isinstance(result, FetchResult):
        try:
            legacy_data = realtime_service.normalise_bars(symbol, offset=750)
        except Exception:
            legacy_data = []
        return RealtimeBarsResponse(success=True, code=code, data=[RealtimeBar(**item) for item in legacy_data])

    _raise_if_unavailable(result, endpoint="bars")
    if cache_for_research and period == "daily" and result.data:
        try:
            _cache_daily_bars_for_research(db, code, result.data)
        except Exception:
            db.rollback()
            logger.exception("failed to cache mootdx bars for strategy research: %s", code)
            raise
    metadata = (
        {
            "status": result.status,
            "provider": result.provider,
            "served_at": result.served_at,
            "fetched_at": result.fetched_at,
            "market_at": result.market_at,
            "cache_age_ms": result.cache_age_ms,
            "stale": result.stale,
            "cache_source": result.cache_source,
            "reason": result.reason,
        }
        if result.status == "ok"
        else {}
    )
    return RealtimeBarsResponse(
        success=True,
        code=code,
        data=[RealtimeBar(**item) for item in result.data],
        **metadata,
    )


@router.websocket('/ws/realtime/{code}')
async def ws_realtime_bars(
    websocket: WebSocket,
    code: str,
    period: str = 'daily',
):
    """WebSocket 推送实时K线数据（需 api_key 查询参数认证）。

    1. 连接后立即推送完整历史数据 → ``{ type: "init", data: [...] }``
    2. 每隔 10s 推送最新 2 根 K 线 → ``{ type: "update", data: [...] }``

    查询参数: ``period`` (daily|weekly|monthly, 默认 daily)
               ``api_key`` (必填，与 X-API-Key 相同)
    """
    # ── 认证：浏览器复用已签名 session，外部客户端仍可使用 api_key ──
    session = websocket.scope.get("session", {})
    if not session.get("authenticated"):
        api_key = websocket.query_params.get('api_key', '')
        try:
            validate_api_key(api_key)
        except AuthError:
            logger.warning("ws_realtime_bars auth rejected: %s", code)
            await websocket.close(code=4008)
            return

    # ── 简单的每 IP 连接频率限制 ──
    client_host = websocket.client.host if websocket.client else 'unknown'
    _ws_conn_tracker[client_host] += 1
    if _ws_conn_tracker[client_host] > 5:
        logger.warning("ws_realtime_bars rate limit exceeded: %s", client_host)
        cnt = _ws_conn_tracker.get(client_host, 0)
        if cnt > 1:
            _ws_conn_tracker[client_host] = cnt - 1
        elif cnt == 1:
            del _ws_conn_tracker[client_host]
        await websocket.close(code=4009)
        return

    await websocket.accept()

    symbol = code.split('.')[-1] if '.' in code else code

    try:
        # ---- 初始全量 ----
        init_result = await asyncio.to_thread(
            realtime_service.fetch_bars, symbol, period
        )
        await websocket.send_json({
            "type": "init",
            "data": init_result.data,
            "status": init_result.status,
            "stale": init_result.stale,
            "cache_age_ms": init_result.cache_age_ms,
            "fetched_at": init_result.fetched_at,
            "market_at": init_result.market_at,
            "reason": init_result.reason,
        })

        # ---- 共享增量推送：同一股票/周期只保留一个尾部轮询器 ----
        updates = await _realtime_hub.subscribe(symbol, period)
        while True:
            await websocket.send_json(await updates.get())
    except WebSocketDisconnect:
        logger.info("ws_realtime_bars disconnected: %s", code)
    except Exception:
        logger.exception("ws_realtime_bars error: %s", code)
        try:
            await websocket.close(code=1011)
        except Exception:
            logger.debug("Failed to close websocket after provider error", exc_info=True)
    finally:
        if 'updates' in locals():
            await _realtime_hub.unsubscribe(symbol, period, updates)
        # 清理连接计数
        cnt = _ws_conn_tracker.get(client_host, 0)
        if cnt > 1:
            _ws_conn_tracker[client_host] = cnt - 1
        elif cnt == 1:
            del _ws_conn_tracker[client_host]
