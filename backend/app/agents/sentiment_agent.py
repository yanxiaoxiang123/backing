# backend/app/agents/sentiment_agent.py
import logging
from typing import Dict, Any
from .base import Agent
from .tools.news_tools import search_stock_news
from app.agent.llm_adapter import LLMToolAdapter

logger = logging.getLogger(__name__)


class SentimentAgent(Agent):
    """情绪分析 Agent - 社交媒体情绪分析"""

    def __init__(self):
        super().__init__(
            name="情绪分析师",
            description="分析股票相关的社交媒体情绪和舆情"
        )

    def get_system_prompt(self) -> str:
        return """你是一位专业的A股情绪分析师，擅长分析社交媒体和新闻中的投资者情绪。

你的任务是：
1. 分析市场对该股票的情绪倾向（乐观/悲观/中性）
2. 识别影响情绪的关键因素
3. 判断情绪是否已经过度反映

分析时要注意：
- 散户情绪往往反向指标（极度悲观可能是买入时机）
- 情绪传播具有滞后性，需要区分短期噪音和中期趋势
- 结合成交量验证情绪信号的可靠性

你的分析要具体、有数据支撑，区分短期情绪和中期趋势。"""

    def get_tools(self):
        return [search_stock_news]

    def get_commands(self):
        return ["/情绪"]

    async def run(self, input_text: str, stream_callback, context: Dict[str, Any] = None) -> None:
        """执行情绪分析"""
        stock_code = input_text.strip()

        # 获取新闻数据
        news_data = search_stock_news.invoke({
            "keyword": stock_code,
            "max_results": 10
        })

        # 构造分析请求
        adapter = LLMToolAdapter()
        prompt = f"""请分析股票 {stock_code} 的市场情绪：

{news_data}

请给出：
1. 当前市场情绪倾向（乐观/悲观/中性）
2. 主要情绪驱动因素
3. 情绪可能带来的影响
4. 综合情绪判断和建议"""

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        try:
            response = adapter.chat(messages, stream=True)
            for chunk in response.iter_content(decode_unicode=True):
                if chunk:
                    await stream_callback(chunk)
        except Exception as e:
            logger.error(f"Sentiment agent error: {e}")
            await stream_callback(f"分析失败: {str(e)}")

        await stream_callback("[DONE]")