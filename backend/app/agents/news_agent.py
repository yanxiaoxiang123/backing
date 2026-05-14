# backend/app/agents/news_agent.py
import logging
from typing import Dict, Any
from .base import Agent
from .tools.news_tools import search_stock_news
from app.agent.llm_adapter import LLMToolAdapter

logger = logging.getLogger(__name__)


class NewsAgent(Agent):
    """新闻分析 Agent"""

    def __init__(self):
        super().__init__(
            name="新闻分析师",
            description="搜索和分析股票相关的新闻资讯"
        )

    def get_system_prompt(self) -> str:
        return """你是一位专业的A股新闻分析师，擅长从新闻中提取投资相关信息。

你的任务是：
1. 识别新闻中的关键信息和对股价的可能影响
2. 评估新闻的重大性（正面/负面/中性）
3. 判断新闻的市场影响程度

分析时要注意：
- 区分直接影响（业绩、政策）和间接影响（行业、情绪）
- 注意新闻的时间效应，有些新闻已经被市场消化
- 结合成交量判断新闻的实际影响力

你的分析要简洁明了，直接指出新闻对投资的含义。"""

    def get_tools(self):
        return [search_stock_news]

    def get_commands(self):
        return ["/新闻"]

    async def run(self, input_text: str, stream_callback, context: Dict[str, Any] = None) -> None:
        """执行新闻分析"""
        keyword = input_text.strip()

        # 获取新闻数据
        news_data = search_stock_news.invoke({
            "keyword": keyword,
            "max_results": 10
        })

        # 构造分析请求
        adapter = LLMToolAdapter()
        prompt = f"""请分析关于 '{keyword}' 的新闻：

{news_data}

请给出：
1. 新闻主要内容概述
2. 关键信息提取
3. 对市场和相关股票的影响
4. 投资建议（谨慎/关注/回避）"""

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
            logger.error(f"News agent error: {e}")
            await stream_callback(f"分析失败: {str(e)}")

        await stream_callback("[DONE]")