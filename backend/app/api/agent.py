# -*- coding: utf-8 -*-
"""Agent 分析 API"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import SessionLocal, get_db
from app.auth import get_current_api_key
from app.models.analysis import AnalysisRecord
from app.models.models import DailyKline, Stock
from app.agent.orchestrator import AgentOrchestrator
from app.services.baostock_service import baostock_service, MAJOR_INDICES
from app.services.job_store import job_store

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class AnalyzeRequest(BaseModel):
    """分析请求"""

    stock_code: str
    stock_name: Optional[str] = ""
    mode: str = "standard"  # quick/standard/full/strategy


class AnalyzeResponse(BaseModel):
    """分析响应"""

    success: bool
    stock_code: str
    stock_name: str
    mode: str
    final_signal: str
    final_confidence: float
    final_reason: str
    opinions: List[dict]
    stages: List[dict]
    news_items: List[dict] = []
    duration_s: float
    error: Optional[str] = None


class AnalysisRecordResponse(BaseModel):
    """分析记录响应"""

    id: int
    stock_code: str
    stock_name: Optional[str]
    analysis_date: str
    mode: str
    final_signal: str
    final_confidence: float
    final_reason: Optional[str]
    duration_s: float
    error: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class AnalyzeSubmitResponse(BaseModel):
    job_id: str
    status: str
    message: str


# 大盘分析 Request/Response Models
class MarketAnalyzeRequest(BaseModel):
    """大盘分析请求"""

    index_codes: List[str] = []  # 空数组表示分析所有主要指数
    mode: str = "quick"


class IndexInfo(BaseModel):
    """指数信息"""

    code: str
    name: str


class MarketAnalyzeResponse(BaseModel):
    """大盘分析响应"""

    success: bool
    indices: List[dict]  # 各指数分析结果
    overall_signal: str  # 综合信号
    overall_confidence: float  # 综合置信度
    overall_reason: str  # 综合分析理由
    duration_s: float
    error: Optional[str] = None


def _ensure_stock_kline_data(db: Session, stock_code: str) -> None:
    stock = db.query(Stock).filter(Stock.code == stock_code).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{stock_code}' not found")

    latest_kline = (
        db.query(DailyKline)
        .filter(DailyKline.stock_code == stock_code)
        .order_by(DailyKline.date.desc())
        .first()
    )
    if latest_kline:
        return

    logger.info("No kline data for %s, syncing before analysis", stock_code)
    count, message = baostock_service.sync_kline_data(
        db=db,
        stock_codes=[stock_code],
        start_date="2020-01-01",
        end_date=datetime.now().strftime("%Y-%m-%d"),
    )
    logger.info(
        "Pre-analysis kline sync result for %s: %s (%s)", stock_code, count, message
    )

    latest_kline = (
        db.query(DailyKline)
        .filter(DailyKline.stock_code == stock_code)
        .order_by(DailyKline.date.desc())
        .first()
    )
    if latest_kline is None:
        raise RuntimeError(f"No kline data available for {stock_code} after sync")


def _persist_analysis(db: Session, request: AnalyzeRequest, result) -> AnalyzeResponse:
    news_items = _extract_news_items(result.stages)
    analysis_record = AnalysisRecord(
        stock_code=request.stock_code,
        stock_name=request.stock_name or request.stock_code,
        analysis_date=datetime.now().date(),
        mode=request.mode,
        final_signal=result.final_signal,
        final_confidence=result.final_confidence,
        final_reason=result.final_reason,
        opinions_json=json.dumps(result.opinions, ensure_ascii=False)
        if result.opinions
        else None,
        stages_json=json.dumps(result.stages, ensure_ascii=False)
        if result.stages
        else None,
        duration_s=result.duration_s,
        error=result.error,
    )
    db.add(analysis_record)
    db.commit()

    return AnalyzeResponse(
        success=result.success,
        stock_code=request.stock_code,
        stock_name=request.stock_name or request.stock_code,
        mode=request.mode,
        final_signal=result.final_signal,
        final_confidence=result.final_confidence,
        final_reason=result.final_reason,
        opinions=result.opinions,
        stages=result.stages,
        news_items=news_items,
        duration_s=result.duration_s,
        error=result.error,
    )


def _extract_news_items(stages: List[dict]) -> List[dict]:
    for stage in stages or []:
        if stage.get("stage_name") == "intel":
            meta = stage.get("meta") or {}
            news_items = meta.get("news_items")
            if isinstance(news_items, list):
                return news_items
    return []


def _run_analysis_job(job_id: str, request_data: dict) -> None:
    db = SessionLocal()
    try:
        request = AnalyzeRequest(**request_data)
        job_store.update(job_id, status="running", message="Running agent analysis")
        _ensure_stock_kline_data(db, request.stock_code)
        orchestrator = AgentOrchestrator(mode=request.mode)
        if not orchestrator.is_available:
            raise RuntimeError(
                "LLM service not available. Please check API key configuration."
            )

        result = orchestrator.run(
            stock_code=request.stock_code,
            stock_name=request.stock_name or request.stock_code,
        )
        payload = _persist_analysis(db, request, result)
        job_store.update(
            job_id,
            status="completed",
            progress=1.0,
            message="Analysis completed",
            result=payload.model_dump(),
        )
    except Exception as exc:
        logger.error(f"Async analysis failed: {exc}", exc_info=True)
        job_store.update(
            job_id, status="failed", error=str(exc), message="Analysis failed"
        )
    finally:
        db.close()


# Endpoints
@router.post("/agent/analyze", response_model=AnalyzeResponse)
def analyze_stock(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """执行股票分析"""
    try:
        _ensure_stock_kline_data(db, request.stock_code)
        # 初始化编排器
        orchestrator = AgentOrchestrator(mode=request.mode)

        # 检查 LLM 是否可用
        if not orchestrator.is_available:
            raise HTTPException(
                status_code=503,
                detail="LLM service not available. Please check API key configuration.",
            )

        # 执行分析
        result = orchestrator.run(
            stock_code=request.stock_code,
            stock_name=request.stock_name or request.stock_code,
        )

        return _persist_analysis(db, request, result)

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/analyze/submit", response_model=AnalyzeSubmitResponse)
def submit_analysis(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(get_current_api_key),
):
    job = job_store.create(job_type="agent_analysis", payload=request.model_dump())
    background_tasks.add_task(_run_analysis_job, job.id, request.model_dump())
    return AnalyzeSubmitResponse(
        job_id=job.id, status=job.status, message="Analysis queued"
    )


@router.get("/agent/history", response_model=List[AnalysisRecordResponse])
def get_analysis_history(
    stock_code: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """获取分析历史"""
    query = db.query(AnalysisRecord)

    if stock_code:
        query = query.filter(AnalysisRecord.stock_code == stock_code)

    records = (
        query.order_by(
            AnalysisRecord.analysis_date.desc(), AnalysisRecord.created_at.desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [AnalysisRecordResponse.model_validate(r) for r in records]


@router.get("/agent/{record_id}")
def get_analysis_detail(
    record_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """获取分析详情"""
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == record_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Analysis record not found")

    return {
        "id": record.id,
        "stock_code": record.stock_code,
        "stock_name": record.stock_name,
        "analysis_date": str(record.analysis_date),
        "mode": record.mode,
        "final_signal": record.final_signal,
        "final_confidence": record.final_confidence,
        "final_reason": record.final_reason,
        "opinions": json.loads(record.opinions_json) if record.opinions_json else [],
        "stages": json.loads(record.stages_json) if record.stages_json else [],
        "news_items": _extract_news_items(
            json.loads(record.stages_json) if record.stages_json else []
        ),
        "duration_s": record.duration_s,
        "error": record.error,
        "created_at": str(record.created_at),
    }


@router.get("/agent/indices", response_model=List[IndexInfo])
def get_index_list(_: str = Depends(get_current_api_key)):
    """获取大盘指数列表"""
    return MAJOR_INDICES


@router.post("/agent/market/analyze", response_model=MarketAnalyzeResponse)
def analyze_market(
    request: MarketAnalyzeRequest,
    _: str = Depends(get_current_api_key),
):
    """执行大盘分析"""
    start_time = time.time()

    try:
        # 确定要分析的指数列表
        if request.index_codes:
            indices_to_analyze = [
                idx for idx in MAJOR_INDICES if idx["code"] in request.index_codes
            ]
        else:
            indices_to_analyze = MAJOR_INDICES

        if not indices_to_analyze:
            return MarketAnalyzeResponse(
                success=False,
                indices=[],
                overall_signal="hold",
                overall_confidence=0.0,
                overall_reason="未选择有效指数",
                duration_s=time.time() - start_time,
                error="No valid indices selected",
            )

        # 初始化编排器
        orchestrator = AgentOrchestrator(mode=request.mode)

        # 检查 LLM 是否可用
        if not orchestrator.is_available:
            raise HTTPException(
                status_code=503,
                detail="LLM service not available. Please check API key configuration.",
            )

        # 获取最近30天的数据日期范围
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

        # 分析每个指数
        index_results = []
        for idx in indices_to_analyze:
            try:
                # 获取指数数据（用于构建提示词）
                df = baostock_service.get_index_daily_kline(
                    idx["code"], start_date, end_date
                )

                # 构建分析提示词
                prompt = _build_market_prompt(idx["name"], idx["code"], df)

                # 执行分析
                result = orchestrator.run(
                    stock_code=idx["code"], stock_name=idx["name"], query=prompt
                )

                index_results.append(
                    {
                        "code": idx["code"],
                        "name": idx["name"],
                        "success": result.success,
                        "signal": result.final_signal,
                        "confidence": result.final_confidence,
                        "reason": result.final_reason,
                        "error": result.error,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to analyze index {idx['code']}: {e}")
                index_results.append(
                    {
                        "code": idx["code"],
                        "name": idx["name"],
                        "success": False,
                        "signal": "hold",
                        "confidence": 0.0,
                        "reason": "",
                        "error": str(e),
                    }
                )

        # 计算综合信号
        buy_count = sum(1 for r in index_results if r["signal"] == "buy")
        sell_count = sum(1 for r in index_results if r["signal"] == "sell")
        _hold_count = sum(1 for r in index_results if r["signal"] == "hold")

        # 综合信号逻辑
        if buy_count > sell_count and buy_count >= len(index_results) * 0.6:
            overall_signal = "buy"
            overall_confidence = buy_count / len(index_results)
        elif sell_count > buy_count and sell_count >= len(index_results) * 0.6:
            overall_signal = "sell"
            overall_confidence = sell_count / len(index_results)
        else:
            overall_signal = "hold"
            overall_confidence = max(buy_count, sell_count) / len(index_results)

        # 生成综合理由
        overall_reason = _build_overall_reason(index_results, overall_signal)

        return MarketAnalyzeResponse(
            success=True,
            indices=index_results,
            overall_signal=overall_signal,
            overall_confidence=overall_confidence,
            overall_reason=overall_reason,
            duration_s=time.time() - start_time,
        )

    except Exception as e:
        logger.error(f"Market analysis failed: {e}", exc_info=True)
        return MarketAnalyzeResponse(
            success=False,
            indices=[],
            overall_signal="hold",
            overall_confidence=0.0,
            overall_reason="",
            duration_s=time.time() - start_time,
            error="Market analysis failed",
        )


def _build_market_prompt(index_name: str, index_code: str, df) -> str:
    """构建大盘分析提示词"""
    if df is None or df.empty:
        return f"请分析 {index_name}（{index_code}）的大盘走势。"

    # 获取最新数据
    latest = df.iloc[-1] if len(df) > 0 else None
    prev = df.iloc[-2] if len(df) > 1 else latest

    # 计算涨跌幅
    change_pct = 0.0
    if latest is not None and prev is not None and prev["close"] > 0:
        change_pct = (latest["close"] - prev["close"]) / prev["close"] * 100

    # 获取近期趋势
    recent_5 = df.tail(5)["close"].values
    trend = (
        "上涨"
        if recent_5[-1] > recent_5[0]
        else "下跌"
        if recent_5[-1] < recent_5[0]
        else "震荡"
    )

    # 获取成交量变化
    vol_change = 0.0
    if len(df) > 5 and df.tail(5)["volume"].iloc[:-1].mean() > 0:
        vol_change = (
            (df.tail(5)["volume"].iloc[-1] - df.tail(5)["volume"].iloc[:-1].mean())
            / df.tail(5)["volume"].iloc[:-1].mean()
            * 100
        )

    prompt = f"""你是一位专业的A股大盘分析师。请分析 {index_name}（{index_code}）的近期走势。

近期关键数据：
- 最新收盘价：{latest["close"] if latest is not None else "N/A"}
- 涨跌幅：{change_pct:.2f}%
- 近期趋势：{trend}
- 成交量变化：{vol_change:.1f}%

请提供以下分析：
1. 整体趋势判断（上涨/下跌/震荡）
2. 关键支撑位和阻力位
3. 均线系统分析
4. 技术指标信号（MACD, RSI等）
5. 后市展望

请以 JSON 格式返回：
{{
    "signal": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reason": "分析理由"
}}
"""
    return prompt


def _build_overall_reason(results: List[dict], overall_signal: str) -> str:
    """构建综合分析理由"""
    if not results:
        return "暂无足够数据进行综合分析"

    signal_summary = []
    for r in results:
        signal_summary.append(f"{r['name']}: {r['signal']}")

    if overall_signal == "buy":
        return f"多数指数呈上涨趋势。建议适度参与市场，关注成交量配合情况。具体来看：{', '.join(signal_summary)}"
    elif overall_signal == "sell":
        return f"多数指数呈下跌趋势，建议控制仓位观望。具体来看：{', '.join(signal_summary)}"
    else:
        return f"市场走势分化，建议保持中性仓位，关注结构性机会。具体来看：{', '.join(signal_summary)}"
