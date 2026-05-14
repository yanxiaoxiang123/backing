# backend/app/agents/technical_agent.py
import json
import logging
from typing import Dict, Any
from .base import Agent
from .tools.stock_data import get_stock_price, get_stock_indicators
from app.agent.llm_adapter import LLMToolAdapter

logger = logging.getLogger(__name__)


class TechnicalAgent(Agent):
    """技术分析 Agent"""

    def __init__(self):
        super().__init__(
            name="技术分析师",
            description="分析股票的技术面，包括 K线、均线、MACD、RSI 等指标"
        )

    def get_system_prompt(self) -> str:
        return """你是一位专业的A股技术分析师。你的任务是：
1. 分析股票的技术面走势
2. 识别关键支撑位和阻力位
3. 判断短期和中期的趋势方向
4. 结合量价关系给出分析结论

分析时要注意：
- A股涨跌停制度（主板 ±10%，科创/创业板 ±20%）
- T+1 交易制度对短线的影响
- 成交量放大/缩小的含义

你的分析要具体、有数据支撑，避免空洞的描述。"""

    def get_tools(self):
        return [get_stock_price, get_stock_indicators]

    def get_commands(self):
        return ["/技术"]

    async def run(self, input_text: str, stream_callback, context: Dict[str, Any] = None) -> None:
        """执行技术分析"""
        stock_code = input_text.strip()

        # 获取数据
        price_data = get_stock_price.invoke({"symbol": stock_code, "days": 30})
        indicator_data = get_stock_indicators.invoke({"symbol": stock_code})

        # 构造分析请求
        adapter = LLMToolAdapter()
        prompt = f"""请分析股票 {stock_code} 的技术面：

{price_data}

{indicator_data}

请给出：
1. 当前趋势判断（上涨/下跌/震荡）
2. 关键支撑位和阻力位
3. 主要技术信号（均线、MACD、RSI）
4. 综合结论和建议"""

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
            logger.error(f"Technical agent error: {e}")
            await stream_callback(f"分析失败: {str(e)}")

        await stream_callback("[DONE]")