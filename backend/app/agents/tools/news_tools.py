# backend/app/agents/tools/news_tools.py
from langchain_core.tools import tool
from typing import Annotated
import requests
import logging

logger = logging.getLogger(__name__)


def search_news(query: str, max_results: int = 10) -> list:
    """使用 Tavily API 搜索新闻"""
    from app.config import settings

    api_key = getattr(settings, 'TAVILY_API_KEY', None)
    if not api_key:
        return fallback_search_news(query, max_results)

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "query": query,
                "api_key": api_key,
                "max_results": max_results,
                "search_depth": "basic"
            },
            timeout=30
        )
        result = response.json()
        return result.get("results", [])
    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return fallback_search_news(query, max_results)


def fallback_search_news(query: str, max_results: int = 10) -> list:
    """备用新闻搜索（返回空列表）"""
    return []


@tool
def search_stock_news(
    keyword: Annotated[str, "搜索关键词（股票名、代码或主题）"],
    max_results: Annotated[int, "返回数量，默认 5"] = 5
) -> str:
    """搜索股票相关新闻"""
    results = search_news(keyword, max_results)

    if not results:
        return f"未找到与 '{keyword}' 相关的新闻"

    output = f"关于 '{keyword}' 的新闻:\n\n"
    for i, r in enumerate(results[:max_results], 1):
        title = r.get("title", "无标题")
        url = r.get("url", "")
        snippet = r.get("content", "")[:200]
        output += f"{i}. {title}\n"
        output += f"   {snippet}...\n"
        output += f"   来源: {url}\n\n"

    return output