# backend/app/api/chat.py
import json
import logging
from typing import List, Dict, Any, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.llm_adapter import LLMToolAdapter
from app.agents.technical_agent import TechnicalAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.news_agent import NewsAgent
from app.agents.fundamentals_agent import FundamentalsAgent
from app.agents.policy_agent import PolicyAgent
from app.agents.hotmoney_agent import HotMoneyAgent
from app.agents.lockup_agent import LockupAgent
from app.config import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

technical_agent = TechnicalAgent()
sentiment_agent = SentimentAgent()
news_agent = NewsAgent()
fundamentals_agent = FundamentalsAgent()
policy_agent = PolicyAgent()
hotmoney_agent = HotMoneyAgent()
lockup_agent = LockupAgent()


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


@router.post("/chat/agent/technical")
async def chat_technical(request: AgentRequest):
    """技术分析 Agent"""
    async def stream_callback(chunk):
        return chunk

    async def generate():
        adapter = LLMToolAdapter()
        try:
            async for chunk in technical_agent.run(request.stock_code, stream_callback, {}):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat/agent/sentiment")
async def chat_sentiment(request: AgentRequest):
    """情绪分析 Agent"""
    async def stream_callback(chunk):
        return chunk

    async def generate():
        try:
            async for chunk in sentiment_agent.run(request.stock_code, stream_callback, {}):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat/agent/news")
async def chat_news(request: AgentRequest):
    """新闻分析 Agent"""
    async def stream_callback(chunk):
        return chunk

    async def generate():
        try:
            async for chunk in news_agent.run(request.stock_code, stream_callback, {}):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat/agent/fundamentals")
async def chat_fundamentals(request: AgentRequest):
    """基本面分析 Agent"""
    async def stream_callback(chunk):
        return chunk

    async def generate():
        try:
            async for chunk in fundamentals_agent.run(request.stock_code, stream_callback, {}):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat/agent/policy")
async def chat_policy(request: AgentRequest):
    """政策分析 Agent"""
    async def stream_callback(chunk):
        return chunk

    async def generate():
        try:
            async for chunk in policy_agent.run(request.stock_code, stream_callback, {}):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat/agent/hotmoney")
async def chat_hotmoney(request: AgentRequest):
    """热钱追踪 Agent"""
    async def stream_callback(chunk):
        return chunk

    async def generate():
        try:
            async for chunk in hotmoney_agent.run(request.stock_code, stream_callback, {}):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat/agent/lockup")
async def chat_lockup(request: AgentRequest):
    """解禁追踪 Agent"""
    async def stream_callback(chunk):
        return chunk

    async def generate():
        try:
            async for chunk in lockup_agent.run(request.stock_code, stream_callback, {}):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")