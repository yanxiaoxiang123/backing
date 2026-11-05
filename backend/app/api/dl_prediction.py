"""
DL 预测 API 接口
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import get_authenticated_actor, get_current_api_key
from app.exceptions import ConflictError, ExternalServiceError
from app.limiter import limiter
from app.services.dl_prediction.contracts import BacktestExperimentRequest, ExperimentRequest
from app.services.dl_prediction import experiments  # noqa: F401 - register durable runners
from app.services.dl_prediction.remote import KronosClient
from app.services.job_store import job_store
from app.services.market_data import digest
from app.services.tasks import get_task_executor
from app.services.baostock_service import BaostockService
from app.services.dl_prediction.backtest import DLBacktester
from app.services.dl_prediction.predictor import DLPredictor

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models")
def models(_: str = Depends(get_current_api_key)):
    try:
        remote = KronosClient().status()
        reason = None
    except Exception as exc:
        remote = {"available": False}
        reason = getattr(exc, "detail", "远程 Kronos 服务不可用")
    return {
        "models": [
            {"id": name, "name": name.replace("kronos", "Kronos"), "min_context": 60,
             "max_context": 512, "min_horizon": 1, "max_horizon": 30,
             "available": bool(remote.get("available")), "reason": reason}
            for name in ("kronos-small", "kronos-base")
        ] + [{"id": "legacy", "name": "现有预测器（含技术指标降级）", "min_context": 30,
              "max_context": 250, "min_horizon": 5, "max_horizon": 5, "available": True}],
        "remote": remote,
    }


def _submit_experiment(request: Request, body: ExperimentRequest, actor: str, backtest: bool) -> dict:
    payload = body.model_dump(mode="json")
    operation = "dl_backtest" if backtest else "dl_predict"
    key = request.headers.get("Idempotency-Key")
    if key and len(key) > 128:
        raise HTTPException(400, detail="Idempotency-Key too long")
    job_key = f"{operation}:{digest(actor)}:{key}" if key else None
    if job_key:
        existing = job_store._find_by_key(job_key)
        if existing and existing.payload != payload:
            raise ConflictError("同一 Idempotency-Key 不能提交不同实验")
    job = get_task_executor().submit(operation, payload=payload, job_key=job_key)
    return {"job_id": job.id, "status": job.status, "job_type": operation, "message": job.message}


@router.post("/predict/submit", status_code=202)
@limiter.limit("10/minute")
def submit_predict(
    request: Request, body: ExperimentRequest, actor: str = Depends(get_authenticated_actor),
):
    return _submit_experiment(request, body, actor, False)


@router.post("/backtest/submit", status_code=202)
@limiter.limit("5/minute")
def submit_backtest(
    request: Request, body: BacktestExperimentRequest, actor: str = Depends(get_authenticated_actor),
):
    return _submit_experiment(request, body, actor, True)


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
def predict(request: DLPredictRequest, _: str = Depends(get_current_api_key)):
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
    except Exception as exc:
        logger.exception("预测失败")
        raise ExternalServiceError("prediction_failed", str(exc)) from exc


@router.post("/backtest", response_model=DLBacktestResponse)
def backtest(request: DLBacktestRequest, _: str = Depends(get_current_api_key)):
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

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("回测失败")
        raise ExternalServiceError("backtest_failed", str(exc)) from exc


def _convert_to_baostock_code(stock_code: str) -> str:
    """转换股票代码为 baostock 格式"""
    if stock_code.startswith("6"):
        return f"sh.{stock_code}"
    elif stock_code.startswith(("0", "3")):
        return f"sz.{stock_code}"
    else:
        return stock_code
