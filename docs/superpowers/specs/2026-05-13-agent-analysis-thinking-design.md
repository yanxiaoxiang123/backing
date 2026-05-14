# AI 分析进度透明化设计

## 目标

让用户在分析过程中实时看到 AI 的"思考过程"——正在看什么数据、注意到什么具体信号。

## 数据结构

### AgentStage 增加 thinking 字段

```typescript
interface AgentStage {
  stage_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  opinion?: AgentOpinion       // 完成后才有
  thinking: string[]           // 新增：思考步骤列表，每项是一个发现/关键信号
  error?: string
  duration_s: number
  meta?: Record<string, unknown>
}
```

thinking 示例：
```
["📊 正在加载最近60日K线数据...",
 "🔍 检测到: MA5=12.35, MA10=12.28, MA5 上穿 MA10，形成金叉",
 "📈 检测到: MACD DIF 线从下方穿越 DEA线，形成金叉",
 "⚠️ 注意: RSI(14)=68，已接近超买区域"]
```

## 后端改动

### 1. StageResult 增加 thinking 字段

文件: `backend/app/agent/protocols.py`

```python
@dataclass
class StageResult:
    stage_name: str
    status: StageStatus = StageStatus.PENDING
    opinion: Optional[AgentOpinion] = None
    thinking: List[str] = field(default_factory=list)  # 新增
    error: Optional[str] = None
    duration_s: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "status": self.status.value,
            "opinion": self.opinion.to_dict() if self.opinion else None,
            "thinking": self.thinking,  # 新增
            "error": self.error,
            "duration_s": self.duration_s,
            "meta": self.meta,
        }
```

### 2. _execute_stage() 注入 thinking

文件: `backend/app/agent/orchestrator.py`

每个阶段的 thinking 注入策略：

#### 技术分析阶段 (technical_analysis)

```python
def _execute_stage(self, context, stage_name, prompt):
    result = StageResult(stage_name=stage_name)

    # 阶段开始：记录正在做什么
    result.thinking.append(f"📊 正在获取 {context.stock_code} 的K线数据...")
    if progress_callback:
        progress_callback(progress, result.stages)

    # 调用 LLM
    response = self.llm.chat(messages=..., ...)

    # 从 LLM 响应中抽取关键发现
    thinking_steps = self._extract_thinking_steps(content, stage_name)
    result.thinking.extend(thinking_steps)

    # 继续解析 opinion...
```

`_extract_thinking_steps(content, stage_name)` 负责从 LLM 原始响应中提取结构化的关键发现：

- 技术分析：提取指标名+数值+信号（如 MACD 金叉、RSI 超买）
- 情报分析：提取新闻标题+情感倾向
- 风控分析：提取风险点描述
- 策略分析：提取策略类型+仓位建议
- 决策：提取最终判断+依据

抽取方式：使用正则 + 关键词匹配，从原始 content 中识别出"数值型发现"（如 MA5=12.35、RSI=68）和"结论型发现"（如 形成金叉、处于超买）。

### 3. progress_callback 同步更新 thinking

```python
def _on_progress(progress: float, stages: list):
    job_store.update(
        job_id,
        progress=progress / 100.0,
        message=f"Running: {stage_name}",
        payload={"stages": stages},
    )
```

## 前端改动

### 进度面板：阶段卡片展开显示 thinking

文件: `frontend/src/pages/AgentAnalysis.tsx`

每个阶段卡片渲染逻辑：

```tsx
<Card size="small"
  style={{
    borderLeft: `3px solid ${statusColor}`,
    marginBottom: 8
  }}
>
  <Row align="middle" gutter={12}>
    <Col>{icon}</Col>
    <Col flex="auto">
      <div style={{ fontWeight: 500 }}>{stageLabel}</div>
    </Col>
    <Col>
      <Tag>{statusLabel}</Tag>
    </Col>
  </Row>

  {/* 新增：thinking 列表 */}
  {stage.thinking && stage.thinking.length > 0 && (
    <div style={{
      marginTop: 12,
      padding: '8px 12px',
      background: 'var(--color-bg-secondary)',
      borderRadius: 6,
      fontSize: 13,
      lineHeight: 1.8
    }}>
      {stage.thinking.map((t, i) => (
        <div key={i}>{t}</div>
      ))}
    </div>
  )}
</Card>
```

样式：
- Pending: 灰色，placeholder 骨架
- Running: 蓝色左边框 + thinking 实时滚动
- Completed: 绿色左边框 + 展示所有 thinking + opinion
- Failed: 红色左边框 + 错误信息

## 实现顺序

1. 后端 `protocols.py` - StageResult 增加 thinking 字段
2. 后端 `orchestrator.py` - `_execute_stage` 注入 thinking + 抽取逻辑
3. 前端 `AgentAnalysis.tsx` - 进度面板渲染 thinking 列表