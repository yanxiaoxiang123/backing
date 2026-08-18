"""Agent 聊天 API 路由（规格决策 D8，挂 /api/v1/agent-chats）。

- POST   /agent-chats                创建会话
- GET    /agent-chats                分页未归档会话
- GET    /agent-chats/{thread_id}    恢复 turn 与事件历史
- POST   /agent-chats/{thread_id}/turns  提交消息（Idempotency-Key）
- GET    /agent-chats/{thread_id}/events SSE（Last-Event-ID 重放，长连接）
- POST   /agent-chats/{thread_id}/cancel  停止当前 turn
- POST   /agent-chats/{thread_id}/archive 软归档

认证沿用 get_current_api_key；CSRF 由中间件统一处理；服务实例挂在
app.state.harness_chat_service（lifespan 启动/关闭）。
"""

import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent_chat.service import HarnessChatService
from app.agent_chat.stores import create_chat_stores
from app.auth import get_current_api_key
from app.config import get_db

router = APIRouter()


class SubmitTurnRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _thread_response(thread: dict[str, Any]) -> dict[str, Any]:
    return {
        "thread_id": thread["thread_id"],
        "title": thread.get("title"),
        "status": thread["status"],
        "last_run_id": thread.get("last_run_id"),
        "archived": bool(thread.get("archived", False)),
        "created_at": _iso(thread.get("created_at")),
        "updated_at": _iso(thread.get("updated_at")),
    }


def _turn_response(turn: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": turn["id"],
        "thread_id": turn["thread_id"],
        "content": turn["user_input"],
        "status": turn["status"],
        "final_reply": turn.get("final_reply"),
        "end_reason": turn.get("finish_reason"),
        "error": turn.get("error"),
        "created_at": _iso(turn.get("created_at")),
    }


def _service(request: Request) -> HarnessChatService:
    return request.app.state.harness_chat_service


def _require_thread(db: Session, thread_id: str) -> None:
    if create_chat_stores(db).threads.get_thread(thread_id) is None:
        raise HTTPException(status_code=404, detail=f"会话 {thread_id} 不存在")


@router.post("/agent-chats", status_code=201)
def create_chat(
    request: Request, _: str = Depends(get_current_api_key)
):
    thread = _service(request).create_thread()
    return _thread_response(thread)


@router.get("/agent-chats")
def list_chats(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    stores = create_chat_stores(db)
    threads = stores.threads.list_threads(limit=limit, offset=offset)
    return {
        "threads": [_thread_response(t) for t in threads],
        "total": stores.threads.count_threads(),
    }


@router.get("/agent-chats/{thread_id}")
def get_chat(
    thread_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    _require_thread(db, thread_id)
    stores = create_chat_stores(db)
    thread = stores.threads.get_thread(thread_id)
    turns = stores.turns.list_turns(thread_id)
    return {
        "thread": _thread_response(thread),
        "turns": [_turn_response(t) for t in turns],
    }


@router.post("/agent-chats/{thread_id}/turns", status_code=202)
def submit_turn(
    thread_id: str,
    payload: SubmitTurnRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    _require_thread(db, thread_id)
    idempotency_key = request.headers.get("Idempotency-Key")
    turn = _service(request).submit_turn(
        thread_id, payload.content, idempotency_key=idempotency_key
    )
    return {"turn": _turn_response(turn)}


@router.get("/agent-chats/{thread_id}/events")
def stream_events(
    thread_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    _require_thread(db, thread_id)

    def generate():
        last_id = 0
        raw = request.headers.get("last-event-id")
        if raw and raw.isdigit():
            last_id = int(raw)
        idle_polls = 0
        while True:
            stores = create_chat_stores(db)
            events = stores.events.list_events(thread_id, after_id=last_id)
            for event in events:
                idle_polls = 0
                payload = dict(event["payload"])
                payload["turn_id"] = event["turn_pk"]
                frame = (
                    f"id: {event['id']}\n"
                    f"event: {event['event_type']}\n"
                    f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                )
                yield frame
                last_id = event["id"]
            # 空闲关闭：线程无 queued/running turn 且约 1.5s 无新事件则结束流。
            # 前端 ChatEventStream 断开后带 Last-Event-ID 自动重连（与 run SSE 同模式）。
            thread = stores.threads.get_thread(thread_id)
            turns = stores.turns.list_turns(thread_id)
            has_active = any(
                t["status"] in ("queued", "running") for t in turns
            )
            if thread is not None and not has_active:
                idle_polls += 1
                if idle_polls >= 3:
                    break
            else:
                idle_polls = 0
            time.sleep(0.5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent-chats/{thread_id}/cancel")
def cancel_turn(
    thread_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    _require_thread(db, thread_id)
    _service(request).stop_turn(thread_id)
    turns = create_chat_stores(db).turns.list_turns(thread_id)
    if not turns:
        raise HTTPException(status_code=404, detail="该会话没有进行中的 turn")
    return {"turn": _turn_response(turns[-1])}


@router.post("/agent-chats/{thread_id}/archive")
def archive_chat(
    thread_id: str,
    request: Request,
    _: str = Depends(get_current_api_key),
):
    thread = _service(request).archive_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=f"会话 {thread_id} 不存在")
    return _thread_response(thread)
