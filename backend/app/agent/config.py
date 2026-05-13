# -*- coding: utf-8 -*-
"""Agent 配置模块"""

from pydantic_settings import BaseSettings
from typing import Optional


class AgentSettings(BaseSettings):
    """Agent 相关配置"""

    # DeepSeek API 配置
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Tavily 搜索配置
    TAVILY_API_KEY: Optional[str] = None

    # Agent 编排配置
    AGENT_ORCHESTRATOR_MODE: str = "standard"  # quick/standard/full/strategy
    AGENT_MAX_STEPS: int = 6
    AGENT_ORCHESTRATOR_TIMEOUT_S: int = 600

    # 记忆配置
    AGENT_MEMORY_ENABLED: bool = False

    # 风控配置
    AGENT_RISK_OVERRIDE: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


agent_settings = AgentSettings()
