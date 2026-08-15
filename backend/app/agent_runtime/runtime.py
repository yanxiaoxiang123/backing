"""Run 生命周期执行器（任务 05；US-1.1/1.2/1.3/1.4/1.5）。

- 顺序执行 ``RuntimeNode`` 列表；每节点一个 ``agent_steps``（seq 单调，
  节点间为 checkpoint 边界）
- 预算检查（轮次/工具调用/token/耗时，budget.py）
- 取消在节点边界生效（CancelToken）
- 失败后 resume 从最近成功节点继续；已完成节点不重复执行（seq 幂等）
- 外部调用幂等：``find_tool_call`` 按参数 hash 去重
"""

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from app.agent_runtime.budget import BudgetState, check_budget
from app.agent_runtime.stores import Stores
from app.domain.plans import RunBudget


def params_hash(params: dict[str, Any]) -> str:
    canonical = json.dumps(params, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    """SQLite DateTime 会丢弃时区，统一使用 naive UTC 以免比较崩溃。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CancelToken:
    """进程内取消信号；进程重启后以 run 状态（cancelled/failed）为准。"""

    def __init__(self) -> None:
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def request(self, run_id: str) -> None:
        with self._lock:
            self._events.setdefault(run_id, threading.Event()).set()

    def is_cancelled(self, run_id: str) -> bool:
        with self._lock:
            event = self._events.get(run_id)
            return bool(event and event.is_set())

    def clear(self, run_id: str) -> None:
        with self._lock:
            self._events.pop(run_id, None)


@dataclass
class NodeContext:
    """传入节点的运行上下文。"""

    run_id: str
    seq: int
    node: str
    stores: Stores
    step_db_id: int
    db: Any = None


class RuntimeNode(Protocol):
    name: str

    def run(self, ctx: NodeContext) -> dict[str, Any]: ...


@dataclass
class SimpleNode:
    """可调用节点：fn(ctx) -> {"output": ..., "tokens_used": ..., "output_schema": ...}。"""

    name: str
    fn: Callable[[NodeContext], dict[str, Any]]

    def run(self, ctx: NodeContext) -> dict[str, Any]:
        return self.fn(ctx)


def find_tool_call(stores: Stores, run_id: str, tool_name: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """外部调用幂等：同一 (tool_name, 参数 hash) 已存在则返回既有记录。"""
    digest = params_hash(params)
    for call in stores.tool_calls.list_tool_calls(run_id):
        if call["tool_name"] == tool_name and call["params_hash"] == digest:
            return call
    return None


def record_tool_call(
    ctx: NodeContext,
    tool_name: str,
    params: dict[str, Any],
    *,
    permission: str = "read",
    status: str = "ok",
    result_ref: str | None = None,
    tool_version: str | None = None,
) -> dict[str, Any]:
    """节点内记录工具调用事实（自动关联 step）。"""
    return ctx.stores.tool_calls.create_tool_call(
        run_id=ctx.run_id,
        step_id=ctx.step_db_id,
        tool_name=tool_name,
        tool_version=tool_version,
        params_hash=params_hash(params),
        params_json=params,
        permission=permission,
        status=status,
        result_ref=result_ref,
    )


class RunExecutor:
    """创建与执行 run；execute 可安全重入（resume 语义）。"""

    def __init__(self, stores: Stores, *, db: Any = None, cancel_token: CancelToken | None = None):
        self.stores = stores
        self.db = db
        self.cancel = cancel_token or CancelToken()

    def create_run(
        self,
        objective: str,
        *,
        budget: RunBudget | None = None,
        thread_id: str | None = None,
        snapshot_id: str | None = None,
        model_version: str | None = None,
    ) -> str:
        run_id = uuid.uuid4().hex[:16]
        budget = budget or RunBudget()
        self.stores.runs.create_run(
            run_id=run_id,
            objective=objective,
            status="planned",
            budget_json=budget.model_dump(mode="json"),
            thread_id=thread_id,
            snapshot_id=snapshot_id,
            model_version=model_version,
        )
        return run_id

    def execute(self, run_id: str, nodes: list[RuntimeNode]) -> dict[str, Any]:
        """执行/恢复 run。节点列表须与创建时一致（seq 对位）。"""
        run = self.stores.runs.get_run(run_id)
        if run is None:
            raise KeyError(f"run {run_id} 不存在")

        budget = RunBudget.model_validate(run["budget_json"] or {})
        existing = {step["seq"]: step for step in self.stores.steps.list_steps(run_id)}

        completed_upto = max(
            (seq for seq, step in existing.items() if step["status"] == "completed"),
            default=0,
        )
        failed_seq = min(
            (seq for seq, step in existing.items() if step["status"] == "failed"),
            default=None,
        )
        start_seq = failed_seq if failed_seq is not None else completed_upto + 1

        started_at = (
            datetime.fromisoformat(run["started_at"])
            if run.get("started_at")
            else _utcnow()
        )
        self.stores.runs.update_run_status(
            run_id,
            "running",
            started_at=started_at.isoformat() if not run.get("started_at") else None,
        )
        if run.get("status") in ("cancelled", "completed", "superseded"):
            return self.stores.runs.get_run(run_id)

        attempts = 0
        for idx, node in enumerate(nodes):
            seq = idx + 1
            step = existing.get(seq)
            # 已完成或已跳过的节点不重复执行（seq 幂等恢复）
            if seq < start_seq or (step is not None and step["status"] == "completed"):
                continue

            attempts += 1
            # 预算（轮次）
            ok, reason = check_budget(
                budget,
                BudgetState(
                    attempts=attempts,
                    tool_calls=len(self.stores.tool_calls.list_tool_calls(run_id)),
                    tokens_used=sum(
                        s.get("tokens_used") or 0
                        for s in self.stores.steps.list_steps(run_id)
                        if s["status"] == "completed"
                    ),
                    elapsed_s=(_utcnow() - started_at).total_seconds(),
                ),
            )
            if not ok:
                return self._fail(run_id, reason)

            # 取消在节点边界生效
            if self.cancel.is_cancelled(run_id):
                self.stores.runs.update_run_status(
                    run_id,
                    "cancelled",
                    finished_at=_utcnow().isoformat(),
                )
                self.cancel.clear(run_id)
                return self.stores.runs.get_run(run_id)

            now = _utcnow()
            if step is None:
                step_row = self.stores.steps.create_step(
                    run_id=run_id,
                    seq=seq,
                    node=node.name,
                    status="running",
                    started_at=now.isoformat(),
                )
            else:
                # 恢复重试：更新既有 step（(run_id, seq) 唯一，不能重建）
                self.stores.steps.update_step_status(
                    run_id, seq, "running", started_at=now.isoformat()
                )
                step_row = {"id": step["id"]}
            node_started = time.perf_counter()
            try:
                result = node.run(
                    NodeContext(
                        run_id=run_id,
                        seq=seq,
                        node=node.name,
                        stores=self.stores,
                        step_db_id=step_row["id"],
                        db=self.db,
                    )
                )
            except Exception as exc:
                self.stores.steps.update_step_status(
                    run_id,
                    seq,
                    "failed",
                    error=str(exc),
                    retries=(step.get("retries") or 0) + 1 if step else 1,
                    duration_s=round(time.perf_counter() - node_started, 4),
                    finished_at=_utcnow().isoformat(),
                )
                return self._fail(run_id, f"node:{node.name}: {exc}")

            self.stores.steps.update_step_status(
                run_id,
                seq,
                "completed",
                output_schema=result.get("output_schema"),
                output_json=result.get("output"),
                tokens_used=result.get("tokens_used"),
                duration_s=round(time.perf_counter() - node_started, 4),
                finished_at=_utcnow().isoformat(),
            )
            existing = {s["seq"]: s for s in self.stores.steps.list_steps(run_id)}

        self.stores.runs.update_run_status(
            run_id,
            "completed",
            finished_at=_utcnow().isoformat(),
        )
        return self.stores.runs.get_run(run_id)

    def _fail(self, run_id: str, reason: str) -> dict[str, Any]:
        self.stores.runs.update_run_status(
            run_id,
            "failed",
            error=reason,
            finished_at=_utcnow().isoformat(),
        )
        return self.stores.runs.get_run(run_id)
