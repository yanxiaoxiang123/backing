"""SQLAlchemy repository 实现（SQLite/MySQL 通用）。

所有方法返回 JSON 安全 dict（datetime → isoformat），供 runtime/API 直接使用。
"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_runtime import (
    AgentRun,
    AgentStep,
    ApprovalRecord,
    ArtifactRecord,
    ToolCallRecord,
)


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _dt(value: Any) -> Any:
    """ISO 字符串 → datetime（create 路径的统一转换）。"""
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {column.name: _iso(getattr(row, column.name)) for column in row.__table__.columns}


class SqlAlchemyRunStore:
    def __init__(self, session: Session):
        self.session = session

    def create_run(self, *, run_id: str, objective: str, **fields: Any) -> dict[str, Any]:
        if fields.get("started_at") is not None:
            fields["started_at"] = _dt(fields["started_at"])
        if fields.get("finished_at") is not None:
            fields["finished_at"] = _dt(fields["finished_at"])
        row = AgentRun(run_id=run_id, objective=objective, **fields)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_dict(row)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = (
            self.session.query(AgentRun).filter(AgentRun.run_id == run_id).one_or_none()
        )
        return _row_to_dict(row) if row else None

    def update_run_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> bool:
        row = (
            self.session.query(AgentRun).filter(AgentRun.run_id == run_id).one_or_none()
        )
        if row is None:
            return False
        row.status = status
        if error is not None:
            row.error = error
        if started_at is not None:
            row.started_at = datetime.fromisoformat(started_at)
        if finished_at is not None:
            row.finished_at = datetime.fromisoformat(finished_at)
        self.session.commit()
        return True

    def list_runs(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        query = self.session.query(AgentRun)
        if status is not None:
            query = query.filter(AgentRun.status == status)
        rows = query.order_by(AgentRun.created_at.desc()).limit(limit).offset(offset).all()
        return [_row_to_dict(row) for row in rows]


class SqlAlchemyStepStore:
    def __init__(self, session: Session):
        self.session = session

    def create_step(self, *, run_id: str, seq: int, node: str, **fields: Any) -> dict[str, Any]:
        if fields.get("started_at") is not None:
            fields["started_at"] = _dt(fields["started_at"])
        if fields.get("finished_at") is not None:
            fields["finished_at"] = _dt(fields["finished_at"])
        row = AgentStep(run_id=run_id, seq=seq, node=node, **fields)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_dict(row)

    def get_step(self, run_id: str, seq: int) -> dict[str, Any] | None:
        row = (
            self.session.query(AgentStep)
            .filter(AgentStep.run_id == run_id, AgentStep.seq == seq)
            .one_or_none()
        )
        return _row_to_dict(row) if row else None

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
    ) -> bool:
        row = (
            self.session.query(AgentStep)
            .filter(AgentStep.run_id == run_id, AgentStep.seq == seq)
            .one_or_none()
        )
        if row is None:
            return False
        row.status = status
        if output_schema is not None:
            row.output_schema = output_schema
        if output_json is not None:
            row.output_json = output_json
        if retries is not None:
            row.retries = retries
        if duration_s is not None:
            row.duration_s = duration_s
        if tokens_used is not None:
            row.tokens_used = tokens_used
        if error is not None:
            row.error = error
        if started_at is not None:
            row.started_at = datetime.fromisoformat(started_at)
        if finished_at is not None:
            row.finished_at = datetime.fromisoformat(finished_at)
        self.session.commit()
        return True

    def list_steps(self, run_id: str) -> list[dict[str, Any]]:
        rows = (
            self.session.query(AgentStep)
            .filter(AgentStep.run_id == run_id)
            .order_by(AgentStep.seq.asc())
            .all()
        )
        return [_row_to_dict(row) for row in rows]


class SqlAlchemyToolCallStore:
    def __init__(self, session: Session):
        self.session = session

    def create_tool_call(
        self,
        *,
        run_id: str,
        tool_name: str,
        params_hash: str,
        params_json: dict[str, Any],
        **fields: Any,
    ) -> dict[str, Any]:
        row = ToolCallRecord(
            run_id=run_id,
            tool_name=tool_name,
            params_hash=params_hash,
            params_json=params_json,
            **fields,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_dict(row)

    def list_tool_calls(self, run_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        rows = (
            self.session.query(ToolCallRecord)
            .filter(ToolCallRecord.run_id == run_id)
            .order_by(ToolCallRecord.created_at.asc())
            .limit(limit)
            .all()
        )
        return [_row_to_dict(row) for row in rows]


class SqlAlchemyArtifactStore:
    def __init__(self, session: Session):
        self.session = session

    def create_artifact(
        self,
        *,
        run_id: str,
        artifact_type: str,
        uri: str,
        **fields: Any,
    ) -> dict[str, Any]:
        if fields.get("as_of") is not None:
            fields["as_of"] = _dt(fields["as_of"])
        row = ArtifactRecord(run_id=run_id, artifact_type=artifact_type, uri=uri, **fields)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_dict(row)

    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        rows = (
            self.session.query(ArtifactRecord)
            .filter(ArtifactRecord.run_id == run_id)
            .order_by(ArtifactRecord.created_at.asc())
            .all()
        )
        return [_row_to_dict(row) for row in rows]


class SqlAlchemyApprovalStore:
    def __init__(self, session: Session):
        self.session = session

    def create_approval(
        self,
        *,
        run_id: str,
        action: str,
        summary: str,
        **fields: Any,
    ) -> dict[str, Any]:
        if fields.get("expires_at") is not None:
            fields["expires_at"] = _dt(fields["expires_at"])
        if fields.get("decided_at") is not None:
            fields["decided_at"] = _dt(fields["decided_at"])
        row = ApprovalRecord(run_id=run_id, action=action, summary=summary, **fields)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_dict(row)

    def get_approval(self, approval_id: int) -> dict[str, Any] | None:
        row = self.session.get(ApprovalRecord, approval_id)
        return _row_to_dict(row) if row else None

    def update_approval_status(
        self,
        approval_id: int,
        status: str,
        *,
        decided_by: str | None = None,
        decided_at: str | None = None,
    ) -> bool:
        row = self.session.get(ApprovalRecord, approval_id)
        if row is None:
            return False
        row.status = status
        if decided_by is not None:
            row.decided_by = decided_by
        if decided_at is not None:
            row.decided_at = datetime.fromisoformat(decided_at)
        self.session.commit()
        return True

    def list_approvals(self, run_id: str) -> list[dict[str, Any]]:
        rows = (
            self.session.query(ApprovalRecord)
            .filter(ApprovalRecord.run_id == run_id)
            .order_by(ApprovalRecord.created_at.asc())
            .all()
        )
        return [_row_to_dict(row) for row in rows]
