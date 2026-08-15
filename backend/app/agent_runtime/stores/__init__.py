"""Repository 工厂：把五类 store 绑定到同一 Session 并打包。"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agent_runtime.stores.protocols import Stores
from app.agent_runtime.stores.sqlalchemy import (
    SqlAlchemyApprovalStore,
    SqlAlchemyArtifactStore,
    SqlAlchemyRunStore,
    SqlAlchemyStepStore,
    SqlAlchemyToolCallStore,
)


@dataclass
class SqlAlchemyStores(Stores):
    runs: SqlAlchemyRunStore
    steps: SqlAlchemyStepStore
    tool_calls: SqlAlchemyToolCallStore
    artifacts: SqlAlchemyArtifactStore
    approvals: SqlAlchemyApprovalStore


def create_stores(session: Session) -> Stores:
    """绑定到给定 Session 的 repository 集合（换 PostgreSQL 换此工厂实现）。"""
    return SqlAlchemyStores(
        runs=SqlAlchemyRunStore(session),
        steps=SqlAlchemyStepStore(session),
        tool_calls=SqlAlchemyToolCallStore(session),
        artifacts=SqlAlchemyArtifactStore(session),
        approvals=SqlAlchemyApprovalStore(session),
    )


__all__ = ["SqlAlchemyStores", "Stores", "create_stores"]
