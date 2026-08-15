"""Agent 运行时 API 路由（任务 06）。

- POST   /api/v1/agent-runs                创建 run（可选同步执行）
- GET    /api/v1/agent-runs                列表（可选 status 过滤）
- GET    /api/v1/agent-runs/{run_id}       状态
- GET    /api/v1/agent-runs/{run_id}/events SSE 事件流（Last-Event-ID 重放）
- POST   /api/v1/agent-runs/{run_id}/resume 恢复执行（?wait=true 同步等待）
- POST   /api/v1/agent-runs/{run_id}/cancel 请求取消
- GET    /api/v1/agent-runs/{run_id}/artifacts 产物列表
"""

import json
import logging
import threading
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agent_api.pipelines import default_pipeline
from app.agent_api.schemas import CreateRunRequest, RunListResponse, RunResponse
from app.agent_runtime.events import iter_run_events
from app.agent_runtime.runtime import CancelToken, RunExecutor
from app.agent_runtime.stores import create_stores
from app.auth import get_current_api_key
from app.config import SessionLocal, get_db

logger = logging.getLogger(__name__)

router = APIRouter()

#: 进程内取消注册表（进程重启后以 run 状态为准）
_cancel_tokens: dict[str, CancelToken] = {}
_tokens_lock = threading.Lock()


def _cancel_token(run_id: str) -> CancelToken:
    with _tokens_lock:
        token = _cancel_tokens.get(run_id)
        if token is None:
            token = CancelToken()
            _cancel_tokens[run_id] = token
        return token


def _spawn_execution(run_id: str, objective: str, strategy_params: dict | None = None) -> None:
    """后台线程执行（threads 后端；生产可换独立 worker，见规格决策 6 备注）。"""

    def _run() -> None:
        session = SessionLocal()
        try:
            stores = create_stores(session)
            executor = RunExecutor(stores, db=session, cancel_token=_cancel_token(run_id))
            executor.execute(
                run_id,
                default_pipeline(objective, strategy_params=strategy_params),
            )
        except Exception:
            logger.exception("run %s 后台执行异常", run_id)
        finally:
            session.close()

    threading.Thread(target=_run, daemon=True, name=f"agent-run-{run_id}").start()


def _require_run(db: Session, run_id: str) -> dict:
    run = create_stores(db).runs.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} 不存在")
    return run


@router.post("/agent-runs", response_model=RunResponse, status_code=201)
def create_run(
    payload: CreateRunRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    stores = create_stores(db)
    executor = RunExecutor(stores, db=db)
    run_id = executor.create_run(
        payload.objective,
        budget=payload.budget,
        thread_id=payload.thread_id,
        snapshot_id=payload.snapshot_id,
    )
    token = _cancel_token(run_id)
    if payload.execute_inline:
        executor = RunExecutor(stores, db=db, cancel_token=token)
        final = executor.execute(
            run_id,
            default_pipeline(payload.objective, strategy_params=payload.strategy_params),
        )
    else:
        _spawn_execution(
            run_id, payload.objective, strategy_params=payload.strategy_params
        )
        final = stores.runs.get_run(run_id)
    return RunResponse(
        run_id=run_id,
        status=final["status"],
        events_url=f"/api/v1/agent-runs/{run_id}/events",
    )


@router.get("/agent-runs", response_model=RunListResponse)
def list_runs(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    runs = create_stores(db).runs.list_runs(status=status, limit=limit, offset=offset)
    return RunListResponse(total=len(runs), runs=runs)


@router.get("/agent-runs/{run_id}")
def get_run(
    run_id: str,
    include_steps: bool = Query(default=True, description="附带节点输出（工作台研究面板数据源）"),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """run 详情；``include_steps=false`` 时只返回 run 记录（兼容列表语义）。"""
    run = _require_run(db, run_id)
    if not include_steps:
        return run
    stores = create_stores(db)
    run["steps"] = stores.steps.list_steps(run_id)
    return run


@router.get("/agent-runs/{run_id}/events")
def stream_events(
    run_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    _require_run(db, run_id)
    stores = create_stores(db)

    def generate():
        last_id = 0
        raw = request.headers.get("last-event-id")
        if raw and raw.isdigit():
            last_id = int(raw)
        while True:
            events = iter_run_events(stores, run_id)
            for idx, event in enumerate(events, start=1):
                if idx <= last_id:
                    continue
                payload = json.dumps(event, ensure_ascii=False)
                yield f"id: {idx}\ndata: {payload}\n\n"
                last_id = idx
            run = stores.runs.get_run(run_id)
            if run["status"] in ("completed", "failed", "cancelled", "superseded"):
                yield "event: done\ndata: {}\n\n"
                break
            time.sleep(0.5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent-runs/{run_id}/resume")
def resume_run(
    run_id: str,
    wait: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    _require_run(db, run_id)
    stores = create_stores(db)
    run = stores.runs.get_run(run_id)
    objective = run["objective"]
    executor = RunExecutor(stores, db=db, cancel_token=_cancel_token(run_id))
    if wait:
        return executor.execute(run_id, default_pipeline(objective))
    _spawn_execution(run_id, objective)
    return stores.runs.get_run(run_id)


@router.post("/agent-runs/{run_id}/cancel")
def cancel_run(
    run_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    _require_run(db, run_id)
    _cancel_token(run_id).request(run_id)
    return create_stores(db).runs.get_run(run_id)


@router.get("/agent-runs/{run_id}/artifacts")
def list_artifacts(
    run_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    _require_run(db, run_id)
    return {"run_id": run_id, "artifacts": create_stores(db).artifacts.list_artifacts(run_id)}


@router.get("/agent-runs/{run_id}/artifacts/{artifact_id}/download")
def download_artifact(
    run_id: str,
    artifact_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """下载产物工作区文件（US-2.9；内容与记录一致）。"""
    from fastapi.responses import JSONResponse

    from app.agent_runtime.artifacts import filename_of, read_artifact
    from app.models.agent_runtime import ArtifactRecord

    _require_run(db, run_id)
    record = db.get(ArtifactRecord, artifact_id)
    if record is None or record.run_id != run_id:
        raise HTTPException(status_code=404, detail="产物不存在")
    content = read_artifact(run_id, filename_of(record.uri))
    if content is None:
        raise HTTPException(status_code=404, detail="产物文件缺失")
    try:
        return JSONResponse(content=json.loads(content))
    except json.JSONDecodeError:
        return JSONResponse(content={"raw": content})
