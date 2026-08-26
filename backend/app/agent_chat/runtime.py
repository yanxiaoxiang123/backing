"""Backend-native conversational Agent runtime.

This module intentionally has no dependency on the DeepSeek Harness checkout.
It uses the installed ``langchain-openai`` client when a real model is enabled,
while keeping the model boundary injectable for deterministic tests.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from app.agent_api.pipelines import default_pipeline
from app.agent_chat.policy import (
    ToolAdmission,
    ToolScope,
    TurnToolPolicy,
    stock_reference,
)
from app.agent_chat.seam import (
    ASSISTANT_CHUNK,
    ERROR,
    REASONING,
    RUN_LINKED,
    TOOL_CALL,
    TOOL_RESULT,
    ChatEvent,
    EmitFn,
    TurnOutcome,
)
from app.agent_chat.stores import create_chat_stores
from app.agent_runtime.runtime import CancelToken, RunExecutor
from app.agent_runtime.stores import create_stores
from app.tools.base import ToolContext
from app.tools.registry import DEFAULT_REGISTRY

logger = logging.getLogger(__name__)

MAX_MODEL_RESULT_BYTES = 32_000
READ_TOOL_NAMES = {
    "market.kline",
    "market.snapshot",
    "fundamental.stock_info",
    "fundamental.financials",
}
MODEL_TOOL_NAMES = {
    "market_kline": "market.kline",
    "market_snapshot": "market.snapshot",
    "fundamental_stock_info": "fundamental.stock_info",
    "fundamental_financials": "fundamental.financials",
}
REGISTRY_MODEL_NAMES = {value: key for key, value in MODEL_TOOL_NAMES.items()}


@dataclass(frozen=True)
class NativeToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class NativeModelResponse:
    text: str = ""
    tool_calls: list[NativeToolCall] = field(default_factory=list)


class NativeModel(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        emit_text: Callable[[str], None],
        emit_reasoning: Callable[[str], None],
        cancel_event: threading.Event,
    ) -> NativeModelResponse: ...


def _json_text(value: Any, limit: int = MAX_MODEL_RESULT_BYTES) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text.encode("utf-8")) <= limit:
        return text
    encoded = text.encode("utf-8")[:limit]
    return encoded.decode("utf-8", errors="ignore") + "…"


def _text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(
            item.get("text", "")
            for item in value
            if isinstance(item, dict) and item.get("type") in ("text", "output_text")
        )
    return ""


class LangChainDeepSeekModel:
    """Small streaming adapter around ``langchain-openai``."""

    def __init__(self, *, api_key: str, base_url: str, model: str, timeout_s: float):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model
        self.timeout_s = timeout_s

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        emit_text: Callable[[str], None],
        emit_reasoning: Callable[[str], None],
        cancel_event: threading.Event,
    ) -> NativeModelResponse:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "langchain-openai 未安装，请在 backend 环境执行 pip install -r requirements.txt"
            ) from exc

        model: Any = ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model_name,
            temperature=0,
            streaming=True,
            timeout=self.timeout_s,
            max_retries=0,
        )
        bound = model.bind_tools(tools) if tools else model
        full: Any = None
        for chunk in bound.stream(messages):
            if cancel_event.is_set():
                raise _Cancelled()
            content = _text_content(getattr(chunk, "content", ""))
            if content:
                emit_text(content)
            additional = getattr(chunk, "additional_kwargs", {}) or {}
            reasoning = additional.get("reasoning_content") or additional.get("reasoning")
            if reasoning:
                emit_reasoning(str(reasoning))
            full = chunk if full is None else full + chunk

        calls: list[NativeToolCall] = []
        for index, call in enumerate(getattr(full, "tool_calls", []) or []):
            args = call.get("args", {}) if isinstance(call, dict) else {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(
                NativeToolCall(
                    call_id=str(call.get("id") or f"call-{index + 1}"),
                    name=str(call.get("name") or ""),
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        return NativeModelResponse(
            text=_text_content(getattr(full, "content", "")) if full is not None else "",
            tool_calls=calls,
        )


class _Cancelled(Exception):
    pass


class NativeAgentChatRuntime:
    """Multi-turn, bounded ReAct loop backed by the project's own stores."""

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        model: NativeModel | None = None,
        max_steps: int = 6,
        timeout_s: float = 600,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com/v1",
        model_name: str = "deepseek-chat",
    ):
        self._session_factory = session_factory
        self._model = model
        self._max_steps = max(1, max_steps)
        self._timeout_s = max(1.0, timeout_s)
        self._api_key = api_key
        self._base_url = base_url
        self._model_name = model_name
        self._policy = TurnToolPolicy()
        self._cancel_events: dict[str, threading.Event] = {}
        self._cancel_lock = threading.Lock()
        self._shutdown = False

    @property
    def status(self) -> dict[str, Any]:
        if self._shutdown:
            return {"backend": "native", "available": False, "reason": "shutdown"}
        if not self._api_key:
            return {"backend": "native", "available": False, "reason": "missing_api_key"}
        try:
            import langchain_openai  # noqa: F401
        except ImportError:
            return {"backend": "native", "available": False, "reason": "dependency_missing"}
        return {"backend": "native", "available": True, "reason": None}

    def stop(self, session_id: str) -> None:
        with self._cancel_lock:
            event = self._cancel_events.get(session_id)
            if event:
                event.set()

    def shutdown(self) -> None:
        self._shutdown = True
        with self._cancel_lock:
            for event in self._cancel_events.values():
                event.set()
            self._cancel_events.clear()

    def run_turn(
        self,
        session_id: str,
        user_message: str,
        *,
        turn_id: int,
        emit: EmitFn,
        context: dict[str, Any] | None = None,
    ) -> TurnOutcome:
        if not self.status["available"]:
            error = self._status_error(self.status["reason"])
            emit(ChatEvent(ERROR, turn_id, {"error": error, "code": self.status["reason"]}))
            return TurnOutcome("failed", "", "configuration_error", error)

        cancel_event = threading.Event()
        with self._cancel_lock:
            self._cancel_events[session_id] = cancel_event
        try:
            history, history_text = self._history(session_id, turn_id)
            admission = self._policy.classify(user_message, history_text)
            # An explicit analysis request must always produce the structured
            # run consumed by the research pane.  Leaving this tool choice to
            # the model made otherwise-successful analysis replies impossible
            # to attach on the right-hand side.
            auto_run = admission.allow_analysis
            model_admission = (
                ToolAdmission(ToolScope.READ, "analysis_run_already_created")
                if auto_run
                else admission
            )
            tools = self._tool_schemas(model_admission)
            system_prompt = self._system_prompt(admission)
            if context:
                system_prompt += (
                    "\n当前研究上下文（仅用于理解用户意图，不要把它当作行情事实）："
                    f"{json.dumps(context, ensure_ascii=False)}"
                )
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})
            final_text = ""
            deadline = threading.Timer(self._timeout_s, cancel_event.set)
            deadline.daemon = True
            deadline.start()
            try:
                if auto_run:
                    target = stock_reference(user_message) or stock_reference(history_text)
                    objective = user_message.strip()
                    if target and not stock_reference(user_message):
                        objective = f"{objective}（股票：{target}）"
                    call = NativeToolCall(
                        call_id=f"auto-analysis-{turn_id}",
                        name="quant_run_analysis",
                        arguments={"objective": objective},
                    )
                    self._emit_tool_call(emit, turn_id, call)
                    result = self._execute_tool(
                        session_id, call, admission, cancel_event
                    )
                    self._emit_tool_result(emit, turn_id, call, result)
                    messages.extend(self._tool_exchange_messages(call, result))

                for step in range(self._max_steps):
                    if cancel_event.is_set():
                        raise _Cancelled()
                    model = self._model or LangChainDeepSeekModel(
                        api_key=self._api_key or "",
                        base_url=self._base_url,
                        model=self._model_name,
                        timeout_s=self._timeout_s,
                    )
                    response = model.complete(
                        messages,
                        tools,
                        emit_text=lambda text: emit(ChatEvent(ASSISTANT_CHUNK, turn_id, {"content": text})),
                        emit_reasoning=lambda text: emit(ChatEvent(REASONING, turn_id, {"content": text})),
                        cancel_event=cancel_event,
                    )
                    final_text = response.text or final_text
                    if not response.tool_calls:
                        return TurnOutcome("completed", final_text, "completed")
                    if admission.scope is ToolScope.NONE:
                        return TurnOutcome("completed", final_text, "completed")

                    messages.append(
                        {
                            "role": "assistant",
                            "content": response.text or "",
                            "tool_calls": [
                                {
                                    "id": call.call_id,
                                    "type": "function",
                                    "function": {
                                        "name": call.name,
                                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                                    },
                                }
                                for call in response.tool_calls
                            ],
                        }
                    )
                    for call in response.tool_calls:
                        self._emit_tool_call(emit, turn_id, call)
                        result = self._execute_tool(
                            session_id, call, model_admission, cancel_event
                        )
                        self._emit_tool_result(emit, turn_id, call, result)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.call_id,
                                "name": call.name,
                                "content": _json_text(result),
                            }
                        )
                final_text = final_text or "本轮已达到分析步数上限，请缩小研究目标后重试。"
                return TurnOutcome("completed", final_text, "max_steps")
            finally:
                deadline.cancel()
        except _Cancelled:
            return TurnOutcome("cancelled", "", "user_cancelled")
        except Exception as exc:
            logger.exception("native agent chat failed")
            error = str(exc)
            emit(ChatEvent(ERROR, turn_id, {"error": error, "code": "runtime_error"}))
            return TurnOutcome("failed", "", "error", error)
        finally:
            with self._cancel_lock:
                self._cancel_events.pop(session_id, None)

    @staticmethod
    def _emit_tool_call(
        emit: EmitFn,
        turn_id: int,
        call: NativeToolCall,
    ) -> None:
        emit(
            ChatEvent(
                TOOL_CALL,
                turn_id,
                {"call_id": call.call_id, "tool": call.name, "args": call.arguments},
            )
        )

    def _emit_tool_result(
        self,
        emit: EmitFn,
        turn_id: int,
        call: NativeToolCall,
        result: Any,
    ) -> None:
        payload = {
            "call_id": call.call_id,
            "tool": call.name,
            "summary": self._summary(call.name, result),
            "result": result,
        }
        if isinstance(result, dict) and result.get("run_id"):
            payload["run_id"] = result["run_id"]
        emit(ChatEvent(TOOL_RESULT, turn_id, payload))
        if payload.get("run_id"):
            emit(ChatEvent(RUN_LINKED, turn_id, {"run_id": payload["run_id"]}))

    @staticmethod
    def _tool_exchange_messages(
        call: NativeToolCall, result: Any
    ) -> list[dict[str, Any]]:
        return [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": call.call_id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(
                                call.arguments, ensure_ascii=False
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": call.call_id,
                "name": call.name,
                "content": _json_text(result),
            },
        ]

    def _status_error(self, reason: str | None) -> str:
        return {
            "missing_api_key": "Agent 聊天未配置 DEEPSEEK_API_KEY",
            "dependency_missing": "Agent 聊天依赖未安装，请安装 backend/requirements.txt",
            "shutdown": "Agent 聊天服务正在关闭",
        }.get(reason or "", "Agent 聊天暂不可用")

    def _history(self, session_id: str, current_turn_id: int) -> tuple[list[dict[str, Any]], str]:
        session = self._session_factory()
        try:
            stores = create_chat_stores(session)
            turns = stores.turns.list_turns(session_id)
            events = stores.events.list_events(session_id)
            messages: list[dict[str, Any]] = []
            text_parts: list[str] = []
            for turn in turns:
                if turn["id"] == current_turn_id or turn["status"] not in ("completed", "failed"):
                    continue
                messages.append({"role": "user", "content": turn["user_input"]})
                text_parts.append(turn["user_input"])
                # A failed turn may contain an orphan tool_call whose result
                # could not be persisted.  Replaying that partial protocol
                # makes the next OpenAI-compatible request invalid.  Preserve
                # the user's intent, but only replay tools from completed turns.
                if turn["status"] == "failed":
                    continue
                tool_events = sorted(
                    (event for event in events if event["turn_pk"] == turn["id"]),
                    key=lambda item: item["seq"],
                )
                for event in tool_events:
                    payload = event["payload"]
                    if event["event_type"] == TOOL_CALL:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [{
                                    "id": payload.get("call_id", f"history-{turn['id']}"),
                                    "type": "function",
                                    "function": {
                                        "name": payload.get("tool", ""),
                                        "arguments": json.dumps(payload.get("args", {}), ensure_ascii=False),
                                    },
                                }],
                            }
                        )
                    elif event["event_type"] == TOOL_RESULT:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": payload.get("call_id", f"history-{turn['id']}"),
                                "name": payload.get("tool", ""),
                                "content": _json_text(payload.get("result", payload.get("summary", ""))),
                            }
                        )
                if turn.get("final_reply"):
                    messages.append({"role": "assistant", "content": turn["final_reply"]})
                    text_parts.append(turn["final_reply"])
            return messages, "\n".join(text_parts)[-12_000:]
        finally:
            session.close()

    def _tool_schemas(self, admission: ToolAdmission) -> list[dict[str, Any]]:
        names = READ_TOOL_NAMES if admission.scope in (ToolScope.READ, ToolScope.ANALYSIS) else set()
        if admission.allow_analysis:
            names = set(names) | {"quant_run_analysis"}
        schemas = []
        for tool in DEFAULT_REGISTRY.list_tools():
            if tool["name"] in names:
                model_name = REGISTRY_MODEL_NAMES[tool["name"]]
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": model_name,
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                })
        if admission.allow_analysis:
            schemas.append({
                "type": "function",
                "function": {
                    "name": "quant_run_analysis",
                    "description": "创建并执行一次明确目标的股票研究或策略回测 run。",
                    "parameters": {
                        "type": "object",
                        "properties": {"objective": {"type": "string"}},
                        "required": ["objective"],
                        "additionalProperties": False,
                    },
                },
            })
        return schemas

    def _system_prompt(self, admission: ToolAdmission) -> str:
        return (
            "你是 Backing 的中文股票量化研究助手。先理解用户意图，再回答。"
            "普通问候、能力询问和感谢直接自然回复，不调用工具。信息不足时只追问缺少的股票、周期或研究目标。"
            "不得编造行情、财报、回测结果或收益承诺；使用工具得到的数据时说明来源和时间。"
            f"本轮工具权限为 {admission.scope.value}，不要调用未提供的工具。"
        )

    def _execute_tool(
        self, session_id: str, call: NativeToolCall, admission: ToolAdmission, cancel_event: threading.Event
    ) -> dict[str, Any]:
        if call.name == "quant_run_analysis":
            if not admission.allow_analysis:
                return {"ok": False, "error": {"code": "analysis_not_admitted", "message": "研究目标不完整"}}
            objective = str(call.arguments.get("objective") or "").strip()
            if not objective:
                return {"ok": False, "error": {"code": "validation", "message": "objective 不能为空"}}
            session = self._session_factory()
            try:
                stores = create_stores(session)
                executor = RunExecutor(stores, db=session, cancel_token=CancelToken())
                run_id = executor.create_run(objective, thread_id=session_id)
                run_done = threading.Event()

                def propagate_cancel() -> None:
                    while not run_done.wait(0.1):
                        if cancel_event.is_set():
                            executor.cancel.request(run_id)
                            return

                watcher = threading.Thread(
                    target=propagate_cancel,
                    daemon=True,
                    name=f"agent-chat-cancel-{run_id}",
                )
                watcher.start()
                try:
                    if cancel_event.is_set():
                        executor.cancel.request(run_id)
                    final = executor.execute(run_id, default_pipeline(objective))
                finally:
                    run_done.set()
                    watcher.join(timeout=0.25)
                stores.tool_calls.create_tool_call(
                    run_id=run_id,
                    tool_name="quant_run_analysis",
                    tool_version="native-1.0",
                    params_hash=hashlib.sha256(objective.encode("utf-8")).hexdigest(),
                    params_json={"objective": objective},
                    permission="strategy",
                    status="ok" if final.get("status") == "completed" else "failed",
                    error=final.get("error"),
                )
                return {"ok": True, "run_id": run_id, "status": final.get("status"), "run": final}
            finally:
                session.close()

        if call.name not in READ_TOOL_NAMES:
            registry_name = MODEL_TOOL_NAMES.get(call.name)
        else:
            registry_name = call.name
        if registry_name not in READ_TOOL_NAMES:
            return {"ok": False, "error": {"code": "tool_not_allowed", "message": f"工具 {call.name} 未开放"}}
        session = self._session_factory()
        try:
            result = DEFAULT_REGISTRY.invoke(
                registry_name,
                call.arguments,
                ToolContext(db=session, stores=create_stores(session), granted_permissions={"read"}),
            )
            return result
        finally:
            session.close()

    @staticmethod
    def _summary(tool: str, result: Any) -> str:
        if isinstance(result, dict) and result.get("ok") is False:
            return str(result.get("error", {}).get("message", "工具执行失败"))
        if isinstance(result, dict) and result.get("run_id"):
            return f"量化 run {result['run_id']}：{result.get('status', '已创建')}"
        if isinstance(result, dict) and result.get("source_id"):
            return f"{tool} 已返回数据（来源 {result['source_id']}）"
        return f"{tool} 已完成"


__all__ = ["LangChainDeepSeekModel", "NativeAgentChatRuntime", "NativeModel", "NativeModelResponse", "NativeToolCall"]
