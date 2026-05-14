# backend/app/agents/base.py
from abc import ABC, abstractmethod
from typing import List, AsyncGenerator, Dict, Any
from langchain_core.tools import BaseTool


class Agent(ABC):
    """AI Agent 基类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def get_system_prompt(self) -> str:
        """返回 Agent 的系统提示词"""
        pass

    @abstractmethod
    async def run(
        self,
        input_text: str,
        stream_callback,
        context: Dict[str, Any] = None
    ) -> None:
        """执行 Agent 分析，流式输出结果"""
        pass

    def get_tools(self) -> List[BaseTool]:
        """返回该 Agent 可用的工具列表"""
        return []

    def get_commands(self) -> List[str]:
        """返回该 Agent 对应的斜杠命令"""
        return []