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
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.agent_chat.seam import RUN_LINKED, TURN_DONE, ChatEvent, HarnessChatSeam
from app.agent_chat.stores import ChatStores, create_chat_stores
from app.agent_chat.titles import clean_title, fallback_title, needs_title

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_thread_id() -> str:
    return f"thread-{uuid.uuid4().hex[:16]}"


def _new_turn_id() -> str:
    return f"turn-{uuid.uuid4().hex[:16]}"


class HarnessChatService:
    """多 worker 线程池 + 按 thread_id 串行 FIFO 聊天服务。

    - 同一 thread_id 内的消息严格 FIFO 串行执行，确保会话上下文时序安全；
    - 不同 thread_id 之间通过 ThreadPoolExecutor 并发处理，互不阻塞；
    - 活跃 turn 映射表支持多会话独立精准取消与状态追踪。
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        seam: HarnessChatSeam,
        max_workers: int = 4,
        title_generator: Callable[[str], str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._seam = seam
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None
        self._running = False
        # thread_id -> list[turn_id] (每个会话的待处理 FIFO 队列)
        self._pending_by_thread: dict[str, list[str]] = {}
        # active executing turns: session_id/thread_id -> turn_id
        self._active_turns: dict[str, str] = {}
        # 当前正在执行 turn 的 thread_id 集合
        self._running_threads: set[str] = set()
        self._lock = threading.Lock()
        self._title_generator = title_generator
        self._title_executor: ThreadPoolExecutor | None = None
        self._pending_titles: set[str] = set()

    def _stores(self) -> tuple[Session, ChatStores]:
        session = self._session_factory()
        return session, create_chat_stores(session)

    # ------------------------------------------------------------------ 生命周期
    def startup(self) -> None:
        if self._running:
            return
        self._running = True
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers, thread_name_prefix="harness-chat-worker"
        )
        if self._title_generator is not None:
            self._title_executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="chat-title-worker"
            )
        self._recover_interrupted()
        logger.info("HarnessChatService started with %d workers", self._max_workers)

    def shutdown(self) -> None:
        self._running = False
        if self._title_executor is not None:
            self._title_executor.shutdown(wait=True, cancel_futures=True)
            self._title_executor = None
        with self._lock:
            self._pending_titles.clear()
        self._seam.shutdown()
        with self._lock:
            self._pending_by_thread.clear()
            self._running_threads.clear()
            self._active_turns.clear()
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None
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

    def ensure_thread_title(self, thread: dict[str, Any]) -> bool:
        """Queue at most one title per chat, without calling a model in requests.

        List/detail reads also use this to backfill existing unnamed chats.
        Empty chats and already named/archived chats never incur model calls.
        """
        if not needs_title(thread.get("title")) or thread.get("archived"):
            return False
        thread_id = thread["thread_id"]
        with self._lock:
            if thread_id in self._pending_titles:
                return True
            if (
                not self._running
                or self._title_executor is None
                or len(self._pending_titles) >= 200
            ):
                return False
            session, stores = self._stores()
            try:
                latest = stores.threads.get_thread(thread_id)
                if latest is None or latest.get("archived"):
                    return False
                # A list request may hold a snapshot from before the worker
                # finished. Re-read before scheduling another provider call.
                thread["title"] = latest.get("title")
                if not needs_title(thread["title"]):
                    return False
                first_turn = stores.turns.first_turn(thread_id)
            finally:
                session.close()
            if first_turn is None or not first_turn["user_input"].strip():
                return False
            self._pending_titles.add(thread_id)
            self._title_executor.submit(
                self._generate_title,
                thread_id,
                thread.get("title"),
                first_turn["user_input"],
            )
            return True

    def _generate_title(
        self, thread_id: str, expected_title: str | None, user_input: str
    ) -> None:
        try:
            title = ""
            try:
                if self._title_generator is not None:
                    title = clean_title(self._title_generator(user_input))
            except Exception:
                # Provider exceptions can contain request/credential details.
                logger.warning("AI title generation failed for %s; using summary", thread_id)
            title = title or fallback_title(user_input)
            session, stores = self._stores()
            try:
                stores.threads.set_generated_title(
                    thread_id, title, expected_title=expected_title
                )
            finally:
                session.close()
        except Exception:
            logger.exception("Could not save conversation title for %s", thread_id)
        finally:
            with self._lock:
                self._pending_titles.discard(thread_id)

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
            self._enqueue_turn(thread_id, turn["turn_id"])
            thread = stores.threads.get_thread(thread_id)
            if thread is not None:
                self.ensure_thread_title(thread)
            return turn
        finally:
            session.close()

    def stop_turn(self, thread_id: str) -> None:
        """请求取消当前活动 turn；native runtime 使用协作式取消令牌。"""
        with self._lock:
            if thread_id not in self._active_turns:
                raise ValueError("该会话当前没有正在执行的 turn")
        self._seam.stop(thread_id)

    def status(self) -> dict[str, Any]:
        """返回聊天 runtime 的脱敏可用状态。"""
        value = getattr(self._seam, "status", None)
        if isinstance(value, dict):
            return dict(value)
        return {"backend": "fake", "available": True, "reason": None}

    # ------------------------------------------------------------------ worker 调度
    def _enqueue_turn(self, thread_id: str, turn_id: str) -> None:
        with self._lock:
            if not self._running:
                return
            if thread_id in self._running_threads:
                # 该 thread 当前正在执行 turn，入队排队等待（保证单 thread 严格 FIFO）
                self._pending_by_thread.setdefault(thread_id, []).append(turn_id)
            else:
                # 该 thread 空闲，立即标记并提交线程池异步执行（不同 thread 并发）
                self._running_threads.add(thread_id)
                if self._executor is not None:
                    self._executor.submit(self._run_turn_worker, thread_id, turn_id)

    def _run_turn_worker(self, thread_id: str, turn_id: str) -> None:
        try:
            self._execute_turn(turn_id)
        except Exception:
            logger.exception("turn %s 执行异常", turn_id)
            self._mark_failed(turn_id)
        finally:
            self._on_turn_completed(thread_id)

    def _on_turn_completed(self, thread_id: str) -> None:
        with self._lock:
            if not self._running:
                self._running_threads.discard(thread_id)
                self._pending_by_thread.pop(thread_id, None)
                return
            pending = self._pending_by_thread.get(thread_id)
            if pending:
                next_turn_id = pending.pop(0)
                if not pending:
                    self._pending_by_thread.pop(thread_id, None)
                if self._executor is not None:
                    self._executor.submit(self._run_turn_worker, thread_id, next_turn_id)
            else:
                self._running_threads.discard(thread_id)

    def _execute_turn(self, turn_id: str) -> None:
        session, stores = self._stores()
        turn = None
        thread = None
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
            with self._lock:
                self._active_turns[session_id] = turn["turn_id"]
                self._active_turns[turn["thread_id"]] = turn["turn_id"]
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
            with self._lock:
                if turn is not None:
                    self._active_turns.pop(turn["thread_id"], None)
                    if thread is not None:
                        sid = thread["session_id"] or thread["thread_id"]
                        self._active_turns.pop(sid, None)
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
                self._enqueue_turn(t["thread_id"], t["turn_id"])
        finally:
            session.close()
