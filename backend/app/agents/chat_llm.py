# backend/app/agents/chat_llm.py
import json
import logging
from typing import List, Dict, AsyncGenerator
from app.agent.llm_adapter import LLMToolAdapter

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的A股投资研究助手，名为" backing AI"。你的特点是：
1. 专业：熟悉A股市场、财报分析、技术分析、政策解读
2. 简洁：回答简洁有力，不废话
3. 谨慎：不推荐具体买卖时机，风险提示充分

你可以回答用户关于股票、基金、投资策略等各方面的问题。"""


async def stream_chat(messages: List[Dict[str, str]], system_prompt: str = SYSTEM_PROMPT) -> AsyncGenerator[str, None]:
    """流式调用 LLM 进行普通对话"""
    adapter = LLMToolAdapter()

    # 构造完整的 messages
    full_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        full_messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        response = adapter.chat(full_messages, stream=True)
        for chunk in response.iter_content(decode_unicode=True):
            if chunk:
                yield f"data: {json.dumps({'content': chunk})}\n\n"
    except Exception as e:
        logger.error(f"LLM streaming error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"