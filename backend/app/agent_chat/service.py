"""HarnessChatService 单例（规格决策 D6/D7）。

- FastAPI lifespan 启动/关闭；单 worker 按 FIFO 串行执行 turn（同实例同时
  只执行一个 turn，保障 SDK 生命周期、取消与 SQLite 写入安全）。
- 运行中提交的消息进入队列；``Idempotency-Key`` 去重返回原 turn。
- 重启恢复：running -> interrupted（不自动重复提交）；queued 继续执行。
- cancel：仅调用当前活动 thread 的 ``seam.stop(session_id)``，当前 turn 以 cancelled 收尾，队列保留。
- 事件（reasoning/assistant_chunk/tool_call/tool_result/run.linked/turn.done）
  按序落 ``agent_chat_events``，SSE 可按事件行 id 做 Last-Event-ID 重放。
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.agent_chat.seam import RUN_LINKED, TURN_DONE, ChatEvent, HarnessChatSeam
from app.agent_chat.stores import ChatStores, create_chat_stores

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_thread_id() -> str:
    return f"thread-{uuid.uuid4().hex[:16]}"


def _new_turn_id() -> str:
    return f"turn-{uuid.uuid4().hex[:16]}"


class HarnessChatService:
    """单 worker FIFO 聊天服务（构造后由 lifespan 调 startup/shutdown）。"""

    def __init__(self, session_factory: SessionFactory, seam: HarnessChatSeam) -> None:
        self._session_factory = session_factory
        self._seam = seam
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._running = False
        self._active_session_id: str | None = None
        self._active_turn_id: str | None = None
        self._active_lock = threading.Lock()

    def _stores(self) -> tuple[Session, ChatStores]:
        session = self._session_factory()
        return session, create_chat_stores(session)

    # ------------------------------------------------------------------ 生命周期
    def startup(self) -> None:
        if self._running:
            return
        self._running = True
        self._recover_interrupted()
        self._worker = threading.Thread(
            target=self._worker_loop, daemon=True, name="harness-chat-worker"
        )
        self._worker.start()
        logger.info("HarnessChatService started")

    def shutdown(self) -> None:
        self._running = False
        self._queue.put(None)  # poison pill
        self._seam.shutdown()
        if self._worker is not None:
            self._worker.join(timeout=5)
            self._worker = None
        logger.info("HarnessChatService stopped")

    # ------------------------------------------------------------------ 会话
    def create_thread(self, title: str | None = None) -> dict[str, Any]:
        session, stores = self._stores()
        try:
            thread_id = _new_thread_id()
            return stores.threads.create_thread(
                thread_id=thread_id,
                session_id=thread_id,
                title=title,
                status="idle",
                archived=False,
            )
        finally:
            session.close()

    def archive_thread(self, thread_id: str) -> dict[str, Any] | None:
        session, stores = self._stores()
        try:
            if not stores.threads.update_thread(thread_id, archived=True):
                return None
            return stores.threads.get_thread(thread_id)
        finally:
            session.close()

    # ------------------------------------------------------------------ turn
    def submit_turn(
        self,
        thread_id: str,
        content: str,
        idempotency_key: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session, stores = self._stores()
        try:
            if idempotency_key:
                existing = stores.turns.get_turn_by_idempotency(idempotency_key)
                if existing is not None:
                    return existing
            turn = stores.turns.create_turn(
                turn_id=_new_turn_id(),
                thread_id=thread_id,
                user_input=content,
                context_json=context,
                status="queued",
                idempotency_key=idempotency_key,
            )
            stores.threads.update_thread(thread_id, status="running")
            self._queue.put(turn["turn_id"])
            return turn
        finally:
            session.close()

    def stop_turn(self, thread_id: str) -> None:
        """请求取消当前活动 turn；native runtime 使用协作式取消令牌。"""
        with self._active_lock:
            if self._active_session_id != thread_id:
                raise ValueError("该会话当前没有正在执行的 turn")
        self._seam.stop(thread_id)

    def status(self) -> dict[str, Any]:
        """返回聊天 runtime 的脱敏可用状态。"""
        value = getattr(self._seam, "status", None)
        if isinstance(value, dict):
            return dict(value)
        return {"backend": "fake", "available": True, "reason": None}

    # ------------------------------------------------------------------ worker
    def _worker_loop(self) -> None:
        while self._running:
            turn_id = self._queue.get()
            if turn_id is None:
                break
            try:
                self._execute_turn(turn_id)
            except Exception:
                logger.exception("turn %s 执行异常", turn_id)
                self._mark_failed(turn_id)

    def _execute_turn(self, turn_id: str) -> None:
        session, stores = self._stores()
        try:
            turn = stores.turns.get_turn(turn_id)
            if turn is None:
                return
            thread = stores.threads.get_thread(turn["thread_id"])
            if thread is None:
                return
            session_id = thread["session_id"] or thread["thread_id"]

            stores.turns.update_turn_status(
                turn_id, "running", started_at=_now_iso()
            )
            with self._active_lock:
                self._active_session_id = session_id
                self._active_turn_id = turn["turn_id"]
            seq_holder = [0]
            done_holder = [False]

            def persist(event: Any) -> None:
                seq_holder[0] += 1
                stores.events.create_event(
                    turn_id=turn["turn_id"],
                    seq=seq_holder[0],
                    event_type=event.type,
                    payload=event.payload,
                )
                if event.type == RUN_LINKED:
                    run_id = event.payload.get("run_id")
                    if run_id:
                        stores.threads.update_thread(
                            turn["thread_id"], last_run_id=run_id
                        )
                if event.type == TURN_DONE:
                    done_holder[0] = True

            seam_kwargs: dict[str, Any] = {"turn_id": turn["id"], "emit": persist}
            if turn.get("context_json"):
                seam_kwargs["context"] = turn["context_json"]
            outcome = self._seam.run_turn(session_id, turn["user_input"], **seam_kwargs)
            # 无 turn.done 的终态（如取消/异常）补发合成终态事件，SSE 前端可靠收口
            if not done_holder[0]:
                persist(
                    ChatEvent(
                        TURN_DONE,
                        turn["id"],
                        {
                            "status": outcome.status,
                            "final_reply": outcome.final_reply,
                            "end_reason": outcome.end_reason,
                            "error": outcome.error,
                        },
                    )
                )
            stores.turns.update_turn_status(
                turn_id,
                outcome.status,
                final_reply=outcome.final_reply or None,
                finish_reason=outcome.end_reason,
                error=outcome.error,
                finished_at=_now_iso(),
            )
            stores.threads.update_thread(turn["thread_id"], status="idle")
        finally:
            with self._active_lock:
                if self._active_turn_id == turn_id:
                    self._active_session_id = None
                    self._active_turn_id = None
            session.close()

    def _mark_failed(self, turn_id: str) -> None:
        try:
            session, stores = self._stores()
            try:
                turn = stores.turns.get_turn(turn_id)
                if turn is not None:
                    stores.turns.update_turn_status(
                        turn_id,
                        "failed",
                        finish_reason="error",
                        error="服务端执行异常",
                        finished_at=_now_iso(),
                    )
                    stores.threads.update_thread(turn["thread_id"], status="idle")
            finally:
                session.close()
        except Exception:
            logger.exception("标记 turn %s 失败时出错", turn_id)

    # ------------------------------------------------------------------ 恢复
    def _recover_interrupted(self) -> None:
        session, stores = self._stores()
        try:
            for t in stores.turns.list_turns_by_status(["running"]):
                stores.turns.update_turn_status(
                    t["turn_id"], "interrupted", finish_reason="restart"
                )
                stores.threads.update_thread(t["thread_id"], status="idle")
            for t in stores.turns.list_turns_by_status(["queued"]):
                self._queue.put(t["turn_id"])
        finally:
            session.close()
