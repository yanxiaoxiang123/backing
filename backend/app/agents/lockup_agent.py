# backend/app/agents/lockup_agent.py
import logging
from typing import Dict, Any
from .base import Agent
from .tools.flow_tools import get_northbound_flow
from .tools.news_tools import search_stock_news
from app.agent.llm_adapter import LLMToolAdapter

logger = logging.getLogger(__name__)


class LockupAgent(Agent):
    """解禁追踪 Agent - 解禁股和减持压力分析"""

    def __init__(self):
        super().__init__(
            name="解禁分析师",
            description="分析股票的解禁股和减持压力"
        )

    def get_system_prompt(self) -> str:
        return """你是一位专业的A股解禁和减持分析师。

你的任务是：
1. 分析股票面临的解禁压力
2. 评估减持对股价的潜在影响
3. 判断市场消化解禁压力的能力

分析时要注意：
- 解禁不等于减持，关注大股东实际意愿
- 区分首发解禁、增发解禁、股权激励解禁
- 解禁前股价往往承压，解禁后需要观察
- 关注大宗交易数据了解机构接盘情况

你的分析要客观评估解禁影响，不夸大也不忽视。"""

    def get_tools(self):
        return [search_stock_news, get_northbound_flow]

    def get_commands(self):
        return ["/解禁"]

    async def run(self, input_text: str, stream_callback, context: Dict[str, Any] = None) -> None:
        """执行解禁分析"""
        stock_code = input_text.strip()

        # 获取相关数据
        news_data = search_stock_news.invoke({
            "keyword": f"{stock_code} 解禁 减持",
            "max_results": 10
        })
        northbound = get_northbound_flow.invoke({"symbol": stock_code, "days": 5})

        # 构造分析请求
        adapter = LLMToolAdapter()
        prompt = f"""请分析股票 {stock_code} 的解禁和减持压力：

相关新闻：
{news_data}

北向资金：
{northbound}

请给出：
1. 解禁压力概述
2. 减持风险评估
3. 市场消化能力判断
4. 综合投资建议"""

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
            logger.error(f"Lockup agent error: {e}")
            await stream_callback(f"分析失败: {str(e)}")

        await stream_callback("[DONE]")