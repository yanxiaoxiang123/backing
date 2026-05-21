# 股票筛选 AI Agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 选股能力融入 `/screener` 页面，无需用户输入参数，按固定条件筛选全市场股票，输出 TOP 5 推荐及 AI 分析理由，每个阶段显示详细进度。

**Architecture:** 三阶段流程：① mootdx 并行扫描全市场计算技术指标 ② 综合评分排序选 TOP 5 ③ AI Agent 深度分析 TOP 5（复用 orchestrator）。Job 模式提交任务，前端轮询进度。

**Tech Stack:** FastAPI + SQLAlchemy + mootdx + DeepSeek LLM + React

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/services/screener_service.py` | 选股核心逻辑：并行扫描、指标计算、评分排序 |
| `backend/app/api/screener_agent.py` | API 入口：Job 提交 + 状态查询 |
| `backend/app/schemas/schemas.py` | 新增 `ScreenerAgentRequest/Response` |
| `backend/main.py` | 注册 screener_agent router |
| `frontend/src/pages/Screener.tsx` | 重写为 AI 选股界面 |
| `frontend/src/services/api.ts` | 新增 `runScreenerAgent` API |

---

## Task 1: 后端 — 选股核心服务 screener_service.py

**Files:**
- Create: `backend/app/services/screener_service.py`
- Modify: `backend/app/services/realtime_service.py`（如需新增方法）
- Test: `backend/tests/test_screener_service.py`

- [ ] **Step 1: 写 Schema 定义（写到 schemas.py）**

```python
# backend/app/schemas/schemas.py 新增

class ScreenerStockResult(BaseModel):
    """单只股票筛选结果"""
    stock_code: str
    stock_name: str
    close: float
    volume: int
    change_pct: Optional[float] = None
    # 技术指标
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    dividend_rate: Optional[float] = None
    ma5: float
    ma10: float
    ma20: float
    macd_dif: float
    macd_dea: float
    macd_hist: float
    rsi: float
    volume_ratio: float  # 今日/20日均量
    # 评分
    composite_score: float = 0.0
    # AI 分析结果（后续填充）
    ai_signal: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_reason: Optional[str] = None

class ScreenerStageUpdate(BaseModel):
    """Job 进度更新"""
    stage: str  # "scanning" | "scoring" | "ai_analysis"
    current: int  # 当前处理到第几只
    total: int    # 总共多少只
    message: str  # 展示给用户的文字

class ScreenerAgentResponse(BaseModel):
    success: bool
    total_scanned: int
    results: List[ScreenerStockResult]  # TOP 5 排序结果
    execution_time_s: float
```

- [ ] **Step 2: 创建 screener_service.py — parallel_scan 方法**

```python
# backend/app/services/screener_service.py

class ScreenerService:
    """选股服务 — 计算技术指标 + 综合评分"""

    def __init__(self):
        self.indicators_weights = {
            'valuation': 0.30,   # PE/PB
            'profit': 0.25,      # ROE
            'technical': 0.25,   # MA多头/MACD/量能
            'dividend': 0.20,    # 股息率
        }

    def parallel_scan_stocks(self, stocks: List[Stock], offset: int = 120,
                            max_workers: int = 10,
                            progress_callback: Optional[Callable] = None) -> List[dict]:
        """并行扫描全市场股票，计算技术指标"""
        results: List[dict] = []
        total = len(stocks)
        completed = 0

        def process_one(stock: Stock) -> Optional[dict]:
            symbol = stock.code.split('.')[-1] if '.' in stock.code else stock.code
            bars = realtime_service.normalise_bars(symbol=symbol, frequency=9, offset=offset)
            if len(bars) < 30:
                return None
            df = pd.DataFrame(bars)
            indicators = self._compute_indicators(df)
            indicators['stock_code'] = stock.code
            indicators['stock_name'] = stock.name
            return indicators

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_one, s): s for s in stocks}
            for future in as_completed(futures):
                result = future.result()
                completed += 1
                if result:
                    results.append(result)
                if progress_callback:
                    progress_callback('scanning', completed, total,
                                      f'正在扫描全市场股票... ({completed}/{total})')
        return results

    def _compute_indicators(self, df: pd.DataFrame) -> dict:
        """计算单只股票的所有技术指标"""
        close = df['close']
        volume = df['volume']
        results = {}

        # 均线
        results['ma5'] = float(TechnicalFactors.SMA(close, 5).iloc[-1])
        results['ma10'] = float(TechnicalFactors.SMA(close, 10).iloc[-1])
        results['ma20'] = float(TechnicalFactors.SMA(close, 20).iloc[-1])

        # MACD
        macd = TechnicalFactors.MACD(close, 12, 26, 9)
        results['macd_dif'] = float(macd['dif'].iloc[-1])
        results['macd_dea'] = float(macd['dea'].iloc[-1])
        results['macd_hist'] = float(macd['hist'].iloc[-1])

        # RSI
        results['rsi'] = float(TechnicalFactors.RSI(close, 14).iloc[-1])

        # 成交量比
        vol_ma = TechnicalFactors.VolumeMA(volume, 20)
        results['volume_ratio'] = float(volume.iloc[-1] / vol_ma.iloc[-1]) if vol_ma.iloc[-1] > 0 else 0

        # 评分
        results['composite_score'] = self._calc_composite_score(results)

        return results

    def _calc_composite_score(self, indicators: dict) -> float:
        """计算综合评分（0-100）"""
        score = 0.0

        # 技术面 25%
        tech_score = 0
        if indicators.get('ma5', 0) > indicators.get('ma10', 0) > indicators.get('ma20', 0):
            tech_score += 10  # 均线多头
        if indicators.get('macd_hist', 0) > 0:
            tech_score += 8  # MACD 红柱
        if indicators.get('rsi', 50) < 30:
            tech_score += 7  # RSI 超卖
        if indicators.get('volume_ratio', 0) > 1.5:
            tech_score += 5  # 成交量放大
        score += tech_score * 0.25 / 30 * 100  # 归一化

        # 估值 30% — mootdx 无法直接获取，留给 AI 补充
        # 股息 20% — 同上
        # 盈利 25% — 同上

        return round(score, 2)
```

- [ ] **Step 3: 添加 filter_and_rank 方法**

```python
    def filter_and_rank(self, results: List[dict],
                        progress_callback: Optional[Callable] = None) -> List[dict]:
        """过滤 + 评分排序，返回 TOP 5"""
        # 过滤：MA 多头 + MACD 金叉 + 成交量放大
        filtered = [
            r for r in results
            if r.get('ma5', 0) > r.get('ma10', 0) > r.get('ma20', 0)  # 均线多头
            and r.get('macd_hist', 0) > 0  # MACD 红柱（金叉）
            and r.get('volume_ratio', 0) > 1.5  # 成交量放大
        ]

        if progress_callback:
            progress_callback('scoring', 0, 1, f'符合条件的股票: {len(filtered)} 只')

        # 排序：综合评分降序
        filtered.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

        return filtered[:5]  # TOP 5
```

- [ ] **Step 4: 测试 parallel_scan（用真实股票）**

Run: `cd backend && python -c "from app.services.screener_service import ScreenerService; ss = ScreenerService(); from app.config import get_db; from app.models.models import Stock; db = next(get_db()); stocks = db.query(Stock).limit(20).all(); results = ss.parallel_scan_stocks(stocks, offset=120); print(f'扫描了 {len(results)} 只'); db.close()"`

- [ ] **Step 5: 提交代码**

```bash
git add backend/app/services/screener_service.py backend/app/schemas/schemas.py
git commit -m "feat: add ScreenerService with parallel scan and indicators"
```

---

## Task 2: 后端 — API 入口 screener_agent.py

**Files:**
- Create: `backend/app/api/screener_agent.py`
- Modify: `backend/main.py`（注册 router）
- Test: `backend/tests/test_screener_agent.py`

- [ ] **Step 1: 创建 screener_agent.py — submit endpoint**

```python
# backend/app/api/screener_agent.py

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Callable
import time

from app.auth import get_current_api_key
from app.config import get_db
from app.limiter import limiter
from app.models.models import Stock
from app.services.screener_service import ScreenerService
from app.services.job_store import job_store
from app.schemas.schemas import ScreenerStockResult

router = APIRouter()

class ScreenerJobResponse(BaseModel):
    job_id: str

@router.post("/screener/submit", response_model=ScreenerJobResponse)
@limiter.limit("2/minute")
def submit_screener_job(
    _: str = Depends(get_current_api_key),
    db=Depends(get_db),
):
    """提交选股任务，返回 job_id"""
    job_id = f"screener_{int(time.time() * 1000)}"

    def run_job():
        service = ScreenerService()

        def progress_callback(stage: str, current: int, total: int, message: str):
            job_store.update(job_id, progress=current / total if total else 0,
                             payload={'stage': stage, 'current': current, 'total': total, 'message': message})

        # 加载股票列表
        stocks = db.query(Stock).all()

        # 阶段1: 并行扫描
        results = service.parallel_scan_stocks(stocks, offset=120,
                                                max_workers=10,
                                                progress_callback=progress_callback)

        # 阶段2: 过滤排序
        top5 = service.filter_and_rank(results, progress_callback=progress_callback)

        job_store.update(job_id, status='completed', progress=1.0,
                          result={'success': True, 'total_scanned': len(results),
                                  'results': top5, 'execution_time_s': 0})

    # 后台执行
    import threading
    threading.Thread(target=run_job, daemon=True).start()

    return ScreenerJobResponse(job_id=job_id)
```

- [ ] **Step 2: 添加 get_screener_job_status endpoint**

```python
@router.get("/screener/{job_id}")
def get_screener_job_status(
    job_id: str,
    _: str = Depends(get_current_api_key),
):
    """查询选股任务状态和结果"""
    job = job_store.get(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job
```

- [ ] **Step 3: 注册 router 到 main.py**

```python
# backend/main.py 新增
from app.api.screener_agent import router as screener_agent_router
# 在 include_router 部分添加
app.include_router(screener_agent_router, prefix="/api", tags=["screener_agent"])
```

- [ ] **Step 4: 测试 job 提交**

Run: `curl -X POST http://localhost:8808/api/screener/submit -H "X-API-Key: test"`

- [ ] **Step 5: 提交代码**

```bash
git add backend/app/api/screener_agent.py backend/main.py
git commit -m "feat: add screener agent API endpoints"
```

---

## Task 3: 前端 — Screener.tsx 重写

**Files:**
- Modify: `frontend/src/pages/Screener.tsx`
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: 更新 api.ts — 添加 submitScreener 和 getScreenerStatus**

```typescript
// frontend/src/services/api.ts 新增
export async function submitScreener(): Promise<{ job_id: string }> {
  const response = await api.post<{ job_id: string }>('/screener/submit')
  return response.data
}

export async function getScreenerStatus(jobId: string): Promise<{
  status: string
  progress: number
  payload?: { stage: string; current: number; total: number; message: string }
  result?: any
}> {
  const response = await api.get(`/screener/${jobId}`)
  return response.data
}
```

- [ ] **Step 2: 重写 Screener.tsx — 进度显示**

```typescript
// frontend/src/pages/Screener.tsx

import { useState, useEffect } from 'react'
import { Card, Button, Progress, Tag, message, Spin, Row, Col } from 'antd'
import { PlayCircleOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { submitScreener, getScreenerStatus } from '../services/api'

interface StockResult {
  stock_code: string
  stock_name: string
  close: number
  change_pct: number
  ma5: number
  ma10: number
  ma20: number
  rsi: number
  volume_ratio: number
  composite_score: number
  ai_signal?: string
  ai_confidence?: number
  ai_reason?: string
}

const STAGE_LABELS: Record<string, string> = {
  scanning: '📊 正在扫描全市场股票...',
  scoring: '🏆 正在综合评分排序...',
  ai_analysis: '🤖 AI 深度分析中',
  completed: '✅ 选股完成',
}

function Screener() {
  const [running, setRunning] = useState(false)
  const [stage, setStage] = useState('')
  const [progress, setProgress] = useState(0)
  const [current, setCurrent] = useState(0)
  const [total, setTotal] = useState(0)
  const [message_text, setMessageText] = useState('')
  const [results, setResults] = useState<StockResult[]>([])
  const [jobId, setJobId] = useState<string | null>(null)

  const handleRun = async () => {
    try {
      setRunning(true)
      setResults([])
      const res = await submitScreener()
      setJobId(res.job_id)
      await pollJob(res.job_id)
    } catch (e) {
      message.error('提交选股任务失败')
      setRunning(false)
    }
  }

  const pollJob = async (jobId: string) => {
    while (true) {
      const job = await getScreenerStatus(jobId)
      if (job.status === 'completed') {
        setStage('completed')
        setProgress(100)
        if (job.result?.results) {
          setResults(job.result.results)
        }
        setRunning(false)
        break
      }
      if (job.status === 'failed') {
        message.error('选股任务失败')
        setRunning(false)
        break
      }
      // 更新进度
      const p = job.payload
      if (p) {
        setStage(p.stage)
        setCurrent(p.current)
        setTotal(p.total)
        setMessageText(p.message || STAGE_LABELS[p.stage] || '')
        setProgress(Math.round((p.current / p.total) * 100))
      }
      await new Promise(r => setTimeout(r, 2000))
    }
  }

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">AI 量化选股</h1>
        <p className="page-subtitle">基于多维度筛选 + AI 深度分析，智能推荐 A 股</p>
      </div>

      {/* 开始选股按钮 */}
      {!running && results.length === 0 && (
        <Card style={{ textAlign: 'center', padding: '40px' }}>
          <Button
            type="primary"
            size="large"
            icon={<PlayCircleOutlined />}
            onClick={handleRun}
            style={{ borderRadius: 24, padding: '8px 48px', fontSize: 16 }}
          >
            开始 AI 选股
          </Button>
          <div style={{ marginTop: 16, color: 'var(--color-text-secondary)', fontSize: 13 }}>
            自动扫描全市场 5000+ 股票，综合评分排序后 AI 深度分析 TOP 5
          </div>
        </Card>
      )}

      {/* 进度显示 */}
      {running && (
        <Card style={{ padding: '32px' }}>
          <div style={{ marginBottom: 16, fontSize: 16, fontWeight: 600 }}>
            {STAGE_LABELS[stage] || '正在处理...'}
          </div>
          <Progress percent={progress} status="active" />
          <div style={{ marginTop: 8, color: 'var(--color-text-secondary)', fontSize: 13 }}>
            {message_text}
          </div>
          {total > 0 && (
            <div style={{ marginTop: 8, color: 'var(--color-text-tertiary)', fontSize: 12 }}>
              已处理 {current} / {total} 只股票
            </div>
          )}
        </Card>
      )}

      {/* 结果展示 */}
      {results.length > 0 && (
        <div>
          <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <CheckCircleOutlined style={{ color: 'var(--color-success)' }} />
            <span style={{ fontSize: 16, fontWeight: 600 }}>AI 精选 TOP 5</span>
          </div>
          <Row gutter={[0, 16]}>
            {results.map((stock, idx) => (
              <Col span={24} key={stock.stock_code}>
                <Card
                  style={{
                    borderLeft: `4px solid ${
                      stock.ai_signal === 'buy' ? '#52c41a' :
                      stock.ai_signal === 'sell' ? '#ff4d4f' : '#8c8c8c'
                    }`
                  }}
                >
                  <Row gutter={16} align="middle">
                    <Col span={4}>
                      <div style={{ fontSize: 18, fontWeight: 700 }}>{stock.stock_code}</div>
                      <div style={{ color: 'var(--color-text-secondary)' }}>{stock.stock_name}</div>
                    </Col>
                    <Col span={3}>
                      <div style={{ fontSize: 20, fontWeight: 700 }}>{stock.close.toFixed(2)}</div>
                      <div style={{
                        color: stock.change_pct >= 0 ? '#EB001B' : '#52C41A',
                        fontSize: 13
                      }}>
                        {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                      </div>
                    </Col>
                    <Col span={5}>
                      <Tag color={stock.ai_signal === 'buy' ? 'green' : stock.ai_signal === 'sell' ? 'red' : 'default'}>
                        {stock.ai_signal === 'buy' ? '买入' : stock.ai_signal === 'sell' ? '卖出' : '持有'}
                      </Tag>
                      {stock.ai_confidence && (
                        <span style={{ marginLeft: 8, color: 'var(--color-text-secondary)' }}>
                          置信度 {Math.round(stock.ai_confidence * 100)}%
                        </span>
                      )}
                    </Col>
                    <Col span={12}>
                      <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                        {stock.ai_reason || 'AI 分析中...'}
                      </div>
                    </Col>
                  </Row>
                </Card>
              </Col>
            ))}
          </Row>
          <Button style={{ marginTop: 16 }} onClick={() => setResults([])}>
            重新选股
          </Button>
        </div>
      )}
    </div>
  )
}

export default Screener
```

- [ ] **Step 3: 测试前端编译**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 4: 提交代码**

```bash
git add frontend/src/pages/Screener.tsx frontend/src/services/api.ts
git commit -m "feat: rewrite Screener page as AI stock screener"
```

---

## Task 4: AI Agent 深度分析接入

**Files:**
- Modify: `backend/app/services/screener_service.py`（添加 analyze_top5 方法）
- Modify: `backend/app/api/screener_agent.py`（在 job 中调用 AI）

- [ ] **Step 1: 分析 TOP 5 — 调用 AI Agent**

在 `run_job` 函数中，TOP 5 排序完成后，对每只股票调用 AI Agent：

```python
# 在 screener_agent.py 的 run_job 中，filter_and_rank 后添加

from app.agent.orchestrator import AgentOrchestrator

def run_job():
    service = ScreenerService()
    # ... 扫描和排序 ...

    # 阶段3: AI 深度分析 TOP 5
    orchestrator = AgentOrchestrator(mode='full')
    for i, stock in enumerate(top5):
        if progress_callback:
            progress_callback('ai_analysis', i + 1, 5,
                              f'🤖 AI 深度分析中 ({i+1}/5): {stock["stock_name"]}')

        result = orchestrator.run(
            stock_code=stock['stock_code'],
            stock_name=stock['stock_name'],
            progress_callback=None
        )
        stock['ai_signal'] = result.final_signal
        stock['ai_confidence'] = result.final_confidence
        stock['ai_reason'] = result.final_reason
```

- [ ] **Step 2: 测试 AI 分析（单只股票）**

Run: `cd backend && python -c "
from app.agent.orchestrator import AgentOrchestrator
o = AgentOrchestrator('full')
r = o.run('000001', '平安银行')
print(f'signal: {r.final_signal}, confidence: {r.final_confidence}, reason: {r.final_reason[:100]}')
"`

- [ ] **Step 3: 提交代码**

```bash
git add backend/app/services/screener_service.py backend/app/api/screener_agent.py
git commit -m "feat: integrate AI agent for TOP 5 deep analysis in screener"
```

---

## 验证清单

- [ ] 后端 API `/api/screener/submit` 能提交任务
- [ ] 后端 API `/api/screener/{job_id}` 能返回进度和结果
- [ ] 前端点击"开始选股"能显示进度（扫描 N/M → 评分 → AI分析）
- [ ] 完成后显示 5 个股票卡片，每个含信号 + 置信度 + AI 理由
- [ ] AI 多阶段分析输出正确的信号和理由