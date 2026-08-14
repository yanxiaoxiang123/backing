# -*- coding: utf-8 -*-
"""Agent 模块初始化"""

from app.agent.config import AgentSettings, agent_settings
from app.agent.memory import AgentMemory
from app.agent.orchestrator import AgentOrchestrator, OrchestratorResult
from app.agent.protocols import (
    AgentContext,
    AgentOpinion,
    StageResult,
    StageStatus,
    normalize_decision_signal,
)
from app.agent.runner import ToolExecutor, run_agent_loop

__all__ = [
    # Protocols
    "AgentContext",
    # Memory
    "AgentMemory",
    "AgentOpinion",
    # Orchestrator
    "AgentOrchestrator",
    # Config
    "AgentSettings",
    "OrchestratorResult",
    "StageResult",
    "StageStatus",
    "ToolExecutor",
    "agent_settings",
    "normalize_decision_signal",
    # Runner
    "run_agent_loop",
]
