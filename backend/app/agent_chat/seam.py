"""Agent 聊天 Harness 接缝（规格决策 D1/D2）。

- ``HarnessChatSeam``：抽象接缝，真实 ``DeepSeekHarness`` 适配器与 fake 的公共接口。
- ``FakeHarnessChatSeam``：确定性 fake，产出 reasoning / assistant_chunk /
  tool_call / tool_result / run.linked / turn.done 事件；``quant_run_analysis``
  工具调用经 ``agent_runtime`` stores 真实创建 run（写 thread_id 关联会话）
  后发布 ``run.linked``，供右栏 attach。

真实适配器延后：需构建 DSH 运行时 + ``pip install -e`` SDK + 密钥
（dsh-quant-plugin/README.md 启动路径；Q1：quant_run_analysis 工具签名先以本文件为准）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from sqlalchemy.orm import Session

from app.agent_runtime.stores import create_stores

# 事件类型（与前端 frontend/src/types/chat.ts ChatEventType 契约一致）
REASONING = "reasoning"
ASSISTANT_CHUNK = "assistant_chunk"
TOOL_CALL = "tool_call"
TOOL_RESULT = "tool_result"
RUN_LINKED = "run.linked"
TURN_DONE = "turn.done"
ERROR = "error"


@dataclass
class ChatEvent:
    """可重放聊天事件。payload 键与前端契约对应：content/tool/args/summary/run_id/status/..."""

    type: str
    turn_id: int
    payload: dict[str, Any]


@dataclass
class TurnOutcome:
    """一轮 turn 的终态（服务层持久化到 agent_chat_turns）。"""

    status: str  # completed | failed | cancelled
    final_reply: str
    end_reason: str | None = None
    error: str | None = None


EmitFn = Callable[[ChatEvent], None]


class HarnessChatSeam(Protocol):
    """与真实 DeepSeekHarness 适配器共享的接缝接口。

    ``run_turn`` 同步阻塞，通过 ``emit`` 回调按序产出事件；返回该轮终态。
    ``stop`` 请求终止当前会话 turn（SDK 无单会话 cancel，真实适配器在服务层
    终止并重建 runtime 等价物；fake 以取消标记模拟）。
    """

    def run_turn(
        self, session_id: str, user_message: str, *, turn_id: int, emit: EmitFn
    ) -> TurnOutcome: ...

    def stop(self, session_id: str) -> None: ...

    def shutdown(self) -> None: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FakeHarnessChatSeam:
    """确定性 fake：模拟推理/助手回复/量化工具调用，并真实创建 run。

    ``session_factory``：零参工厂返回 ``Session``（服务层注入；每次建会话
    用完即关，避免 SQLite 连接泄漏）。同输入产出同事件序列（run_id 由
    session+turn 确定性派生），满足可重放测试要求。
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._cancelled: set[str] = set()

    def stop(self, session_id: str) -> None:
        self._cancelled.add(session_id)

    def shutdown(self) -> None:
        self._cancelled.clear()

    def run_turn(
        self, session_id: str, user_message: str, *, turn_id: int, emit: EmitFn
    ) -> TurnOutcome:
        emit(
            ChatEvent(
                REASONING,
                turn_id,
                {"content": f"分析用户请求：{user_message[:40]}"},
            )
        )
        if self._check_cancelled(session_id):
            return self._cancelled_outcome()
        emit(ChatEvent(ASSISTANT_CHUNK, turn_id, {"content": "我将发起一次量化分析。"}))
        if self._check_cancelled(session_id):
            return self._cancelled_outcome()

        run_id = self._create_quant_run(session_id, turn_id, user_message)
        emit(
            ChatEvent(
                TOOL_CALL,
                turn_id,
                {"tool": "quant_run_analysis", "args": {"objective": user_message}},
            )
        )
        emit(
            ChatEvent(
                TOOL_RESULT,
                turn_id,
                {
                    "tool": "quant_run_analysis",
                    "summary": "分析 run 已创建",
                    "run_id": run_id,
                },
            )
        )
        emit(ChatEvent(RUN_LINKED, turn_id, {"run_id": run_id}))

        reply = (
            f"已完成对「{user_message}」的分析，量化 run `{run_id}` 已生成，"
            "右栏将展示行情、证据、回测与风险结论。"
        )
        emit(ChatEvent(ASSISTANT_CHUNK, turn_id, {"content": reply}))
        emit(
            ChatEvent(
                TURN_DONE,
                turn_id,
                {"status": "completed", "final_reply": reply, "end_reason": "completed"},
            )
        )
        return TurnOutcome(status="completed", final_reply=reply, end_reason="completed")

    def _check_cancelled(self, session_id: str) -> bool:
        if session_id in self._cancelled:
            self._cancelled.discard(session_id)
            return True
        return False

    def _cancelled_outcome(self) -> TurnOutcome:
        return TurnOutcome(
            status="cancelled",
            final_reply="",
            end_reason="user_cancelled",
            error=None,
        )

    def _create_quant_run(self, session_id: str, turn_id: int, objective: str) -> str:
        digest = hashlib.sha1(f"{session_id}:{turn_id}".encode()).hexdigest()[:12]
        run_id = f"run-{digest}"
        now = _now_iso()
        session = self._session_factory()
        try:
            stores = create_stores(session)
            stores.runs.create_run(
                run_id=run_id,
                objective=objective,
                thread_id=session_id,
                status="running",
                started_at=now,
                harness_version="fake-1.0",
            )
            stores.steps.create_step(
                run_id=run_id,
                seq=1,
                node="research",
                status="completed",
                output_schema="ResearchSummary",
                started_at=now,
                finished_at=now,
            )
            stores.tool_calls.create_tool_call(
                run_id=run_id,
                tool_name="quant_run_analysis",
                params_hash=hashlib.sha1(objective.encode()).hexdigest()[:16],
                params_json={"objective": objective},
                status="ok",
            )
            stores.runs.update_run_status(run_id, "completed", finished_at=now)
        finally:
            session.close()
        return run_id
