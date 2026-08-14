"""Agent 编排器 - 简化版

支持多模式:
- quick: 快速分析（技术分析 -> 决策）
- standard: 标准分析（技术分析 -> 情报 -> 决策）
- full: 完整分析（技术分析 -> 情报 -> 风控 -> 决策）
- strategy: 策略分析（技术分析 -> 情报 -> 风控 -> 策略 -> 决策）

阶段定义、单阶段执行与提示词分别拆到 ``pipeline.py`` / ``prompts.py``，
本模块只保留编排器外壳与模式校验，降低回归范围。
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from app.agent.config import agent_settings
from app.agent.llm_adapter import LLMToolAdapter
from app.agent.pipeline import MODE_PIPELINES, OrchestratorResult, run_pipeline
from app.agent.protocols import AgentContext
from app.services.tasks.base import TaskCancelledError

logger = logging.getLogger(__name__)

# 支持的模式
VALID_MODES = tuple(MODE_PIPELINES.keys())

__all__ = ["VALID_MODES", "AgentOrchestrator", "OrchestratorResult"]


class AgentOrchestrator:
    """Agent 编排器"""

    def __init__(self, mode: str | None = None):
        """初始化编排器

        Args:
            mode: 编排模式 (quick/standard/full/strategy)
        """
        self.mode = mode or agent_settings.AGENT_ORCHESTRATOR_MODE
        if self.mode not in VALID_MODES:
            raise ValueError(f"Invalid mode: {self.mode}. Valid: {VALID_MODES}")

        self.max_steps = agent_settings.AGENT_MAX_STEPS
        self.llm: LLMToolAdapter | None = None
        self._init_llm()

    def _init_llm(self) -> None:
        """初始化 LLM"""
        try:
            self.llm = LLMToolAdapter()
        except ValueError as e:
            logger.warning("LLM not initialized: %s", e)

    @property
    def is_available(self) -> bool:
        """检查 LLM 是否可用"""
        return self.llm is not None

    def run(
        self,
        stock_code: str,
        stock_name: str = "",
        query: str = "",
        context_data: dict[str, Any] | None = None,
        progress_callback: Callable[[float, list[dict[str, Any]]], None] | None = None,
    ) -> OrchestratorResult:
        """执行 Agent 分析

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            query: 用户查询
            context_data: 预提供的上下文数据
            progress_callback: 进度回调 (progress_0_100, stages)

        Returns:
            OrchestratorResult: 分析结果
        """
        start_time = time.time()

        # 创建上下文
        context = AgentContext(
            stock_code=stock_code,
            stock_name=stock_name,
            query=query,
            mode=self.mode,
            data=context_data or {},
        )

        # 检查 LLM 可用性
        if not self.llm:
            result = OrchestratorResult()
            result.error = "LLM not available"
            result.duration_s = time.time() - start_time
            return result

        try:
            result = run_pipeline(context, self.llm, progress_callback)
        except TaskCancelledError:
            # 协作式取消（例如后台任务被用户取消）：原样抛出，交由任务执行器
            # 标记为 cancelled，而不是吞掉后继续执行。
            raise
        except Exception as exc:
            logger.exception("Orchestrator error")
            result = OrchestratorResult()
            result.error = str(exc)

        result.duration_s = time.time() - start_time
        return result
