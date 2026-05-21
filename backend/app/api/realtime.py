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
    _: str = Query(None, description="API key", alias='api_key'),
):
    """获取股票实时日K数据（最近10条）"""
    # 去掉市场前缀 (sh.600036 -> 600036)
    symbol = code.split('.')[-1] if '.' in code else code

    data = realtime_service.normalise_bars(symbol=symbol, offset=10)

    return RealtimeBarsResponse(
        success=True,
        code=code,
        data=[RealtimeBar(**item) for item in data],
    )
