"""Agent 流水线执行

从 orchestrator.py 拆分出的部分：

* ``OrchestratorResult`` — 编排结果类型
* ``MODE_PIPELINES`` — 各模式的阶段定义（阶段名 + 完成进度）
* ``run_pipeline`` — 按模式逐阶段执行、聚合意见、产出最终决策
* 单阶段执行（``_execute_stage``）与 LLM 响应解析（``_extract_thinking_steps``）

行为与原 orchestrator 完全一致（quick/standard/full/strategy 四种模式的
阶段门控与进度回调保持不变），仅将重复的四个 ``_run_*`` 方法收敛为一份
通用实现，降低回归范围。
"""

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.agent.prompts import (
    decision_prompt,
    intel_prompt,
    risk_prompt,
    strategy_prompt,
    technical_prompt,
)
from app.agent.protocols import (
    AgentContext,
    AgentOpinion,
    StageResult,
    StageStatus,
    normalize_decision_signal,
)
from app.agent.tools.search import tavily_search

# 模式 -> [(阶段名, 完成时进度), ...]
MODE_PIPELINES: dict[str, list[tuple[str, float]]] = {
    "quick": [("technical_analysis", 50.0), ("decision", 100.0)],
    "standard": [
        ("technical_analysis", 33.0),
        ("intel", 66.0),
        ("decision", 100.0),
    ],
    "full": [
        ("technical_analysis", 25.0),
        ("intel", 50.0),
        ("risk", 75.0),
        ("decision", 100.0),
    ],
    "strategy": [
        ("technical_analysis", 20.0),
        ("intel", 40.0),
        ("risk", 60.0),
        ("strategy", 80.0),
        ("decision", 100.0),
    ],
}

_STAGE_PROMPTS: dict[str, Callable[..., str]] = {
    "technical_analysis": technical_prompt,
    "intel": intel_prompt,
    "risk": risk_prompt,
    "strategy": strategy_prompt,
    "decision": decision_prompt,
}


@dataclass
class OrchestratorResult:
    """编排结果"""

    success: bool = False
    final_signal: str = "hold"
    final_confidence: float = 0.0
    final_reason: str = ""
    opinions: list[dict[str, Any]] = field(default_factory=list)
    stages: list[dict[str, Any]] = field(default_factory=list)
    duration_s: float = 0.0
    error: str | None = None


def run_pipeline(
    context: AgentContext,
    llm,
    progress_callback: Callable[[float, list[dict[str, Any]]], None] | None = None,
) -> OrchestratorResult:
    """按 context.mode 定义的阶段顺序执行分析，返回编排结果。

    门控规则（与原实现一致）：
    * quick：技术分析失败则不再执行决策阶段；
    * standard：技术分析失败时跳过情报阶段，但决策阶段始终执行；
    * full / strategy：所有阶段始终执行。
    """
    mode = context.mode
    stages = MODE_PIPELINES.get(mode)
    if stages is None:
        return OrchestratorResult(error=f"Unknown mode: {mode}")

    result = OrchestratorResult()

    # 预填充所有阶段为 PENDING，保证前端始终看到完整列表
    for name, _progress in stages:
        pending = StageResult(stage_name=name)
        pending.status = StageStatus.PENDING
        result.stages.append(pending.to_dict())

    for i, (name, progress) in enumerate(stages):
        # standard 模式：技术分析失败时跳过情报阶段
        if (
            i == 1
            and name == "intel"
            and mode == "standard"
            and result.stages[0]["status"] != StageStatus.COMPLETED.value
        ):
            continue

        stage = _execute_stage(context, llm, name, result.opinions)
        result.stages[i] = stage.to_dict()
        if progress_callback:
            progress_callback(progress, result.stages)

        if stage.opinion:
            result.opinions.append(stage.opinion.to_dict())

        # quick 模式：技术分析失败则中止（决策阶段保持 PENDING）
        if i == 0 and mode == "quick" and stage.status != StageStatus.COMPLETED:
            break

    # 最终决策取自最后一个已完成的意见（即决策阶段）
    last = result.stages[-1]
    if last["status"] == StageStatus.COMPLETED.value and result.opinions:
        last_opinion = result.opinions[-1]
        result.final_signal = last_opinion["signal"]
        result.final_confidence = last_opinion["confidence"]
        result.final_reason = last_opinion["reason"]
        result.success = True

    return result


def _execute_stage(
    context: AgentContext,
    llm,
    stage_name: str,
    opinions: list[dict[str, Any]] | None = None,
) -> StageResult:
    """执行单个阶段

    *opinions*：决策阶段需要已累积的各维度意见来构造提示词。
    """
    result = StageResult(stage_name=stage_name)
    result.status = StageStatus.RUNNING
    start_time = time.time()

    stage_start_msg = {
        "technical_analysis": f"📊 正在分析 {context.stock_code} 技术面...",
        "intel": f"🔍 正在收集 {context.stock_code} 情报信息...",
        "risk": f"⚖️ 正在评估 {context.stock_code} 风险因素...",
        "strategy": f"📋 正在评估 {context.stock_code} 策略适用性...",
        "decision": "🎯 正在综合各维度分析给出最终决策...",
    }.get(stage_name, f"🔄 正在执行 {stage_name}...")
    result.thinking.append(stage_start_msg)

    try:
        if stage_name == "intel":
            news_items = tavily_search.search_stock_news(
                stock_code=context.stock_code,
                stock_name=context.stock_name or context.stock_code,
                max_results=8,
            )
            result.meta["news_items"] = news_items

        # 构建消息
        prompt_fn = _STAGE_PROMPTS[stage_name]
        system_content = (
            prompt_fn(context, opinions or [])
            if stage_name == "decision"
            else prompt_fn(context)
        )
        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": _build_stage_user_content(
                    context=context,
                    stage_name=stage_name,
                    news_items=result.meta.get("news_items", []),
                ),
            },
        ]

        # 调用 LLM
        response = llm.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )

        # 解析响应
        content = (
            response.get("choices", [{}])[0].get("message", {}).get("content", "")
        )

        # 从 LLM 响应中抽取关键发现
        key_findings = _extract_thinking_steps(content, stage_name)
        result.thinking.extend(key_findings)

        # 尝试解析 JSON
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            opinion = AgentOpinion(
                agent_name=stage_name,
                signal=normalize_decision_signal(data.get("signal", "hold")),
                confidence=data.get("confidence", 0.5),
                reason=data.get("reason", data.get("analysis", content[:200])),
                metadata=data,
            )
            result.opinion = opinion
            result.status = StageStatus.COMPLETED
        else:
            # 简单解析
            content_lower = content.lower()
            signal = "hold"
            if any(
                k in content_lower for k in ["买入", "买", "buy", "看多", "做多"]
            ):
                signal = "buy"
            elif any(
                k in content_lower for k in ["卖出", "卖", "sell", "看空", "做空"]
            ):
                signal = "sell"

            opinion = AgentOpinion(
                agent_name=stage_name,
                signal=signal,
                confidence=0.5,
                reason=content[:300],
                metadata={"raw": content},
            )
            result.opinion = opinion
            result.status = StageStatus.COMPLETED

        result.duration_s = time.time() - start_time

    except Exception as exc:
        result.status = StageStatus.FAILED
        result.error = str(exc)
        result.duration_s = time.time() - start_time

    return result


def _extract_thinking_steps(content: str, stage_name: str) -> list[str]:
    """从 LLM 响应中抽取关键发现"""
    thinking = []
    content_lower = content.lower()

    if stage_name == "technical_analysis":

        # MA 交叉
        ma_matches = re.findall(r'ma[5,10,20,60,120][=\s]*[\d.]+', content_lower)
        if ma_matches:
            for m in ma_matches[:3]:
                thinking.append(f"📊 检测到: {m.upper()}")

        # MACD 金叉/死叉
        if 'macd' in content_lower and ('金叉' in content or '交叉' in content_lower):
            direction = "金叉" if any(k in content_lower for k in ['上方', '上穿', '金叉']) else "死叉"
            thinking.append(f"📈 MACD 形成{direction}")

        # RSI
        rsi_match = re.search(r'RSI[^0-9]*(\d+)', content, re.IGNORECASE)
        if rsi_match:
            rsi_val = int(rsi_match.group(1))
            if rsi_val > 70:
                thinking.append(f"⚠️ 注意: RSI({rsi_val}) 处于超买区域")
            elif rsi_val < 30:
                thinking.append(f"⚠️ 注意: RSI({rsi_val}) 处于超卖区域")
            else:
                thinking.append(f"📊 RSI({rsi_val}) 运行正常")

        # 成交量
        if any(k in content_lower for k in ['放量', '缩量', '量能放大', '量能萎缩']):
            vol_keywords = re.findall(r'量[能]?[放缩]?[大]?[萎缩]?', content)
            if vol_keywords:
                thinking.append(f"📊 成交量: {vol_keywords[0]}")

    elif stage_name == "intel":
        news_matches = re.findall(r'标题[：:]\s*["""](.+?)["""]', content)
        if news_matches:
            thinking.append(f"📰 找到 {len(news_matches)} 条相关新闻")

        if any(k in content_lower for k in ['利好', '看多', '买入', '上涨']):
            thinking.append("📈 消息面偏利好")
        elif any(k in content_lower for k in ['利空', '看空', '卖出', '下跌']):
            thinking.append("📉 消息面偏利空")

    elif stage_name == "risk":
        risk_keywords = ['高风险', '中等风险', '低风险', '风险', '止损', '流动性']
        for kw in risk_keywords:
            if kw in content_lower:
                thinking.append(f"⚠️ 风控: {kw}")

    elif stage_name == "strategy":
        strategy_keywords = ['仓位', '持仓', '止盈', '止损', '策略']
        for kw in strategy_keywords:
            if kw in content_lower:
                thinking.append(f"📋 策略: {kw}")

    elif stage_name == "decision":
        if '买入' in content or 'buy' in content_lower:
            thinking.append("✅ 决策: 建议买入")
        elif '卖出' in content or 'sell' in content_lower:
            thinking.append("✅ 决策: 建议卖出")
        else:
            thinking.append("✅ 决策: 建议观望")

    if not thinking and content:
        snippet = content[:150].replace('\n', ' ').strip()
        thinking.append(f"💭 {snippet}...")

    return thinking[:6]


def _build_stage_user_content(
    context: AgentContext,
    stage_name: str,
    news_items: list[dict[str, Any]] | None = None,
) -> str:
    content = f"股票: {context.stock_name or context.stock_code} ({context.stock_code})\n{context.query}"
    if stage_name != "intel" or not news_items:
        return content

    lines = []
    for idx, item in enumerate(news_items, start=1):
        lines.append(
            f"{idx}. 标题: {item.get('title', '')}\n"
            f"链接: {item.get('url', '')}\n"
            f"摘要: {item.get('content', '')[:300]}"
        )

    return f"{content}\n\nTavily 搜索到的相关新闻:\n" + "\n\n".join(lines)
