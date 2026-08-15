"""Agent 领域层——纯 Pydantic 契约，零数据库/服务依赖。

本包是 Agent 输出的唯一结构化契约来源（见规格 US-0.1/US-0.2）：
- 所有证据强制携带 source_id / as_of / vendor / data_version；
- 缺证据的结论必须显式标记为假设（hypothesis），禁止把自由文本当事实。
"""

from app.domain.backtest import BacktestCheck, BacktestMetrics, BacktestVerdict
from app.domain.evidence import Evidence
from app.domain.plans import PlanStep, RunBudget, RunPlan
from app.domain.portfolio import (
    ConstraintResult,
    ExposureSummary,
    PortfolioProposal,
    PositionAllocation,
)
from app.domain.quality import DataQualityReport, MissingPeriod, QualityCheck
from app.domain.research import ResearchClaim
from app.domain.strategy import (
    CostModel,
    PositionSizing,
    RiskConstraints,
    StrategySpec,
    UniverseSpec,
)
from app.domain.version import SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "BacktestCheck",
    "BacktestMetrics",
    "BacktestVerdict",
    "ConstraintResult",
    "CostModel",
    "DataQualityReport",
    "Evidence",
    "ExposureSummary",
    "MissingPeriod",
    "PlanStep",
    "PortfolioProposal",
    "PositionAllocation",
    "PositionSizing",
    "QualityCheck",
    "ResearchClaim",
    "RiskConstraints",
    "RunBudget",
    "RunPlan",
    "StrategySpec",
    "UniverseSpec",
]
