# -*- coding: utf-8 -*-
"""Decision Agent - 综合决策 Agent"""

import logging
import json
from typing import Optional

from app.agent.agents.base_agent import BaseAgent
from app.agent.llm_adapter import LLMToolAdapter
from app.agent.protocols import AgentContext, AgentOpinion, normalize_decision_signal
from app.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class DecisionAgent(BaseAgent):
    """综合决策 Agent"""

    agent_name = "decision"

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
    ):
        super().__init__(tool_registry, llm_adapter)

    def system_prompt(self, ctx: AgentContext) -> str:
        return """你是综合决策专家。你需要：

1. 综合所有 Agent（技术分析、情报分析、风险评估、策略评估）的意见
2. 权衡各种因素
3. 做出最终买卖决策
4. 生成决策报告

决策规则：
- 技术面看多 + 情报面看多 + 风险低 = 买入
- 技术面看空 + 情报面看空 + 风险高 = 卖出
- 其他情况 = 持有

请根据所有分析结果，做出最终决策：

输出格式要求：
请以 JSON 格式输出，包含以下字段：
{
    "final_signal": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reason": "决策理由",
    "summary": "综合分析报告"
}"""

    def build_user_message(self, ctx: AgentContext) -> str:
        # 汇总所有 Agent 的分析结果
        all_opinions = []

        for opinion in ctx.opinions:
            all_opinions.append(opinion.to_dict())

        return f"""股票代码: {ctx.stock_code}
分析模式: {ctx.mode}

以下是所有 Agent 的分析意见：

{json.dumps(all_opinions, ensure_ascii=False, indent=2)}

请根据以上所有分析意见，做出一个综合的最终决策。"""

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """后处理 LLM 响应"""
        try:
            import re

            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group())

                signal = normalize_decision_signal(data.get("final_signal", "hold"))

                return AgentOpinion(
                    agent_name=self.agent_name,
                    signal=signal,
                    confidence=data.get("confidence", 0.5),
                    reason=data.get("reason", ""),
                    metadata={
                        "summary": data.get("summary", ""),
                    },
                )
        except Exception as e:
            logger.error(f"Failed to parse decision: {e}")

        # 回退：基于简单规则
        return self._fallback_decision(ctx)

    def _fallback_decision(self, ctx: AgentContext) -> AgentOpinion:
        """回退：基于简单规则做决策"""
        buy_count = 0
        sell_count = 0
        total_confidence = 0

        for opinion in ctx.opinions:
            if opinion.signal == "buy":
                buy_count += 1
                total_confidence += opinion.confidence
            elif opinion.signal == "sell":
                sell_count += 1
                total_confidence += opinion.confidence

        if buy_count > sell_count:
            signal = "buy"
            confidence = min(0.9, buy_count / max(1, len(ctx.opinions)))
        elif sell_count > buy_count:
            signal = "sell"
            confidence = min(0.9, sell_count / max(1, len(ctx.opinions)))
        else:
            signal = "hold"
            confidence = 0.5

        return AgentOpinion(
            agent_name=self.agent_name,
            signal=signal,
            confidence=confidence,
            reason="基于多数投票的决策",
            metadata={"method": "fallback_voting"},
        )
