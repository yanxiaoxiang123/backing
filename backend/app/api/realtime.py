from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import BaseModel
from typing import List
import asyncio
import logging
import time
from collections import defaultdict

from app.services.realtime_service import realtime_service
from app.auth import get_current_api_key, validate_api_key, AuthError

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
    data: List[RealtimeBar]


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
    data: List[RealtimeQuote]


class RealtimeIndicesResponse(BaseModel):
    success: bool
    data: List[RealtimeIndex]


@router.get('/realtime/quotes', response_model=RealtimeQuotesResponse)
def get_realtime_quotes(
    codes: str = Query(..., description="股票代码，逗号分隔，如 600036,000001,sh.600036"),
    _: str = Depends(get_current_api_key),
):
    """批量获取股票实时行情（最新价格/涨跌幅）"""
    # Strip market prefix (sh./sz./bj.) as mootdx expects raw 6-digit codes
    symbol_list = [s.strip().split('.')[-1] if '.' in s else s for s in codes.split(',') if s.strip()]
    data = realtime_service.get_realtime_quotes(symbol_list)
    return RealtimeQuotesResponse(success=True, data=[RealtimeQuote(**item) for item in data])


@router.get('/realtime/indices', response_model=RealtimeIndicesResponse)
def get_realtime_indices(
    _: str = Depends(get_current_api_key),
):
    """获取主要指数实时行情"""
    data = realtime_service.get_index_realtime()
    return RealtimeIndicesResponse(success=True, data=[RealtimeIndex(**item) for item in data])


@router.get('/realtime/{code}', response_model=RealtimeBarsResponse)
def get_realtime_bars(
    code: str,
    period: str = Query('daily', description="daily|weekly|monthly"),
    _: str = Depends(get_current_api_key),
):
    """获取股票实时K线数据（日/周/月）"""
    # 去掉市场前缀 (sh.600036 -> 600036)
    symbol = code.split('.')[-1] if '.' in code else code

    # period -> frequency 映射
    freq_map = {'daily': 9, 'weekly': 5, 'monthly': 6}
    frequency = freq_map.get(period, 9)

    # offset: 日K 750(3年), 周K 104(2年), 月K 36(3年)
    offset_map = {'daily': 750, 'weekly': 104, 'monthly': 36}
    offset = offset_map.get(period, 750)

    data = realtime_service.normalise_bars(symbol=symbol, frequency=frequency, offset=offset)

    return RealtimeBarsResponse(
        success=True,
        code=code,
        data=[RealtimeBar(**item) for item in data],
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
    # ── 认证 ──
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
    freq_map = {'daily': 9, 'weekly': 5, 'monthly': 6}
    offset_map = {'daily': 750, 'weekly': 104, 'monthly': 36}

    try:
        freq = freq_map.get(period, 9)
        offset = offset_map.get(period, 750)

        # ---- 初始全量 ----
        data = await asyncio.to_thread(
            realtime_service.normalise_bars,
            symbol=symbol, frequency=freq, offset=offset,
        )
        await websocket.send_json({"type": "init", "data": data})

        # ---- 增量推送 ----
        while True:
            await asyncio.sleep(10)
            tail = await asyncio.to_thread(
                realtime_service.normalise_bars,
                symbol=symbol, frequency=freq, offset=2,
            )
            if tail:
                await websocket.send_json({"type": "update", "data": tail})
    except WebSocketDisconnect:
        logger.info("ws_realtime_bars disconnected: %s", code)
    except Exception:
        logger.error("ws_realtime_bars error: %s", code, exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        # 清理连接计数
        cnt = _ws_conn_tracker.get(client_host, 0)
        if cnt > 1:
            _ws_conn_tracker[client_host] = cnt - 1
        elif cnt == 1:
            del _ws_conn_tracker[client_host]
