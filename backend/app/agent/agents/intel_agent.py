# -*- coding: utf-8 -*-
"""Intel Agent - 情报收集 Agent"""

import logging
import json
from typing import Optional

from app.agent.agents.base_agent import BaseAgent
from app.agent.llm_adapter import LLMToolAdapter
from app.agent.protocols import AgentContext, AgentOpinion
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.search import tavily_search
from app.config import SessionLocal
from app.models.models import Stock

logger = logging.getLogger(__name__)


class IntelAgent(BaseAgent):
    """情报收集 Agent - 负责收集和分析股票相关新闻"""

    agent_name = "intel"

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_adapter: LLMToolAdapter,
    ):
        super().__init__(tool_registry, llm_adapter)

    def system_prompt(self, ctx: AgentContext) -> str:
        return """你是股票情报分析专家。你需要：

1. 搜索和分析股票相关的新闻
2. 评估新闻对股票的影响
3. 判断市场情绪（看涨/看跌/中性）
4. 识别关键事件和风险

请根据提供的新闻数据，进行情报分析并给出：
- 情绪判断：bullish（看涨）/ bearish（看跌）/ neutral（中性）
- 置信度：0-1 之间
- 关键事件列表
- 新闻摘要

输出格式要求：
请以 JSON 格式输出，包含以下字段：
{
    "sentiment": "bullish/bearish/neutral",
    "confidence": 0.0-1.0,
    "news_summary": "新闻摘要",
    "key_events": ["事件1", "事件2"],
    "risk_factors": ["风险因素1", "风险因素2"]
}"""

    def build_user_message(self, ctx: AgentContext) -> str:
        stock_code = ctx.stock_code
        stock_name = self._get_stock_name(stock_code)

        # 搜索新闻
        news_data = self._search_news(stock_code, stock_name)

        return f"""请分析股票 {stock_code} ({stock_name}) 的情报面：

{news_data}

请给出情报分析结论，包括市场情绪、关键事件和风险因素。"""

    def _get_stock_name(self, stock_code: str) -> str:
        """获取股票名称"""
        db = SessionLocal()
        try:
            stock = db.query(Stock).filter(Stock.code == stock_code).first()
            return stock.name if stock else stock_code
        finally:
            db.close()

    def _search_news(self, stock_code: str, stock_name: str) -> str:
        """搜索股票新闻"""
        results = tavily_search.search_stock_news(
            stock_code=stock_code,
            stock_name=stock_name,
            max_results=10,
        )

        if not results:
            return f"未找到股票 {stock_name} 的相关新闻"

        # 格式化新闻数据
        news_list = []
        for i, item in enumerate(results, 1):
            news_list.append(f"""### 新闻 {i}
标题: {item.get("title", "")}
来源: {item.get("url", "")}
内容: {item.get("content", "")[:500]}
""")

        return "\n".join(news_list)

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        """后处理 LLM 响应"""
        try:
            import re

            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group())

                # 标准化情绪
                sentiment = data.get("sentiment", "neutral")
                if sentiment in ["bullish", "看涨", "多"]:
                    signal = "buy"
                elif sentiment in ["bearish", "看跌", "空"]:
                    signal = "sell"
                else:
                    signal = "hold"

                return AgentOpinion(
                    agent_name=self.agent_name,
                    signal=signal,
                    confidence=data.get("confidence", 0.5),
                    reason=data.get("news_summary", ""),
                    metadata={
                        "sentiment": sentiment,
                        "key_events": data.get("key_events", []),
                        "risk_factors": data.get("risk_factors", []),
                    },
                )
        except Exception as e:
            logger.error(f"Failed to parse intel analysis: {e}")

        return AgentOpinion(
            agent_name=self.agent_name,
            signal="hold",
            confidence=0.5,
            reason="需要进一步分析",
            metadata={},
        )
