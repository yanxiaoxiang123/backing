"""Repository 协议：run/step/tool_call/artifact/approval 的持久化接口。

实现类仅以 ``sqlalchemy.orm.Session`` 构造，返回 JSON 安全 dict；
换 PostgreSQL 只需新增实现类并通过工厂注入（规格决策 7）。
"""

from typing import Any, Protocol


class RunStore(Protocol):
    def create_run(self, *, run_id: str, objective: str, **fields: Any) -> dict[str, Any]: ...

    def get_run(self, run_id: str) -> dict[str, Any] | None: ...

    def update_run_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> bool: ...

    def list_runs(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]: ...


class StepStore(Protocol):
    def create_step(
        self, *, run_id: str, seq: int, node: str, **fields: Any
    ) -> dict[str, Any]: ...

    def get_step(self, run_id: str, seq: int) -> dict[str, Any] | None: ...

    def update_step_status(
        self,
        run_id: str,
        seq: int,
        status: str,
        *,
        output_schema: str | None = None,
        output_json: dict[str, Any] | None = None,
        retries: int | None = None,
        duration_s: float | None = None,
        tokens_used: int | None = None,
        error: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> bool: ...

    def list_steps(self, run_id: str) -> list[dict[str, Any]]: ...


class ToolCallStore(Protocol):
    def create_tool_call(
        self,
        *,
        run_id: str,
        tool_name: str,
        params_hash: str,
        params_json: dict[str, Any],
        **fields: Any,
    ) -> dict[str, Any]: ...

    def list_tool_calls(self, run_id: str, *, limit: int = 200) -> list[dict[str, Any]]: ...


class ArtifactStore(Protocol):
    def create_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        uri: str,
        **fields: Any,
    ) -> dict[str, Any]: ...

    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]: ...


class ApprovalStore(Protocol):
    def create_approval(
        self,
        *,
        run_id: str,
        action: str,
        summary: str,
        **fields: Any,
    ) -> dict[str, Any]: ...

    def get_approval(self, approval_id: int) -> dict[str, Any] | None: ...

    def update_approval_status(
        self,
        approval_id: int,
        status: str,
        *,
        decided_by: str | None = None,
        decided_at: str | None = None,
    ) -> bool: ...

    def list_approvals(self, run_id: str) -> list[dict[str, Any]]: ...


class Stores(Protocol):
    runs: RunStore
    steps: StepStore
    tool_calls: ToolCallStore
    artifacts: ArtifactStore
    approvals: ApprovalStore
