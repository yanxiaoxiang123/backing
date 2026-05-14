# backend/app/api/chat.py
import json
import logging
from typing import List, Dict, Any, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.llm_adapter import LLMToolAdapter
from app.config import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class AgentRequest(BaseModel):
    stock_code: str
    query: str = ""


async def stream_llm_response(messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """流式调用 LLM，返回 SSE 格式"""
    adapter = LLMToolAdapter()

    # 构造 messages 格式
    llm_messages = [{"role": m.role, "content": m.content} for m in messages]

    try:
        response = adapter.chat(llm_messages, stream=True)
        for chunk in response.iter_content(decode_unicode=True):
            if chunk:
                yield f"data: {json.dumps({'content': chunk})}\n\n"
    except Exception as e:
        logger.error(f"LLM streaming error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """普通对话流式输出"""
    return StreamingResponse(
        stream_llm_response([m.model_dump() for m in request.messages]),
        media_type="text/event-stream"
    )