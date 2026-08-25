# backend/app/api/screener_agent.py

import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.agent.orchestrator import AgentOrchestrator
from app.auth import get_current_api_key
from app.config import SessionLocal
from app.exceptions import NotFoundError
from app.limiter import limiter
from app.models.models import Stock
from app.services.job_store import job_store
from app.services.screener_service import screener_service
from app.services.tasks import get_task_executor, register_runner

logger = logging.getLogger(__name__)
router = APIRouter()


def run_orchestrator_with_timeout(
    orchestrator: AgentOrchestrator,
    stock_code: str,
    stock_name: str,
    timeout_s: int = 120,
) -> Optional[AgentOrchestrator]:
    """Run orchestrator with a timeout using threading."""
    result = [None]
    error = [None]

    def target():
        try:
            result[0] = orchestrator.run(
                stock_code=stock_code,
                stock_name=stock_name,
                progress_callback=None,
            )
        except Exception as exc:
            error[0] = exc

    t = threading.Thread(target=target)
    t.start()
    t.join(timeout_s)
    # 先检查 error —— 如果线程恰好在超时瞬间完成并报错，error[0] 已设置但
    # is_alive() 可能仍为 True，旧顺序会丢失异常信息。
    if error[0]:
        raise error[0]
    if t.is_alive():
        logger.warning("AI analysis timed out for %s after %ss", stock_code, timeout_s)
        return None
    return result[0]


class ScreenerSubmitResponse(BaseModel):
    job_id: str


@register_runner("screener")
def run_screener_job(job_id: str, payload: dict) -> None:
    """后台执行全市场选股 + TOP5 AI 深度分析（协作式取消）。"""
    db = SessionLocal()

    def _check_cancelled():
        """检查 job 是否被用户取消 —— 避免与 cancel_job 端点的竞态条件。"""
        record = job_store.get(job_id)
        return bool(record and record.status in ("failed", "cancelled") and "cancelled" in (record.error or ""))

    def _safe_update(**changes):
        """取消后不再写入更新，避免覆盖取消状态。"""
        if _check_cancelled():
            return
        job_store.update(job_id, **changes)

    try:
        def progress_callback(stage: str, current: int, total: int, message: str):
            _safe_update(
                status="running",
                progress=current / total if total else 0,
                payload={
                    "stage": stage, "current": current, "total": total,
                    "message": message,
                },
            )

        # 加载股票列表
        _safe_update(
            status="running", progress=0,
            payload={
                "stage": "scanning", "current": 0, "total": 0,
                "message": "正在加载股票列表...",
            },
        )

        stocks = db.query(Stock).all()
        logger.info("Screener job %s: loaded %d stocks", job_id, len(stocks))

        # 阶段1: 并行扫描
        progress_callback(
            "scanning", 0, len(stocks), f"正在扫描全市场股票... (0/{len(stocks)})"
        )
        scan_results = screener_service.parallel_scan_stocks(
            stocks, offset=120, max_workers=10,
            progress_callback=progress_callback,
        )
        logger.info(
            "Screener job %s: scanned %d stocks with data", job_id, len(scan_results)
        )

        # 阶段2: 过滤排序
        progress_callback("scoring", 0, 1, "正在综合评分排序...")
        top5 = screener_service.filter_and_rank(
            scan_results, progress_callback=progress_callback
        )
        logger.info(
            "Screener job %s: top 5 = %s",
            job_id, [s["stock_code"] for s in top5],
        )

        # 阶段3: AI 深度分析 TOP 5
        orchestrator = AgentOrchestrator(mode="full")

        for i, stock in enumerate(top5):
            progress_callback(
                "ai_analysis",
                i + 1,
                5,
                f" AI 深度分析中 ({i+1}/5): {stock['stock_name']}",
            )

            try:
                result = run_orchestrator_with_timeout(
                    orchestrator,
                    stock["stock_code"],
                    stock["stock_name"],
                    timeout_s=120,
                )
                if result is None:
                    stock["ai_signal"] = "hold"
                    stock["ai_confidence"] = 0.0
                    stock["ai_reason"] = "AI 分析超时 (120s)"
                    continue
                stock["ai_signal"] = result.final_signal
                stock["ai_confidence"] = result.final_confidence
                stock["ai_reason"] = (
                    result.final_reason if result.final_reason else "AI 分析完成"
                )
                logger.info(
                    "Screener AI: %s -> signal=%s, confidence=%.2f",
                    stock["stock_code"], result.final_signal, result.final_confidence,
                )
            except Exception as exc:
                logger.error(
                    "AI analysis failed for %s", stock["stock_code"], exc_info=exc
                )
                stock["ai_signal"] = "hold"
                stock["ai_confidence"] = 0.0
                stock["ai_reason"] = f"AI 分析失败: {exc!s}"

        # 完成
        _safe_update(
            status="completed", progress=1.0,
            result={
                "success": True,
                "total_scanned": len(scan_results),
                "results": top5,
                "execution_time_s": 0,  # TODO: compute actual time
            },
        )

    except Exception as exc:
        logger.exception("Screener job %s failed", job_id)
        _safe_update(status="failed", error=str(exc))
    finally:
        db.close()


@router.post("/screener/submit", response_model=ScreenerSubmitResponse)
@limiter.limit("10/minute")
def submit_screener_job(
    request: Request,
    _: str = Depends(get_current_api_key),
):
    """提交一次新的选股任务并返回 job_id。

    前端在任务运行期间不会重复提交；完成后的“重新选股”必须创建新任务，
    不能复用当天较早的行情与筛选结果。
    """
    job = get_task_executor().submit(job_type="screener")
    return ScreenerSubmitResponse(job_id=job.id)


@router.get("/screener/{job_id}")
def get_screener_job_status(
    job_id: str,
    _: str = Depends(get_current_api_key),
):
    """查询选股任务状态和结果"""
    job = job_store.get(job_id)
    if not job:
        raise NotFoundError(detail="Job not found")
    return job
