# -*- coding: utf-8 -*-
"""Agent 运行循环"""

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from app.agent.config import agent_settings
from app.agent.llm_adapter import LLMToolAdapter
from app.agent.memory import AgentMemory
from app.agent.protocols import AgentContext, AgentOpinion

logger = logging.getLogger(__name__)


class ToolExecutor:
    """工具执行器"""

    def __init__(self):
        self.tools: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable) -> None:
        """注册工具"""
        self.tools[name] = func

    def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具"""
        if name not in self.tools:
            return {"error": f"Tool {name} not found"}
        try:
            return self.tools[name](**arguments)
        except Exception as e:
            return {"error": str(e)}


def run_agent_loop(
    context: AgentContext,
    system_prompt: str,
    max_steps: int = 6,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_executor: Optional[ToolExecutor] = None,
) -> Dict[str, Any]:
    """Agent 运行循环

    Args:
        context: Agent 执行上下文
        system_prompt: 系统提示词
        max_steps: 最大步数
        tools: 工具定义列表
        tool_executor: 工具执行器

    Returns:
        包含结果的字典
    """
    start_time = time.time()
    llm = None
    memory = AgentMemory()

    # 初始化 LLM
    try:
        llm = LLMToolAdapter()
    except ValueError as e:
        logger.warning(f"LLM not available: {e}")
        return {
            "error": str(e),
            "context": context.to_dict(),
        }

    # 添加系统提示
    memory.add("system", system_prompt)

    # 添加用户查询
    user_message = f"股票代码: {context.stock_code}\n股票名称: {context.stock_name}\n查询: {context.query}"
    memory.add("user", user_message)

    # 构建消息
    messages = memory.get_messages()

    # 步骤记录
    steps: List[Dict[str, Any]] = []
    final_opinion: Optional[AgentOpinion] = None

    for step in range(max_steps):
        step_start = time.time()
        logger.info(f"Agent step {step + 1}/{max_steps}")

        # 调用 LLM
        try:
            response = llm.chat(
                messages=messages,
                temperature=agent_settings.LLM_TEMPERATURE,
                max_tokens=agent_settings.LLM_MAX_TOKENS,
                tools=tools,
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            steps.append(
                {
                    "step": step + 1,
                    "error": str(e),
                    "duration_s": time.time() - step_start,
                }
            )
            break

        # 解析响应
        message = response.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        # 记录步骤
        step_result = {
            "step": step + 1,
            "content": content,
            "tool_calls": [
                {
                    "id": tc.get("id"),
                    "name": tc.get("function", {}).get("name"),
                    "arguments": tc.get("function", {}).get("arguments"),
                }
                for tc in tool_calls
            ],
            "duration_s": time.time() - step_start,
        }

        # 添加助手回复到记忆
        memory.add("assistant", content)

        # 执行工具调用
        if tool_calls and tool_executor:
            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name")
                func_args = tc.get("function", {}).get("arguments", {})

                # 解析参数
                if isinstance(func_args, str):
                    try:
                        func_args = json.loads(func_args)
                    except json.JSONDecodeError:
                        func_args = {}

                # 执行工具
                result = tool_executor.execute(func_name, func_args)
                result_str = json.dumps(result, ensure_ascii=False)

                # 添加工具结果到记忆
                memory.add(
                    "tool",
                    f"Tool {func_name} result: {result_str}",
                    metadata={"tool_name": func_name},
                )

                step_result["tool_results"] = step_result.get("tool_results", [])
                step_result["tool_results"].append(
                    {
                        "name": func_name,
                        "result": result,
                    }
                )

        steps.append(step_result)

        # 检查是否完成（没有更多工具调用）
        if not tool_calls:
            # 尝试解析最终意见
            final_opinion = _parse_opinion(content)
            break

        # 更新消息
        messages = memory.get_messages()

    # 构建结果
    duration = time.time() - start_time

    return {
        "context": context.to_dict(),
        "steps": steps,
        "final_opinion": final_opinion.to_dict() if final_opinion else None,
        "duration_s": duration,
    }


def _parse_opinion(content: str) -> Optional[AgentOpinion]:
    """从内容中解析意见"""
    # 简化实现：尝试从 JSON 中提取
    try:
        # 尝试找到 JSON
        import re

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return AgentOpinion(
                agent_name="agent",
                signal=data.get("signal", "hold"),
                confidence=data.get("confidence", 0.5),
                reason=data.get("reason", content[:200]),
                metadata=data,
            )
    except Exception:
        logger.warning("解析_parse_opinion JSON失败，回退到关键词匹配", exc_info=True)

    # 尝试从文本中提取信号关键词
    content_lower = content.lower()
    signal = "hold"
    if any(k in content_lower for k in ["买入", "买", "buy", "看多", "做多"]):
        signal = "buy"
    elif any(k in content_lower for k in ["卖出", "卖", "sell", "看空", "做空"]):
        signal = "sell"

    return AgentOpinion(
        agent_name="agent",
        signal=signal,
        confidence=0.5,
        reason=content[:200] if content else "",
    )
