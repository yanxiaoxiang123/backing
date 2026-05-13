# -*- coding: utf-8 -*-
"""Agent 编排器 - 简化版

支持多模式:
- quick: 快速分析（技术分析 -> 决策）
- standard: 标准分析（技术分析 -> 情报 -> 决策）
- full: 完整分析（技术分析 -> 情报 -> 风控 -> 决策）
- strategy: 策略分析（技术分析 -> 情报 -> 风控 -> 策略 -> 决策）
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agent.config import agent_settings
from app.agent.llm_adapter import LLMToolAdapter
from app.agent.protocols import (
    AgentContext,
    AgentOpinion,
    StageResult,
    StageStatus,
    normalize_decision_signal,
)
from app.agent.tools.search import tavily_search

logger = logging.getLogger(__name__)

# 支持的模式
VALID_MODES = ("quick", "standard", "full", "strategy")


@dataclass
class OrchestratorResult:
    """编排结果"""

    success: bool = False
    final_signal: str = "hold"
    final_confidence: float = 0.0
    final_reason: str = ""
    opinions: List[Dict[str, Any]] = field(default_factory=list)
    stages: List[Dict[str, Any]] = field(default_factory=list)
    duration_s: float = 0.0
    error: Optional[str] = None


class AgentOrchestrator:
    """Agent 编排器"""

    def __init__(self, mode: Optional[str] = None):
        """初始化编排器

        Args:
            mode: 编排模式 (quick/standard/full/strategy)
        """
        self.mode = mode or agent_settings.AGENT_ORCHESTRATOR_MODE
        if self.mode not in VALID_MODES:
            raise ValueError(f"Invalid mode: {self.mode}. Valid: {VALID_MODES}")

        self.max_steps = agent_settings.AGENT_MAX_STEPS
        self.llm: Optional[LLMToolAdapter] = None
        self._init_llm()

    def _init_llm(self) -> None:
        """初始化 LLM"""
        try:
            self.llm = LLMToolAdapter()
        except ValueError as e:
            logger.warning(f"LLM not initialized: {e}")

    @property
    def is_available(self) -> bool:
        """检查 LLM 是否可用"""
        return self.llm is not None

    def run(
        self,
        stock_code: str,
        stock_name: str = "",
        query: str = "",
        context_data: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorResult:
        """执行 Agent 分析

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            query: 用户查询
            context_data: 预提供的上下文数据

        Returns:
            OrchestratorResult: 分析结果
        """
        start_time = time.time()
        result = OrchestratorResult()

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
            result.error = "LLM not available"
            return result

        try:
            # 根据模式执行不同阶段
            if self.mode == "quick":
                result = self._run_quick(context)
            elif self.mode == "standard":
                result = self._run_standard(context)
            elif self.mode == "full":
                result = self._run_full(context)
            elif self.mode == "strategy":
                result = self._run_strategy(context)
            else:
                result.error = f"Unknown mode: {self.mode}"

        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            result.error = str(e)

        result.duration_s = time.time() - start_time
        return result

    def _run_quick(self, context: AgentContext) -> OrchestratorResult:
        """快速模式: 技术分析 -> 决策"""
        result = OrchestratorResult()

        # 阶段 1: 技术分析
        stage1 = self._execute_stage(
            context,
            "technical_analysis",
            _get_technical_prompt(context),
        )
        result.stages.append(stage1.to_dict())

        if stage1.opinion:
            result.opinions.append(stage1.opinion.to_dict())

        # 阶段 2: 决策
        if stage1.status == StageStatus.COMPLETED:
            stage2 = self._execute_stage(
                context,
                "decision",
                _get_decision_prompt(context, result.opinions),
            )
            result.stages.append(stage2.to_dict())

            if stage2.opinion:
                result.opinions.append(stage2.opinion.to_dict())
                result.final_signal = stage2.opinion.signal
                result.final_confidence = stage2.opinion.confidence
                result.final_reason = stage2.opinion.reason
                result.success = True

        return result

    def _run_standard(self, context: AgentContext) -> OrchestratorResult:
        """标准模式: 技术分析 -> 情报 -> 决策"""
        result = OrchestratorResult()

        # 阶段 1: 技术分析
        stage1 = self._execute_stage(
            context,
            "technical_analysis",
            _get_technical_prompt(context),
        )
        result.stages.append(stage1.to_dict())

        if stage1.opinion:
            result.opinions.append(stage1.opinion.to_dict())

        # 阶段 2: 情报收集
        if stage1.status == StageStatus.COMPLETED:
            stage2 = self._execute_stage(
                context,
                "intel",
                _get_intel_prompt(context),
            )
            result.stages.append(stage2.to_dict())

            if stage2.opinion:
                result.opinions.append(stage2.opinion.to_dict())

        # 阶段 3: 决策
        stage3 = self._execute_stage(
            context,
            "decision",
            _get_decision_prompt(context, result.opinions),
        )
        result.stages.append(stage3.to_dict())

        if stage3.opinion:
            result.opinions.append(stage3.opinion.to_dict())
            result.final_signal = stage3.opinion.signal
            result.final_confidence = stage3.opinion.confidence
            result.final_reason = stage3.opinion.reason
            result.success = True

        return result

    def _run_full(self, context: AgentContext) -> OrchestratorResult:
        """完整模式: 技术分析 -> 情报 -> 风控 -> 决策"""
        result = OrchestratorResult()

        # 阶段 1: 技术分析
        stage1 = self._execute_stage(
            context,
            "technical_analysis",
            _get_technical_prompt(context),
        )
        result.stages.append(stage1.to_dict())

        if stage1.opinion:
            result.opinions.append(stage1.opinion.to_dict())

        # 阶段 2: 情报收集
        stage2 = self._execute_stage(
            context,
            "intel",
            _get_intel_prompt(context),
        )
        result.stages.append(stage2.to_dict())

        if stage2.opinion:
            result.opinions.append(stage2.opinion.to_dict())

        # 阶段 3: 风控分析
        stage3 = self._execute_stage(
            context,
            "risk",
            _get_risk_prompt(context),
        )
        result.stages.append(stage3.to_dict())

        if stage3.opinion:
            result.opinions.append(stage3.opinion.to_dict())

        # 阶段 4: 决策
        stage4 = self._execute_stage(
            context,
            "decision",
            _get_decision_prompt(context, result.opinions),
        )
        result.stages.append(stage4.to_dict())

        if stage4.opinion:
            result.opinions.append(stage4.opinion.to_dict())
            result.final_signal = stage4.opinion.signal
            result.final_confidence = stage4.opinion.confidence
            result.final_reason = stage4.opinion.reason
            result.success = True

        return result

    def _run_strategy(self, context: AgentContext) -> OrchestratorResult:
        """策略模式: 技术分析 -> 情报 -> 风控 -> 策略 -> 决策"""
        result = OrchestratorResult()

        # 阶段 1: 技术分析
        stage1 = self._execute_stage(
            context,
            "technical_analysis",
            _get_technical_prompt(context),
        )
        result.stages.append(stage1.to_dict())

        if stage1.opinion:
            result.opinions.append(stage1.opinion.to_dict())

        # 阶段 2: 情报收集
        stage2 = self._execute_stage(
            context,
            "intel",
            _get_intel_prompt(context),
        )
        result.stages.append(stage2.to_dict())

        if stage2.opinion:
            result.opinions.append(stage2.opinion.to_dict())

        # 阶段 3: 风控分析
        stage3 = self._execute_stage(
            context,
            "risk",
            _get_risk_prompt(context),
        )
        result.stages.append(stage3.to_dict())

        if stage3.opinion:
            result.opinions.append(stage3.opinion.to_dict())

        # 阶段 4: 策略评估
        stage4 = self._execute_stage(
            context,
            "strategy",
            _get_strategy_prompt(context),
        )
        result.stages.append(stage4.to_dict())

        if stage4.opinion:
            result.opinions.append(stage4.opinion.to_dict())

        # 阶段 5: 决策
        stage5 = self._execute_stage(
            context,
            "decision",
            _get_decision_prompt(context, result.opinions),
        )
        result.stages.append(stage5.to_dict())

        if stage5.opinion:
            result.opinions.append(stage5.opinion.to_dict())
            result.final_signal = stage5.opinion.signal
            result.final_confidence = stage5.opinion.confidence
            result.final_reason = stage5.opinion.reason
            result.success = True

        return result

    def _execute_stage(
        self,
        context: AgentContext,
        stage_name: str,
        prompt: str,
    ) -> StageResult:
        """执行单个阶段"""
        result = StageResult(stage_name=stage_name)
        start_time = time.time()

        try:
            if stage_name == "intel":
                news_items = tavily_search.search_stock_news(
                    stock_code=context.stock_code,
                    stock_name=context.stock_name or context.stock_code,
                    max_results=8,
                )
                result.meta["news_items"] = news_items

            # 构建消息
            messages = [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": self._build_stage_user_content(
                        context=context,
                        stage_name=stage_name,
                        news_items=result.meta.get("news_items", []),
                    ),
                },
            ]

            # 调用 LLM
            response = self.llm.chat(
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )

            # 解析响应
            content = (
                response.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

            # 尝试解析 JSON
            import json
            import re

            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                opinion = AgentOpinion(
                    agent_name=stage_name,
                    signal=normalize_decision_signal(data.get("signal", "hold")),
                    confidence=data.get("confidence", 0.5),
                    reason=data.get("reason", data.get("analysis", content[:200])),
                    metadata=data,
                )
                result.opinion = opinion
                result.status = StageStatus.COMPLETED
            else:
                # 简单解析
                content_lower = content.lower()
                signal = "hold"
                if any(
                    k in content_lower for k in ["买入", "买", "buy", "看多", "做多"]
                ):
                    signal = "buy"
                elif any(
                    k in content_lower for k in ["卖出", "卖", "sell", "看空", "做空"]
                ):
                    signal = "sell"

                opinion = AgentOpinion(
                    agent_name=stage_name,
                    signal=signal,
                    confidence=0.5,
                    reason=content[:300],
                    metadata={"raw": content},
                )
                result.opinion = opinion
                result.status = StageStatus.COMPLETED

            result.duration_s = time.time() - start_time

        except Exception as e:
            result.status = StageStatus.FAILED
            result.error = str(e)
            result.duration_s = time.time() - start_time

        return result

    def _build_stage_user_content(
        self,
        context: AgentContext,
        stage_name: str,
        news_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        content = f"股票: {context.stock_name or context.stock_code} ({context.stock_code})\n{context.query}"
        if stage_name != "intel" or not news_items:
            return content

        lines = []
        for idx, item in enumerate(news_items, start=1):
            lines.append(
                f"{idx}. 标题: {item.get('title', '')}\n"
                f"链接: {item.get('url', '')}\n"
                f"摘要: {item.get('content', '')[:300]}"
            )

        return f"{content}\n\nTavily 搜索到的相关新闻:\n" + "\n\n".join(lines)


# ============================================================
# Prompt 模板
# ============================================================


def _get_technical_prompt(context: AgentContext) -> str:
    """技术分析提示词"""
    return f"""你是一位专业的股票技术分析师。请分析股票 {context.stock_name or context.stock_code} ({context.stock_code}) 的技术面。

请提供以下分析:
1. 整体趋势判断
2. 关键支撑位和阻力位
3. 均线系统分析
4. 成交量分析
5. 技术指标信号 (MACD, RSI, KDJ等)
6. 最终信号和建议

请以 JSON 格式返回:
{{
    "signal": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reason": "分析理由"
}}
"""


def _get_intel_prompt(context: AgentContext) -> str:
    """情报收集提示词"""
    return f"""你是一位专业的股票情报分析师。请收集和分析股票 {context.stock_name or context.stock_code} ({context.stock_code}) 的相关信息。

请提供以下分析:
1. 最新消息和公告
2. 行业动态
3. 主力资金流向
4. 大宗交易情况
5. 龙虎榜数据（如有）

请以 JSON 格式返回:
{{
    "signal": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reason": "情报分析理由"
}}
"""


def _get_risk_prompt(context: AgentContext) -> str:
    """风控分析提示词"""
    return f"""你是一位专业的股票风控分析师。请分析股票 {context.stock_name or context.stock_code} ({context.stock_code}) 的风险因素。

请提供以下分析:
1. 市场系统性风险
2. 个股特有风险
3. 流动性风险
4. 估值风险
5. 风险等级评估

请以 JSON 格式返回:
{{
    "signal": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reason": "风险分析理由"
}}
"""


def _get_strategy_prompt(context: AgentContext) -> str:
    """策略评估提示词"""
    return f"""你是一位专业的量化策略分析师。请评估股票 {context.stock_name or context.stock_code} ({context.stock_code}) 的策略适用性。

请提供以下分析:
1. 适合的策略类型
2. 仓位管理建议
3. 止盈止损策略
4. 风险收益比

请以 JSON 格式返回:
{{
    "signal": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reason": "策略分析理由"
}}
"""


def _get_decision_prompt(context: AgentContext, opinions: List[Dict[str, Any]]) -> str:
    """决策提示词"""
    opinions_text = "\n".join(
        [
            f"- {op.get('agent_name')}: signal={op.get('signal')}, confidence={op.get('confidence')}, reason={op.get('reason', '')[:100]}"
            for op in opinions
        ]
    )

    return f"""你是一位专业的股票投资决策分析师。请根据以下各维度分析结果，给出最终投资建议。

各维度分析:
{opinions_text}

请综合以上分析，给出最终决策:

请以 JSON 格式返回:
{{
    "signal": "buy/sell/hold",
    "confidence": 0.0-1.0,
    "reason": "综合决策理由"
}}
"""
