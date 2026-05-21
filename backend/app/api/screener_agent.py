# backend/app/api/screener_agent.py

import logging
import threading
import time
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_api_key
from app.limiter import limiter
from app.services.screener_service import screener_service
from app.services.job_store import job_store
from app.agent.orchestrator import AgentOrchestrator
from app.config import SessionLocal
from app.models.models import Stock

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
                progress_callback=None
            )
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=target)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        logger.warning(f"AI analysis timed out for {stock_code} after {timeout_s}s")
        return None
    if error[0]:
        raise error[0]
    return result[0]


class ScreenerSubmitResponse(BaseModel):
    job_id: str


@router.post("/screener/submit", response_model=ScreenerSubmitResponse)
@limiter.limit("2/minute")
def submit_screener_job(
    _: str = Depends(get_current_api_key),
):
    """提交选股任务，返回 job_id"""
    job_id = f"screener_{int(time.time() * 1000)}"

    # 初始化 job 状态
    job_store.update(job_id, status='pending', progress=0.0,
                      payload={'stage': 'initializing', 'current': 0, 'total': 0,
                               'message': '正在初始化...'})

    def run_job():
        db = SessionLocal()
        try:
            def progress_callback(stage: str, current: int, total: int, message: str):
                job_store.update(job_id, status='running', progress=current / total if total else 0,
                                  payload={'stage': stage, 'current': current, 'total': total, 'message': message})

            # 加载股票列表
            job_store.update(job_id, status='running', progress=0,
                              payload={'stage': 'scanning', 'current': 0, 'total': 0,
                                       'message': '正在加载股票列表...'})

            stocks = db.query(Stock).all()
            logger.info(f"Screener job {job_id}: loaded {len(stocks)} stocks")

            # 阶段1: 并行扫描
            progress_callback('scanning', 0, len(stocks), f'正在扫描全市场股票... (0/{len(stocks)})')
            scan_results = screener_service.parallel_scan_stocks(
                stocks, offset=120, max_workers=10,
                progress_callback=progress_callback
            )
            logger.info(f"Screener job {job_id}: scanned {len(scan_results)} stocks with data")

            # 阶段2: 过滤排序
            progress_callback('scoring', 0, 1, '正在综合评分排序...')
            top5 = screener_service.filter_and_rank(scan_results, progress_callback=progress_callback)
            logger.info(f"Screener job {job_id}: top 5 = {[s['stock_code'] for s in top5]}")

            # 阶段3: AI 深度分析 TOP 5
            orchestrator = AgentOrchestrator(mode='full')

            for i, stock in enumerate(top5):
                progress_callback(
                    'ai_analysis',
                    i + 1,
                    5,
                    f' AI 深度分析中 ({i+1}/5): {stock["stock_name"]}'
                )

                try:
                    result = run_orchestrator_with_timeout(
                        orchestrator,
                        stock['stock_code'],
                        stock['stock_name'],
                        timeout_s=120
                    )
                    if result is None:
                        stock['ai_signal'] = 'hold'
                        stock['ai_confidence'] = 0.0
                        stock['ai_reason'] = 'AI 分析超时 (120s)'
                        continue
                    stock['ai_signal'] = result.final_signal
                    stock['ai_confidence'] = result.final_confidence
                    stock['ai_reason'] = result.final_reason if result.final_reason else 'AI 分析完成'
                    logger.info(f"Screener AI: {stock['stock_code']} -> signal={result.final_signal}, confidence={result.final_confidence:.2f}")
                except Exception as e:
                    logger.error(f"AI analysis failed for {stock['stock_code']}: {e}")
                    stock['ai_signal'] = 'hold'
                    stock['ai_confidence'] = 0.0
                    stock['ai_reason'] = f'AI 分析失败: {str(e)}'

            # 完成
            job_store.update(job_id, status='completed', progress=1.0,
                              result={
                                  'success': True,
                                  'total_scanned': len(scan_results),
                                  'results': top5,
                                  'execution_time_s': 0,  # TODO: compute actual time
                              })

        except Exception as e:
            logger.error(f"Screener job {job_id} failed: {e}")
            job_store.update(job_id, status='failed', error=str(e))
        finally:
            db.close()

    # 后台线程执行
    t = threading.Thread(target=run_job, daemon=True)
    t.start()

    return ScreenerSubmitResponse(job_id=job_id)


@router.get("/screener/{job_id}")
def get_screener_job_status(
    job_id: str,
    _: str = Depends(get_current_api_key),
):
    """查询选股任务状态和结果"""
    job = job_store.get(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job