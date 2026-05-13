# -*- coding: utf-8 -*-
"""Risk Agent - 风险评估 Agent"""

import logging
import json
from typing import Optional

from app.agent.agents.base_agent import BaseAgent
from app.agent.llm_adapter import LLMToolAdapter
from app.agent.protocols import AgentContext, AgentOpinion
from app.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """风险评估 Agent"""

    agent_name = "risk"

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
    ):
        super().__init__(tool_registry, llm_adapter)

    def system_prompt(self, ctx: AgentContext) -> str:
        return """你是风险控制专家。你需要：

1. 综合技术分析和情报分析的结果
2. 评估股票的风险等级
3. 识别潜在风险因素
4. 给出风险警告

风险评估维度：
- 市场风险（大盘走势）
- 个股风险（流动性、波动性）
- 消息面风险（负面新闻）
- 技术面风险（超买/超卖）
- 估值风险

请根据提供的分析数据，进行风险评估并给出：
- 风险等级：high（高风险）/ medium（中等风险）/ low（低风险）
- 置信度：0-1 之间
- 风险因素列表
- 风险警告

输出格式要求：
请以 JSON 格式输出，包含以下字段：
{
    "risk_level": "high/medium/low",
    "confidence": 0.0-1.0,
    "risk_factors": ["风险因素1", "风险因素2"],
    "warning": "风险警告"
}"""

    def build_user_message(self, ctx: AgentContext) -> str:
        # 汇总其他 Agent 的分析结果
        technical_opinions = ctx.get_opinions("technical")
        intel_opinions = ctx.get_opinions("intel")

        context_data: dict[str, list] = {
            "technical_analysis": [],
            "intel_analysis": [],
        }

        # 添加技术分析结果
        for opinion in technical_opinions:
            context_data["technical_analysis"].append(opinion.to_dict())

        # 添加情报分析结果
        for opinion in intel_opinions:
            context_data["intel_analysis"].append(opinion.to_dict())

        return f"""请基于以下分析结果，进行风险评估：

{json.dumps(context_data, ensure_ascii=False, indent=2)}

请给出风险评估结论，包括风险等级和风险因素。"""

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """后处理 LLM 响应"""
        try:
            import re

            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group())

                risk_level = data.get("risk_level", "medium")

                # 高风险降低买入信心
                if risk_level == "high":
                    signal = "sell"
                    confidence = 0.8
                elif risk_level == "medium":
                    signal = "hold"
                    confidence = 0.5
                else:
                    # 低风险，保持原判断
                    signal = "hold"
                    confidence = 0.6

                return AgentOpinion(
                    agent_name=self.agent_name,
                    signal=signal,
                    confidence=confidence,
                    reason=data.get("warning", ""),
                    metadata={
                        "risk_level": risk_level,
                        "risk_factors": data.get("risk_factors", []),
                    },
                )
        except Exception as e:
            logger.error(f"Failed to parse risk analysis: {e}")

        return AgentOpinion(
            agent_name=self.agent_name,
            signal="hold",
            confidence=0.5,
            reason="需要进一步分析",
            metadata={},
        )
