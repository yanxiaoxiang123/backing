# -*- coding: utf-8 -*-
"""工具注册表"""

from typing import Any, Dict, List, Optional


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(self, tool_def: Dict[str, Any]) -> None:
        """注册工具"""
        name = tool_def.get("name")
        if name:
            self._tools[name] = tool_def

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具定义"""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self._tools.keys())

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有工具定义"""
        return list(self._tools.values())


# 全局工具注册表
tool_registry = ToolRegistry()


def register_default_tools() -> None:
    """注册默认工具"""
    # 搜索工具
    tool_registry.register(
        {
            "name": "search_news",
            "description": "搜索股票相关新闻",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer", "description": "最大结果数"},
                },
                "required": ["query"],
            },
        }
    )

    # 获取 K线数据
    tool_registry.register(
        {
            "name": "get_kline",
            "description": "获取股票K线数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码"},
                    "start_date": {"type": "string", "description": "开始日期"},
                    "end_date": {"type": "string", "description": "结束日期"},
                },
                "required": ["stock_code"],
            },
        }
    )


register_default_tools()
