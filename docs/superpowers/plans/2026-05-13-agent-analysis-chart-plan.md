# AI 分析结果页技术图表实现计划

> **For agentic workers:** Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI 分析结果顶部展示轻量级 K 线图（K 线 + MA5/MA10/MA20），让用户先看图再读 AI 结论。

**Architecture:** 在 AgentAnalysis.tsx 结果区顶部添加 ReactECharts 图表，数据来自 getStockIndicators API，180天日K，复用 StockChart.tsx 的图表逻辑但简化。

**Tech Stack:** React + TypeScript + echarts-for-react + Ant Design

---

## File Map

| File | Role |
|------|------|
| `frontend/src/pages/AgentAnalysis.tsx` | 添加图表卡片 + getLightChartOption + 数据获取 |
| `frontend/src/types/index.ts` | 已更新（thinking 字段，已完成） |

---

## Task 1: 添加图表状态和 getLightChartOption 函数

**Files:**
- Modify: `frontend/src/pages/AgentAnalysis.tsx`

- [ ] **Step 1: 添加状态和导入**

在 `AgentAnalysis.tsx` 顶部添加 `ReactECharts` 和 `EChartsOption` 导入：

```typescript
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
```

在组件状态区添加（位于 `jobStages` 下方）：

```typescript
const [stockIndicators, setStockIndicators] = useState<KlineIndicator[]>([])
```

- [ ] **Step 2: 添加 getLightChartOption 函数**

在组件内部（`copyToClipboard` 函数下方）添加：

```typescript
const getLightChartOption = (data: KlineIndicator[]): EChartsOption => {
  if (!data || data.length === 0) return {}

  const dates = data.map(d => d.date)
  const ohlc = data.map(d => [d.open, d.close, d.low, d.high])
  const ma5 = data.map(d => d.ma5)
  const ma10 = data.map(d => d.ma10)
  const ma20 = data.map(d => d.ma20)

  return {
    backgroundColor: '#fff',
    animation: false,
    legend: {
      top: 10,
      left: 'center',
      textStyle: { color: 'var(--color-text-secondary)', fontSize: 11 },
      data: ['K线', 'MA5', 'MA10', 'MA20']
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#fff',
      borderColor: 'var(--color-border)',
      textStyle: { color: 'var(--color-text-primary)' },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const date = params[0].axisValue
        const kline = params.find((p: any) => p.seriesName === 'K线')
        if (!kline) return ''
        const [o, c, l, h] = kline.data as number[]
        const color = c >= o ? '#ff3b30' : '#34c759'
        return `<div style="font-weight:600;margin-bottom:4px">${date}</div>
          <div>开: <b>${o.toFixed(2)}</b> 收: <b style="color:${color}">${c.toFixed(2)}</b></div>
          <div>高: <b>${h.toFixed(2)}</b> 低: <b>${l.toFixed(2)}</b></div>`
      }
    },
    grid: { left: '10%', right: '8%', top: 50, bottom: 60 },
    xAxis: [{
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { onZero: false },
      axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
    }],
    yAxis: [{
      scale: true,
      axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 10 },
    }],
    dataZoom: [
      { type: 'inside', start: 70, end: 100 },
      { show: true, type: 'slider', bottom: 10, start: 70, end: 100, height: 20 }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#ff3b30',
          color0: '#34c759',
          borderColor: '#ff3b30',
          borderColor0: '#34c759'
        }
      },
      { name: 'MA5', type: 'line', data: ma5, smooth: true, lineStyle: { opacity: 0.5 } },
      { name: 'MA10', type: 'line', data: ma10, smooth: true, lineStyle: { opacity: 0.5 } },
      { name: 'MA20', type: 'line', data: ma20, smooth: true, lineStyle: { opacity: 0.5 } },
    ]
  }
}
```

- [ ] **Step 3: 验证语法**

```bash
cd /Users/yan/Desktop/backing/frontend && npm run build 2>&1 | grep -E "error|Error" | head -20
```

预期：无新增错误（可能有之前遗留的 unused variable 警告可忽略）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/AgentAnalysis.tsx && git commit -m "feat(frontend): add getLightChartOption for agent analysis"
```

---

## Task 2: 分析完成后获取 K 线数据

**Files:**
- Modify: `frontend/src/pages/AgentAnalysis.tsx:79-80`

- [ ] **Step 1: 在 handleAnalyze 中添加数据获取**

在 `waitForJob` 返回后、`setResult(data)` 之前添加 K 线数据获取：

```typescript
setResult(data)

// 获取 K 线数据用于图表
if (data.success && selectedStock) {
  try {
    const endDate = new Date().toISOString().split('T')[0]
    const startDate = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    const indicatorsRes = await getStockIndicators(selectedStock, 'daily', startDate, endDate)
    setStockIndicators(indicatorsRes.data)
  } catch (err) {
    logger.error('Failed to load stock indicators for chart:', err)
  }
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/pages/AgentAnalysis.tsx && git commit -m "feat(frontend): fetch K-line data after analysis completes"
```

---

## Task 3: 在结果区顶部插入图表卡片

**Files:**
- Modify: `frontend/src/pages/AgentAnalysis.tsx:431-475`

- [ ] **Step 1: 在决策卡片前插入图表卡片**

找到 `result &&` 块内的第一张 Card（决策卡片），在其前面添加图表 Card：

```tsx
{result && (
  <div className="fade-in">
    {/* K线图表 - 轻量版 */}
    {stockIndicators.length > 0 && (
      <Card
        style={{ marginBottom: 16 }}
        title={
          <span>
            {result.stock_name} ({result.stock_code}) 近期走势
          </span>
        }
        extra={
          <a
            href={`/stocks/${result.stock_code}`}
            target="_blank"
            rel="noreferrer"
            style={{ color: 'var(--color-accent)' }}
          >
            查看完整图表 →
          </a>
        }
      >
        <ReactECharts
          option={getLightChartOption(stockIndicators)}
          style={{ height: 300 }}
          opts={{ renderer: 'canvas' }}
        />
      </Card>
    )}

    {/* 决策卡片 */}
    <Card style={{ marginBottom: 16 }}>
```

- [ ] **Step 2: 验证构建**

```bash
cd /Users/yan/Desktop/backing/frontend && npm run build 2>&1 | tail -15
```

预期：构建成功，无 TypeScript 错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/AgentAnalysis.tsx && git commit -m "feat(frontend): display light K-line chart above analysis results"
```

---

## Task 4: 端到端验证

- [ ] **Step 1: 启动前后端**

```bash
# 后端
cd /Users/yan/Desktop/backing/backend && python main.py &
# 前端
cd /Users/yan/Desktop/backing/frontend && npm run dev &
```

- [ ] **Step 2: 手动测试**

1. 打开 http://localhost:5173 进入 AI Agent 分析页面
2. 选择一只股票（如 000001）
3. 选择 standard 模式，点击"开始分析"
4. 等待分析完成，观察结果区顶部是否显示 K 线图
5. 确认图表包含 K 线 + MA5 + MA10 + MA20
6. 确认"查看完整图表 →"链接可跳转

---

## 验证清单

- [ ] `getLightChartOption` 函数存在且返回有效 EChartsOption
- [ ] 分析完成后 `stockIndicators` 状态被填充
- [ ] 图表卡片显示在决策卡片上方
- [ ] 图表包含 K 线 + MA5 + MA10 + MA20
- [ ] "查看完整图表 →"链接正确指向 `/stocks/{code}`