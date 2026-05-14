# backend/app/agents/hotmoney_agent.py
import logging
from typing import Dict, Any
from .base import Agent
from .tools.flow_tools import get_northbound_flow, get_hot_money_flow, get_concept_block_info
from app.agent.llm_adapter import LLMToolAdapter

logger = logging.getLogger(__name__)


class HotMoneyAgent(Agent):
    """热钱追踪 Agent - 主力资金追踪"""

    def __init__(self):
        super().__init__(
            name="热钱分析师",
            description="追踪和分析主力资金动向、游资炒作热点"
        )

    def get_system_prompt(self) -> str:
        return """你是一位专业的A股热钱分析师，擅长追踪和分析主力资金动向。

你的任务是：
1. 分析北向资金流向（沪深港通）
2. 追踪游资炒作热点和概念板块
3. 判断资金动向的市场含义

分析时要注意：
- 北向资金往往领先大盘见顶见底
- 游资喜欢炒题材、炒概念，注意龙虎榜数据
- 关注成交量异常放大背后的资金含义
- 对比个股和板块的资金流向

你的分析要指明资金动向和可能的市場含义。"""

    def get_tools(self):
        return [get_northbound_flow, get_hot_money_flow, get_concept_block_info]

    def get_commands(self):
        return ["/热钱"]

    async def run(self, input_text: str, stream_callback, context: Dict[str, Any] = None) -> None:
        """执行热钱分析"""
        stock_code = input_text.strip()

        # 获取资金流数据（目前是stub）
        northbound = get_northbound_flow.invoke({"symbol": stock_code, "days": 5})
        hot_money = get_hot_money_flow.invoke({"symbol": stock_code, "days": 5})

        # 构造分析请求
        adapter = LLMToolAdapter()
        prompt = f"""请分析股票 {stock_code} 的资金流向：

北向资金：
{northbound}

主力资金：
{hot_money}

请给出：
1. 资金流向整体判断（流入/流出/持平）
2. 资金动向的市场含义
3. 短期资金面对股价的影响
4. 综合资金面评估"""

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
            logger.error(f"HotMoney agent error: {e}")
            await stream_callback(f"分析失败: {str(e)}")

        await stream_callback("[DONE]")