import asyncio
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.auth import AuthError, get_current_api_key, validate_api_key
from app.config import settings
from app.exceptions import ProviderUnavailableError
from app.services.realtime_service import FetchResult, realtime_service

logger = logging.getLogger(__name__)
router = APIRouter()

# WebSocket 连接频率追踪（每 IP 最多 5 条并发连接，超量拒绝）
_ws_conn_tracker: dict[str, int] = defaultdict(int)


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


class RealtimeIndicesResponse(BaseModel):
    success: bool
    data: list[RealtimeIndex]


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


@router.get('/realtime/health', response_model=dict)
def get_realtime_health(_: str = Depends(get_current_api_key)) -> dict:
    """Provider health snapshot: selected node, healthy pool size, counters.

    Used by the Dashboard to render a "data feed" badge and by ops to
    verify failover after a configuration change.
    """
    return realtime_service.get_provider_health()


@router.get('/realtime/quotes', response_model=RealtimeQuotesResponse)
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
    )


@router.get('/realtime/indices', response_model=RealtimeIndicesResponse)
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
    )


@router.get('/realtime/{code}', response_model=RealtimeBarsResponse)
def get_realtime_bars(
    code: str,
    period: str = Query('daily', description="daily|weekly|monthly"),
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

    _raise_if_unavailable(result, endpoint="bars")
    return RealtimeBarsResponse(
        success=True,
        code=code,
        data=[RealtimeBar(**item) for item in result.data],
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
        })

        # ---- 增量推送 ----
        while True:
            await asyncio.sleep(settings.REALTIME_WS_POLL_S)
            tail_result = await asyncio.to_thread(
                realtime_service.fetch_bars, symbol, period
            )
            if tail_result.data:
                await websocket.send_json({
                    "type": "update",
                    "data": tail_result.data,
                    "status": tail_result.status,
                })
    except WebSocketDisconnect:
        logger.info("ws_realtime_bars disconnected: %s", code)
    except Exception:
        logger.exception("ws_realtime_bars error: %s", code)
        try:
            await websocket.close(code=1011)
        except Exception:
            logger.debug("Failed to close websocket after provider error", exc_info=True)
    finally:
        # 清理连接计数
        cnt = _ws_conn_tracker.get(client_host, 0)
        if cnt > 1:
            _ws_conn_tracker[client_host] = cnt - 1
        elif cnt == 1:
            del _ws_conn_tracker[client_host]