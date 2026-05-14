# backend/app/agents/tools/flow_tools.py
from langchain_core.tools import tool
from typing import Annotated
import logging

logger = logging.getLogger(__name__)


@tool
def get_northbound_flow(
    symbol: Annotated[str, "股票代码"],
    days: Annotated[int, "天数，默认 5"] = 5
) -> str:
    """获取北向资金流向（沪深港通）"""
    return f"北向资金数据需要单独的数据源支持，当前版本暂不支持获取 {symbol} 的北向资金明细。"


@tool
def get_hot_money_flow(
    symbol: Annotated[str, "股票代码"],
    days: Annotated[int, "天数，默认 5"] = 5
) -> str:
    """获取游资/主力资金流向"""
    return f"游资资金流向数据需要单独的数据源支持，当前版本暂不支持获取 {symbol} 的主力资金明细。"


@tool
def get_concept_block_info(
    concept: Annotated[str, "概念板块名称"]
) -> str:
    """获取概念板块信息"""
    return f"概念板块 '{concept}' 的详细资金数据需要单独的数据源支持。"
