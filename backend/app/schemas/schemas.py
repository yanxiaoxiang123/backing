from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# Stock schemas
class StockBase(BaseModel):
    code: str
    name: str
    market: str


class StockResponse(StockBase):
    id: int
    list_date: Optional[date] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    id: int | None = None
    adjustment: str = "legacy_unknown"
    versioned: bool = False

    model_config = ConfigDict(from_attributes=True)


# Backtest schemas
class BacktestRequest(BaseModel):
    stock_code: str
    strategy_type: str = "ma_cross"
    start_date: date
    end_date: date
    initial_capital: float = 100000
    parameters: Optional[dict] = None
    price_source: Literal["auto", "raw", "legacy"] = "auto"
    corporate_action_mode: Literal["price_only", "verified"] = "price_only"
    dividend_tax_rate: float = Field(0.0, ge=0, le=1, allow_inf_nan=False)


class BacktestTradeResponse(BaseModel):
    id: int
    trade_date: date
    action: str
    price: float
    quantity: int
    amount: float

    model_config = ConfigDict(from_attributes=True)


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
    execution_metadata: Optional[dict] = None
    created_at: datetime
    trades: List[BacktestTradeResponse] = []

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)
