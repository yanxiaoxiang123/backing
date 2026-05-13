# -*- coding: utf-8 -*-
"""Agent 协议定义"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StageStatus(Enum):
    """Agent 执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DecisionSignal(Enum):
    """交易信号"""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    UNKNOWN = "unknown"


@dataclass
class AgentOpinion:
    """Agent 意见"""

    agent_name: str = ""
    signal: str = "hold"  # buy/sell/hold
    confidence: float = 0.5  # 0-1
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "signal": self.signal,
            "confidence": self.confidence,
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class StageResult:
    """Agent 执行结果"""

    stage_name: str
    status: StageStatus = StageStatus.PENDING
    opinion: Optional[AgentOpinion] = None
    error: Optional[str] = None
    duration_s: float = 0.0
    tokens_used: int = 0
    tool_calls_count: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "status": self.status.value,
            "opinion": self.opinion.to_dict() if self.opinion else None,
            "error": self.error,
            "duration_s": self.duration_s,
            "tokens_used": self.tokens_used,
            "tool_calls_count": self.tool_calls_count,
            "meta": self.meta,
        }


@dataclass
class AgentContext:
    """Agent 执行上下文"""

    stock_code: str = ""
    stock_name: str = ""
    query: str = ""
    mode: str = "standard"  # quick/standard/full/strategy
    data: Dict[str, Any] = field(default_factory=dict)  # 预取数据
    opinions: List[AgentOpinion] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def add_opinion(self, opinion: AgentOpinion) -> None:
        """添加意见"""
        self.opinions.append(opinion)

    def get_opinions(self, agent_name: str) -> List[AgentOpinion]:
        """获取指定 Agent 的意见"""
        return [op for op in self.opinions if op.agent_name == agent_name]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "query": self.query,
            "mode": self.mode,
            "data": self.data,
            "opinions": [op.to_dict() for op in self.opinions],
            "meta": self.meta,
        }


def normalize_decision_signal(signal: str) -> str:
    """标准化交易信号"""
    signal_lower = signal.lower().strip()
    if signal_lower in ["buy", "bull", "long", "多", "买入"]:
        return "buy"
    elif signal_lower in ["sell", "bear", "short", "空", "卖出"]:
        return "sell"
    elif signal_lower in ["hold", "neutral", "观望", "持有"]:
        return "hold"
    return "hold"
