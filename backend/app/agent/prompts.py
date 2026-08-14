"""Agent 提示词模板

按阶段拆分出提示词，方便单独维护与测试（不参与编排逻辑）。
"""

from typing import Any

from app.agent.protocols import AgentContext


def technical_prompt(context: AgentContext) -> str:
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


def intel_prompt(context: AgentContext) -> str:
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


def risk_prompt(context: AgentContext) -> str:
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


def strategy_prompt(context: AgentContext) -> str:
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


def decision_prompt(context: AgentContext, opinions: list[dict[str, Any]]) -> str:
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
