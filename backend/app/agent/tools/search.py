# -*- coding: utf-8 -*-
"""Tavily 搜索工具"""

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


class TavilySearchTool:
    """Tavily 搜索工具"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or agent_settings.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"
        self.proxies = get_proxy_dict()

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_answer: bool = True,
        include_raw_content: bool = False,
    ) -> List[Dict[str, Any]]:
        """执行搜索"""
        headers = {"Content-Type": "application/json"}
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
        }

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30,
                proxies=self.proxies,
            )
            response.raise_for_status()
            data = response.json()
            return self._format_results(data)
        except requests.exceptions.RequestException as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    def _format_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """格式化搜索结果"""
        results = []
        for item in data.get("results", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0),
                }
            )
        return results

    def search_stock_news(
        self,
        stock_code: str,
        stock_name: str,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索股票新闻"""
        query = f"{stock_name} {stock_code} 股票 新闻"
        return self.search(query, max_results=max_results)


# 全局搜索工具实例
tavily_search = TavilySearchTool()
