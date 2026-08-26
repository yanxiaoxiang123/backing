from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


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
    parameters: Optional[dict] = None  # JSON 对象（schema v1）


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
    strategy_name: Optional[str] = None
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
    parameters: Optional[dict] = None
    portfolio_values: Optional[list[dict]] = None
    created_at: datetime
    trades: List[BacktestTradeResponse] = []

    class Config:
        from_attributes = True


class BacktestListResponse(BaseModel):
    id: int
    strategy_name: Optional[str] = None
    stock_code: str
    start_date: date
    end_date: date
    total_return: float
    total_trades: int
    parameters: Optional[dict] = None
    portfolio_values: Optional[list[dict]] = None
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


# Job schemas — maps directly from JobDbRecord ORM rows
class JobRecordSchema(BaseModel):
    id: str
    job_type: str
    status: str
    message: str
    progress: float
    payload: dict = {}
    result: Optional[dict] = None
    error: Optional[str] = None
    job_key: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 0
    lease_until: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Screener schemas
class ScreenerStockResult(BaseModel):
    stock_code: str
    stock_name: str
    close: float
    volume: float
    change_pct: float
    ma5: float
    ma10: float
    ma20: float
    macd_dif: float
    macd_dea: float
    macd_hist: float
    rsi: float
    volume_ratio: float
    composite_score: float
    ai_signal: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_reason: Optional[str] = None


class ScreenerAgentResponse(BaseModel):
    success: bool
    total_scanned: int
    results: List[ScreenerStockResult] = []
    execution_time_s: float = 0.0
