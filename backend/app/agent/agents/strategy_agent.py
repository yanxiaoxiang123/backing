# -*- coding: utf-8 -*-
"""Strategy Agent - 策略评估 Agent"""

import logging
import json
from typing import Optional

from app.agent.agents.base_agent import BaseAgent
from app.agent.llm_adapter import LLMToolAdapter
from app.agent.protocols import AgentContext, AgentOpinion
from app.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


# 内置策略列表
BUILTIN_STRATEGIES = {
    "bull_trend": {
        "name": "多头趋势策略",
        "description": "MA5>MA10>MA20 排列 + 低乖离率",
    },
    "ma_golden_cross": {
        "name": "均线金叉策略",
        "description": "MA5 上穿 MA10/MA20",
    },
    "volume_breakout": {
        "name": "放量突破策略",
        "description": "价格突破近期高点 + 成交量放大",
    },
    "shrink_pullback": {
        "name": "缩量回踩策略",
        "description": "回踩均线 + 量能萎缩，低吸点",
    },
    "bottom_volume": {
        "name": "底部放量策略",
        "description": "地量见地价，底部反转信号",
    },
    "dragon_head": {
        "name": "龙头策略",
        "description": "强势龙头，趋势延续追涨",
    },
}


class StrategyAgent(BaseAgent):
    """策略评估 Agent"""

    agent_name = "strategy"

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
    ):
        super().__init__(tool_registry, llm_adapter)

    def system_prompt(self, ctx: AgentContext) -> str:
        strategies_text = "\n".join(
            [
                f"- {k}: {v['name']} - {v['description']}"
                for k, v in BUILTIN_STRATEGIES.items()
            ]
        )

        return f"""你是策略评估专家。你需要根据技术分析和情报分析的结果，评估适合当前股票的策略。

内置策略列表：
{strategies_text}

请根据分析结果：
1. 评估哪个策略最适合当前股票
2. 给出策略评分（0-1）
3. 说明选择理由

输出格式要求：
请以 JSON 格式输出，包含以下字段：
{{
    "recommended_strategy": "策略名称",
    "confidence": 0.0-1.0,
    "reason": "选择理由",
    "alternative_strategies": ["备选策略1", "备选策略2"]
}}"""

    def build_user_message(self, ctx: AgentContext) -> str:
        # 汇总其他 Agent 的分析结果
        all_opinions = []

        for opinion in ctx.opinions:
            all_opinions.append(opinion.to_dict())

        return f"""请根据以下分析结果，评估适合的策略：

{json.dumps(all_opinions, ensure_ascii=False, indent=2)}

请给出推荐的策略及其置信度。"""

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """后处理 LLM 响应"""
        try:
            import re

            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group())

                return AgentOpinion(
                    agent_name=self.agent_name,
                    signal="hold",  # 策略不直接给出买卖信号
                    confidence=data.get("confidence", 0.5),
                    reason=data.get("reason", ""),
                    metadata={
                        "recommended_strategy": data.get("recommended_strategy", ""),
                        "alternative_strategies": data.get(
                            "alternative_strategies", []
                        ),
                    },
                )
        except Exception as e:
            logger.error(f"Failed to parse strategy analysis: {e}")

        return AgentOpinion(
            agent_name=self.agent_name,
            signal="hold",
            confidence=0.5,
            reason="需要进一步分析",
            metadata={},
        )
