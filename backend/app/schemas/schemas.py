from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


# Stock schemas
class StockBase(BaseModel):
    code: str
    name: str
    market: str


class StockCreate(StockBase):
    pass


class StockResponse(StockBase):
    id: int
    list_date: Optional[date] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Daily Kline schemas
class DailyKlineBase(BaseModel):
    stock_code: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None


class DailyKlineResponse(DailyKlineBase):
    id: int

    class Config:
        from_attributes = True


# Strategy schemas
class StrategyBase(BaseModel):
    name: str
    description: Optional[str] = None
    strategy_type: str
    parameters: Optional[str] = None


class StrategyCreate(StrategyBase):
    pass


class StrategyResponse(StrategyBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Backtest schemas
class BacktestRequest(BaseModel):
    stock_code: str
    strategy_type: str = "ma_cross"
    start_date: date
    end_date: date
    initial_capital: float = 100000
    parameters: Optional[dict] = None


class BacktestTradeResponse(BaseModel):
    id: int
    trade_date: date
    action: str
    price: float
    quantity: int
    amount: float

    class Config:
        from_attributes = True


class BacktestResultResponse(BaseModel):
    id: int
    strategy_id: int
    stock_code: str
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: int
    created_at: datetime
    trades: List[BacktestTradeResponse] = []

    class Config:
        from_attributes = True


class BacktestListResponse(BaseModel):
    id: int
    stock_code: str
    start_date: date
    end_date: date
    total_return: float
    total_trades: int
    created_at: datetime

    class Config:
        from_attributes = True


# Sync status
class SyncResponse(BaseModel):
    success: bool
    message: str
    stocks_synced: int = 0
    klines_synced: int = 0


# Watchlist schemas
class WatchlistItemCreate(BaseModel):
    stock_code: str


class WatchlistItemResponse(BaseModel):
    id: int
    stock_code: str
    stock_name: Optional[str] = None
    added_at: datetime

    class Config:
        from_attributes = True


class WatchlistListResponse(BaseModel):
    items: List[WatchlistItemResponse]
    total: int
