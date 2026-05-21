from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List

from app.services.realtime_service import realtime_service
from app.auth import get_current_api_key

router = APIRouter()


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


@router.get('/realtime/{code}', response_model=RealtimeBarsResponse)
def get_realtime_bars(
    code: str,
    period: str = Query('daily', description="daily|weekly|monthly"),
    _: str = Query(None, description="API key", alias='api_key'),
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
