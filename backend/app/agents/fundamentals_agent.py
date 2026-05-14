# backend/app/agents/fundamentals_agent.py
import logging
from typing import Dict, Any
from .base import Agent
from .tools.stock_data import get_stock_price
from app.agent.llm_adapter import LLMToolAdapter

logger = logging.getLogger(__name__)


class FundamentalsAgent(Agent):
    """基本面分析 Agent"""

    def __init__(self):
        super().__init__(
            name="基本面分析师",
            description="分析股票的财务报表和基本面数据"
        )

    def get_system_prompt(self) -> str:
        return """你是一位专业的A股基本面分析师，擅长分析上市公司财报和财务数据。

你的任务是：
1. 分析公司的盈利能力（营收、利润、利润率）
2. 评估公司的财务健康状况（负债率、现金流）
3. 判断公司的成长性和估值水平

分析时要注意：
- A股财报季节性：注意Q4集中确认收入的特点
- 关注扣除非经常性损益后的净利润（扣非净利润）
- 对比行业平均水平，判断公司相对位置
- 注意财报可能存在的财务调节和水分

你的分析要有数据支撑，区分周期性和持续性变化。"""

    def get_tools(self):
        return [get_stock_price]

    def get_commands(self):
        return ["/基本面"]

    async def run(self, input_text: str, stream_callback, context: Dict[str, Any] = None) -> None:
        """执行基本面分析"""
        stock_code = input_text.strip()

        # 获取价格数据作为基本面参考
        price_data = get_stock_price.invoke({"symbol": stock_code, "days": 30})

        # 构造分析请求
        adapter = LLMToolAdapter()
        prompt = f"""请分析股票 {stock_code} 的基本面：

{price_data}

请给出：
1. 公司盈利能力评估
2. 财务健康状况
3. 成长性分析
4. 估值水平判断
5. 综合投资建议"""

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
            logger.error(f"Fundamentals agent error: {e}")
            await stream_callback(f"分析失败: {str(e)}")

        await stream_callback("[DONE]")