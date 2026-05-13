# -*- coding: utf-8 -*-
"""Base Agent - 所有 Agent 的基类"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from app.agent.llm_adapter import LLMToolAdapter
from app.agent.protocols import (
    AgentContext,
    AgentOpinion,
    StageResult,
    StageStatus,
)
from app.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 抽象基类"""

    # 子类必须定义
    agent_name: str = "base"
    tool_names: Optional[List[str]] = None  # None 表示所有工具可用
    max_steps: int = 6

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
        skill_instructions: str = "",
    ):
        self.tool_registry = tool_registry
        self.llm_adapter = llm_adapter
        self.skill_instructions = skill_instructions

    @abstractmethod
    def system_prompt(self, ctx: AgentContext) -> str:
        """构建系统提示词"""

    @abstractmethod
    def build_user_message(self, ctx: AgentContext) -> str:
        """构建用户消息"""

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """后处理 LLM 响应，提取结构化意见"""
        return None

    def run(
        self,
        ctx: AgentContext,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> StageResult:
        """执行 Agent"""
        t0 = time.time()
        result = StageResult(stage_name=self.agent_name, status=StageStatus.RUNNING)

        try:
            messages = self._build_messages(ctx)

            # 简化版：直接调用 LLM，不使用工具循环
            response = self.llm_adapter.chat(messages)

            content = response["choices"][0]["message"]["content"]
            result.tokens_used = response.get("usage", {}).get("total_tokens", 0)
            result.meta["raw_text"] = content

            # 后处理为结构化意见
            opinion = self.post_process(ctx, content)
            if opinion is not None:
                opinion.agent_name = self.agent_name
                ctx.add_opinion(opinion)
                result.opinion = opinion

            result.status = StageStatus.COMPLETED

        except Exception as exc:
            logger.error(f"[{self.agent_name}] execution failed: {exc}", exc_info=True)
            result.status = StageStatus.FAILED
            result.error = str(exc)
        finally:
            result.duration_s = round(time.time() - t0, 2)

        return result

    def _build_messages(self, ctx: AgentContext) -> List[Dict[str, Any]]:
        """构建消息列表"""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt(ctx)},
        ]

        # 注入预取数据
        cached_data = self._inject_cached_data(ctx)
        if cached_data:
            messages.append({"role": "user", "content": cached_data})
            messages.append(
                {"role": "assistant", "content": "明白，已收到预取数据。继续分析。"}
            )

        messages.append({"role": "user", "content": self.build_user_message(ctx)})
        return messages

    def _inject_cached_data(self, ctx: AgentContext) -> str:
        """注入预取数据"""
        parts = []
        for key, value in ctx.data.items():
            if value is not None:
                serialized = str(value)[:8000]  # 限制长度
                parts.append(f"[预取数据: {key}]\n{serialized}")
        return "\n\n".join(parts)
