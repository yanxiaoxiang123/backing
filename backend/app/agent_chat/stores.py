"""Agent 聊天仓库：chat threads / turns / events 持久化接口 + SQLAlchemy 实现。

遵循 agent_runtime/stores 模式（规格决策 7）：实现类以 ``Session`` 构造，
返回 JSON 安全 dict；换 PostgreSQL 只换实现类。
"""

from datetime import datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models.agent_chat import AgentChatEvent, AgentChatThread, AgentChatTurn

_DATETIME_FIELDS = ("started_at", "finished_at", "created_at", "updated_at")


def _dt(value: Any) -> Any:
    """ISO 字符串 → datetime（与 agent_runtime/stores 一致，SQLite DateTime 列要求）。"""
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def _coerce(fields: dict[str, Any]) -> dict[str, Any]:
    for key in _DATETIME_FIELDS:
        if key in fields and isinstance(fields[key], str):
            fields[key] = _dt(fields[key])
    return fields


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


class ChatThreadStore(Protocol):
    def create_thread(self, *, thread_id: str, **fields: Any) -> dict[str, Any]: ...

    def get_thread(self, thread_id: str) -> dict[str, Any] | None: ...

    def update_thread(self, thread_id: str, **fields: Any) -> bool: ...

    def list_threads(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]: ...

    def count_threads(self) -> int: ...


class ChatTurnStore(Protocol):
    def create_turn(
        self, *, turn_id: str, thread_id: str, user_input: str, **fields: Any
    ) -> dict[str, Any]: ...

    def get_turn_by_pk(self, pk: int) -> dict[str, Any] | None: ...

    def get_turn(self, turn_id: str) -> dict[str, Any] | None: ...

    def get_turn_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None: ...

    def list_turns(self, thread_id: str) -> list[dict[str, Any]]: ...

    def update_turn_status(self, turn_id: str, status: str, **fields: Any) -> bool: ...

    def list_turns_by_status(self, statuses: list[str]) -> list[dict[str, Any]]: ...


class ChatEventStore(Protocol):
    def create_event(
        self, *, turn_id: str, seq: int, event_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def list_events(
        self, thread_id: str, *, after_id: int = 0, limit: int = 1000
    ) -> list[dict[str, Any]]: ...


class ChatStores(Protocol):
    threads: ChatThreadStore
    turns: ChatTurnStore
    events: ChatEventStore


class SqlChatThreadStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_thread(self, *, thread_id: str, **fields: Any) -> dict[str, Any]:
        row = AgentChatThread(thread_id=thread_id, **_coerce(fields))
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_dict(row)

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        row = (
            self.session.query(AgentChatThread)
            .filter(AgentChatThread.thread_id == thread_id)
            .first()
        )
        return _row_to_dict(row) if row else None

    def update_thread(self, thread_id: str, **fields: Any) -> bool:
        row = (
            self.session.query(AgentChatThread)
            .filter(AgentChatThread.thread_id == thread_id)
            .first()
        )
        if row is None:
            return False
        for key, value in _coerce(fields).items():
            setattr(row, key, value)
        self.session.commit()
        return True

    def list_threads(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        rows = (
            self.session.query(AgentChatThread)
            .filter(AgentChatThread.archived.is_(False))
            .order_by(AgentChatThread.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_row_to_dict(r) for r in rows]

    def count_threads(self) -> int:
        return (
            self.session.query(AgentChatThread)
            .filter(AgentChatThread.archived.is_(False))
            .count()
        )


class SqlChatTurnStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_turn(
        self, *, turn_id: str, thread_id: str, user_input: str, **fields: Any
    ) -> dict[str, Any]:
        row = AgentChatTurn(
            turn_id=turn_id, thread_id=thread_id, user_input=user_input, **_coerce(fields)
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_dict(row)

    def get_turn_by_pk(self, pk: int) -> dict[str, Any] | None:
        row = self.session.get(AgentChatTurn, pk)
        return _row_to_dict(row) if row else None

    def get_turn(self, turn_id: str) -> dict[str, Any] | None:
        row = (
            self.session.query(AgentChatTurn)
            .filter(AgentChatTurn.turn_id == turn_id)
            .first()
        )
        return _row_to_dict(row) if row else None

    def get_turn_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        row = (
            self.session.query(AgentChatTurn)
            .filter(AgentChatTurn.idempotency_key == idempotency_key)
            .first()
        )
        return _row_to_dict(row) if row else None

    def list_turns(self, thread_id: str) -> list[dict[str, Any]]:
        rows = (
            self.session.query(AgentChatTurn)
            .filter(AgentChatTurn.thread_id == thread_id)
            .order_by(AgentChatTurn.id.asc())
            .all()
        )
        return [_row_to_dict(r) for r in rows]

    def update_turn_status(self, turn_id: str, status: str, **fields: Any) -> bool:
        row = (
            self.session.query(AgentChatTurn)
            .filter(AgentChatTurn.turn_id == turn_id)
            .first()
        )
        if row is None:
            return False
        row.status = status
        for key, value in _coerce(fields).items():
            setattr(row, key, value)
        self.session.commit()
        return True

    def list_turns_by_status(self, statuses: list[str]) -> list[dict[str, Any]]:
        rows = (
            self.session.query(AgentChatTurn)
            .filter(AgentChatTurn.status.in_(statuses))
            .order_by(AgentChatTurn.id.asc())
            .all()
        )
        return [_row_to_dict(r) for r in rows]


class SqlChatEventStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_event(
        self, *, turn_id: str, seq: int, event_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        row = AgentChatEvent(
            turn_id=turn_id, seq=seq, event_type=event_type, payload=payload
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_dict(row)

    def list_events(
        self, thread_id: str, *, after_id: int = 0, limit: int = 1000
    ) -> list[dict[str, Any]]:
        rows = (
            self.session.query(AgentChatEvent, AgentChatTurn.id)
            .join(AgentChatTurn, AgentChatEvent.turn_id == AgentChatTurn.turn_id)
            .filter(AgentChatTurn.thread_id == thread_id)
            .filter(AgentChatEvent.id > after_id)
            .order_by(AgentChatEvent.id.asc())
            .limit(limit)
            .all()
        )
        out = []
        for row, turn_pk in rows:
            item = _row_to_dict(row)
            item["turn_pk"] = turn_pk
            out.append(item)
        return out


def create_chat_stores(session: Session) -> ChatStores:
    """工厂：构造绑定该会话的聊天 stores（换 PostgreSQL 只换实现类）。"""

    class _ChatStores:
        threads = SqlChatThreadStore(session)
        turns = SqlChatTurnStore(session)
        events = SqlChatEventStore(session)

    return _ChatStores()  # type: ignore[return-value]
