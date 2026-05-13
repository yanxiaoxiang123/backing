"""
DL 预测 API 接口
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

from app.auth import get_current_api_key
from app.services.baostock_service import BaostockService
from app.services.dl_prediction.predictor import DLPredictor
from app.services.dl_prediction.backtest import DLBacktester

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Request/Response Models ==============


class DLPredictRequest(BaseModel):
    stock_code: str
    kline_days: int = 60


class DLPredictionData(BaseModel):
    stock_code: str
    current_price: float
    last_date: str
    prediction_dates: List[str]
    predicted_prices: List[float]
    kline_data: List[dict]


class DLPredictResponse(BaseModel):
    success: bool = True
    data: Optional[DLPredictionData] = None
    error: Optional[str] = None


class DLBacktestRequest(BaseModel):
    stock_code: str
    start_date: str
    end_date: str
    initial_capital: float = 100000


class DLBacktestResponse(BaseModel):
    success: bool = True
    data: Optional[dict] = None
    error: Optional[str] = None


# ============== API Routes ==============


@router.post("/predict", response_model=DLPredictResponse)
async def predict(request: DLPredictRequest, _: str = Depends(get_current_api_key)):
    """
    预测未来5天收盘价
    """
    try:
        # 获取K线数据
        bs_code = _convert_to_baostock_code(request.stock_code)
        baostock = BaostockService()

        # 获取最近2年的数据，确保有足够的历史数据
        from datetime import datetime, timedelta

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

        df = baostock.get_daily_kline(bs_code, start_date, end_date)

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="未找到股票数据")

        # 转换为字典列表
        kline_data = df.to_dict("records")

        # 取最后 N 天的数据
        if len(kline_data) > request.kline_days:
            kline_data = kline_data[-request.kline_days :]

        # 预测
        predictor = DLPredictor()
        result = predictor.predict(request.stock_code, kline_data)

        return DLPredictResponse(success=True, data=DLPredictionData(**result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预测失败: {e}")
        return DLPredictResponse(success=False, error="Prediction failed")


@router.post("/backtest", response_model=DLBacktestResponse)
async def backtest(request: DLBacktestRequest, _: str = Depends(get_current_api_key)):
    """
    基于预测结果进行回测
    """
    try:
        backtester = DLBacktester()
        result = backtester.run_backtest(
            stock_code=request.stock_code,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
        )

        return DLBacktestResponse(success=True, data=result)

    except Exception as e:
        logger.error(f"回测失败: {e}")
        return DLBacktestResponse(success=False, error="Backtest failed")


def _convert_to_baostock_code(stock_code: str) -> str:
    """转换股票代码为 baostock 格式"""
    if stock_code.startswith("6"):
        return f"{stock_code}.sh"
    elif stock_code.startswith(("0", "3")):
        return f"{stock_code}.sz"
    else:
        return stock_code
