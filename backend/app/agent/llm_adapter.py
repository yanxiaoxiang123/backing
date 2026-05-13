# -*- coding: utf-8 -*-
"""LLM 适配器 - DeepSeek"""

import json
import logging
from typing import Any, Dict, List, Optional
import requests
from app.agent.config import agent_settings

logger = logging.getLogger(__name__)


def get_proxy_dict() -> Optional[Dict[str, str]]:
    """获取代理配置"""
    from app.config import settings

    if not getattr(settings, "USE_PROXY", False):
        return None

    proxy_host = getattr(settings, "PROXY_HOST", None)
    proxy_port = getattr(settings, "PROXY_PORT", None)
    if not proxy_host or not proxy_port:
        raise ValueError(
            "USE_PROXY is enabled but PROXY_HOST or PROXY_PORT is not set in configuration"
        )
    proxy_url = f"http://{proxy_host}:{proxy_port}"

    return {"http": proxy_url, "https": proxy_url}


class LLMToolAdapter:
    """DeepSeek LLM 适配器"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or agent_settings.DEEPSEEK_API_KEY
        self.base_url = base_url or agent_settings.DEEPSEEK_BASE_URL
        self.model = model or agent_settings.DEEPSEEK_MODEL
        self.proxies = get_proxy_dict()

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """发送聊天请求"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = tools

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
                proxies=self.proxies,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM request failed: {e}")
            raise

    def chat_with_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """请求 JSON 格式的响应"""
        response = self.chat(
            messages=messages,
            temperature=temperature,
        )
        content = response["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 JSON
            import re

            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise

    def count_tokens(self, text: str) -> int:
        """估算 token 数量（简化版）"""
        return len(text) // 4
