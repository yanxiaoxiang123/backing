# AI 分析进度透明化实现计划

> **For agentic workers:** Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户在 AI 分析过程中实时看到 AI 的思考过程——正在看什么数据、注意到什么具体信号。

**Architecture:** 在 StageResult 增加 thinking 字段，_execute_stage() 中从 LLM 响应抽取关键发现注入 thinking，前端进度面板渲染 thinking 列表。

**Tech Stack:** Python (FastAPI backend), TypeScript + Ant Design (React frontend)

---

## File Map

| File | Role |
|------|------|
| `backend/app/agent/protocols.py` | StageResult 增加 thinking 字段 |
| `backend/app/agent/orchestrator.py` | _execute_stage 注入 thinking + 抽取逻辑 |
| `backend/app/agent/config.py` | AgentThinkingConfig 配置（可选） |
| `frontend/src/types/index.ts` | AgentStage 接口增加 thinking |
| `frontend/src/pages/AgentAnalysis.tsx` | 进度面板渲染 thinking 列表 |

---

## Task 1: StageResult 增加 thinking 字段

**Files:**
- Modify: `backend/app/agent/protocols.py:48-70`

- [ ] **Step 1: 修改 StageResult dataclass**

```python
@dataclass
class StageResult:
    """Agent 执行结果"""

    stage_name: str
    status: StageStatus = StageStatus.PENDING
    opinion: Optional[AgentOpinion] = None
    thinking: List[str] = field(default_factory=list)  # 新增
    error: Optional[str] = None
    duration_s: float = 0.0
    tokens_used: int = 0
    tool_calls_count: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "status": self.status.value,
            "opinion": self.opinion.to_dict() if self.opinion else None,
            "thinking": self.thinking,  # 新增
            "error": self.error,
            "duration_s": self.duration_s,
            "tokens_used": self.tokens_used,
            "tool_calls_count": self.tool_calls_count,
            "meta": self.meta,
        }
```

- [ ] **Step 2: 提交**

```bash
cd /Users/yan/Desktop/backing && git add backend/app/agent/protocols.py && git commit -m "feat(agent): add thinking field to StageResult"
```

---

## Task 2: 后端 orchestrator 注入 thinking

**Files:**
- Modify: `backend/app/agent/orchestrator.py:329-419`

- [ ] **Step 1: 添加 thinking 抽取方法**

在 `AgentOrchestrator` 类中添加 `_extract_thinking_steps()` 私有方法。这个方法接收 LLM 原始响应 content 和 stage_name，返回关键发现列表。

```python
def _extract_thinking_steps(self, content: str, stage_name: str) -> List[str]:
    """从 LLM 响应中抽取关键发现"""
    thinking = []
    content_lower = content.lower()

    if stage_name == "technical_analysis":
        # 提取指标数值型发现
        import re

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

        # 成交量异常
        if any(k in content_lower for k in ['放量', '缩量', '量能放大', '量能萎缩']):
            vol_keywords = re.findall(r'量[能]?[放缩]?[大]?[萎缩]?', content)
            if vol_keywords:
                thinking.append(f"📊 成交量: {vol_keywords[0]}")

    elif stage_name == "intel":
        # 提取新闻情感
        news_matches = re.findall(r'标题[：:]\s*["""](.+?)["""]', content)
        if news_matches:
            thinking.append(f"📰 找到 {len(news_matches)} 条相关新闻")

        # 情感判断
        if any(k in content_lower for k in ['利好', '看多', '买入', '上涨']):
            thinking.append("📈 消息面偏利好")
        elif any(k in content_lower for k in ['利空', '看空', '卖出', '下跌']):
            thinking.append("📉 消息面偏利空")

    elif stage_name == "risk":
        # 提取风险点
        risk_keywords = ['高风险', '中等风险', '低风险', '风险', '止损', '流动性']
        for kw in risk_keywords:
            if kw in content_lower:
                thinking.append(f"⚠️ 风控: {kw}")

    elif stage_name == "strategy":
        # 提取策略建议
        strategy_keywords = ['仓位', '持仓', '止盈', '止损', '策略']
        for kw in strategy_keywords:
            if kw in content_lower:
                thinking.append(f"📋 策略: {kw}")

    elif stage_name == "decision":
        # 提取最终决策依据
        if '买入' in content or 'buy' in content_lower:
            thinking.append("✅ 决策: 建议买入")
        elif '卖出' in content or 'sell' in content_lower:
            thinking.append("✅ 决策: 建议卖出")
        else:
            thinking.append("✅ 决策: 建议观望")

    # 如果什么都没抽到，截取前100字作为摘要
    if not thinking and content:
        snippet = content[:150].replace('\n', ' ').strip()
        thinking.append(f"💭 {snippet}...")

    return thinking[:6]  # 最多6条，避免过长
```

- [ ] **Step 2: 修改 _execute_stage 方法**

在 `_execute_stage()` 中：
1. 阶段开始时追加"正在做X"的 thinking
2. LLM 返回后调用 `_extract_thinking_steps()` 追加发现

找到 `_execute_stage` 方法，在开始时和 LLM 调用后插入 thinking：

```python
def _execute_stage(
    self,
    context: AgentContext,
    stage_name: str,
    prompt: str,
) -> StageResult:
    result = StageResult(stage_name=stage_name)
    result.status = StageStatus.RUNNING  # 新增：标记为运行中
    start_time = time.time()

    # 阶段开始：追加第一条 thinking
    stage_start_msg = {
        "technical_analysis": f"📊 正在分析 {context.stock_code} 技术面...",
        "intel": f"🔍 正在收集 {context.stock_code} 情报信息...",
        "risk": f"⚖️ 正在评估 {context.stock_code} 风险因素...",
        "strategy": f"📋 正在评估 {context.stock_code} 策略适用性...",
        "decision": f"🎯 正在综合各维度分析给出最终决策...",
    }.get(stage_name, f"🔄 正在执行 {stage_name}...")
    result.thinking.append(stage_start_msg)

    try:
        # ... 现有逻辑 (news_items 处理) ...

        # 调用 LLM
        response = self.llm.chat(...)

        # 解析响应 (现有逻辑不变)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 新增：从 LLM 响应中抽取关键发现
        key_findings = self._extract_thinking_steps(content, stage_name)
        result.thinking.extend(key_findings)

        # ... 现有 JSON 解析逻辑 ...
```

- [ ] **Step 3: 运行测试验证**

```bash
cd /Users/yan/Desktop/backing/backend && python -c "from app.agent.orchestrator import AgentOrchestrator; print('orchestrator import OK')"
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/agent/orchestrator.py && git commit -m "feat(agent): inject thinking steps into stage execution"
```

---

## Task 3: 前端 AgentStage 类型更新

**Files:**
- Modify: `frontend/src/types/index.ts:253-260`

- [ ] **Step 1: 更新 AgentStage 接口**

```typescript
export interface AgentStage {
  stage_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  opinion?: AgentOpinion
  thinking: string[]  // 新增
  error?: string
  duration_s: number
  meta?: Record<string, unknown>
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/types/index.ts && git commit -m "feat(frontend): add thinking field to AgentStage type"
```

---

## Task 4: 前端进度面板渲染 thinking

**Files:**
- Modify: `frontend/src/pages/AgentAnalysis.tsx:529-648`

- [ ] **Step 1: 更新阶段卡片渲染逻辑**

找到进度面板阶段卡片的渲染部分（`jobStages.map` 部分），在现有结构基础上增加 thinking 列表渲染：

在 `<Card size="small" ...>` 内部，`</Row>` 之后添加：

```tsx
{/* 新增：thinking 列表 */}
{(stage.thinking && stage.thinking.length > 0) && (
  <div style={{
    marginTop: 12,
    padding: '8px 12px',
    background: 'var(--color-bg-secondary)',
    borderRadius: 6,
    fontSize: 13,
    lineHeight: 1.8
  }}>
    {stage.thinking.map((t, i) => (
      <div key={i} style={{ marginBottom: 4 }}>{t}</div>
    ))}
  </div>
)}
```

具体位置在 [AgentAnalysis.tsx:568-609](./frontend/src/pages/AgentAnalysis.tsx#L568-L609) 的 `jobStages.map` 循环内，每个阶段的 `<Card size="small">` 组件里。

- [ ] **Step 2: 验证构建**

```bash
cd /Users/yan/Desktop/backing/frontend && npm run build 2>&1 | head -50
```

预期：无 TypeScript 错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/AgentAnalysis.tsx frontend/src/types/index.ts && git commit -m "feat(frontend): render AI thinking steps in analysis progress panel"
```

---

## Task 5: 集成测试

- [ ] **Step 1: 启动后端**

```bash
cd /Users/yan/Desktop/backing/backend && python main.py &
sleep 3
```

- [ ] **Step 2: 启动前端**

```bash
cd /Users/yan/Desktop/backing/frontend && npm run dev &
```

- [ ] **Step 3: 手动测试**

1. 打开 http://localhost:5173 进入 AI Agent 分析页面
2. 选择一只股票（如 000001）
3. 选择 standard 模式
4. 点击"开始分析"
5. 观察进度面板是否显示 thinking 步骤（蓝色加载中卡片应显示"正在分析技术面..."等实时进度）

预期：每个阶段卡片内能看到 AI 的思考过程，Running 阶段 thinking 实时更新

---

## 验证清单

- [ ] StageResult.to_dict() 包含 thinking 字段
- [ ] orchestrator._execute_stage() 阶段开始时有 thinking 追加
- [ ] orchestrator._execute_stage() LLM 响应后有 key_findings 抽取和追加
- [ ] 前端 AgentStage 类型包含 thinking: string[]
- [ ] 前端进度面板每个阶段卡片展开显示 thinking 列表
- [ ] 端到端测试：分析一只股票，进度面板显示实时 thinking