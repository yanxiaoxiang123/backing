# backend/app/agents/policy_agent.py
import logging
from typing import Dict, Any
from .base import Agent
from .tools.news_tools import search_stock_news
from app.agent.llm_adapter import LLMToolAdapter

logger = logging.getLogger(__name__)


class PolicyAgent(Agent):
    """政策分析 Agent"""

    def __init__(self):
        super().__init__(
            name="政策分析师",
            description="分析股票相关的政策影响和政策动向"
        )

    def get_system_prompt(self) -> str:
        return """你是一位专业的A股政策分析师，擅长分析政策和监管动向对市场的影响。

你的任务是：
1. 分析相关政策对行业和公司的影响
2. 判断政策是支持性还是限制性
3. 评估政策的持续性和影响程度

分析时要注意：
- A股政策敏感性：政策往往对行业有重大影响
- 区分实质政策和支持性表态（情绪信号）
- 关注政策落地进度和实际效果
- 注意政策的地域和时间范围

你的分析要指明政策的实质影响和持续性。"""

    def get_tools(self):
        return [search_stock_news]

    def get_commands(self):
        return ["/政策"]

    async def run(self, input_text: str, stream_callback, context: Dict[str, Any] = None) -> None:
        """执行政策分析"""
        stock_code = input_text.strip()

        # 获取相关新闻
        news_data = search_stock_news.invoke({
            "keyword": f"{stock_code} 政策",
            "max_results": 10
        })

        # 构造分析请求
        adapter = LLMToolAdapter()
        prompt = f"""请分析股票 {stock_code} 相关的政策影响：

{news_data}

请给出：
1. 相关政策概述
2. 政策对公司的影响
3. 政策持续性和确定性
4. 综合政策评估和建议"""

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
            logger.error(f"Policy agent error: {e}")
            await stream_callback(f"分析失败: {str(e)}")

        await stream_callback("[DONE]")