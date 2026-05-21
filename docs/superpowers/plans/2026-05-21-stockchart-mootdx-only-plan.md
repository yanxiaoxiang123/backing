# StockChart 改为纯 mootdx 数据源

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** StockChart 页面进入时直接调用 mootdx 获取日K数据并显示，无需DB读取，无需轮询。

**Architecture:** 移除 10 秒轮询 + DB 读取逻辑，改为进入时一次性调用 `/api/realtime/{code}` 获取数据。

**Tech Stack:** mootdx, FastAPI, React

---

## Task 1: 简化 StockChart.tsx — 移除轮询，改为纯 mootdx

**Files:**
- Modify: `frontend/src/pages/StockChart.tsx`

### 1.1 更新 import

```typescript
// 改前
import { getStockIndicators, getStock, getRealtimeBars } from '../services/api'

// 改后（移除 getStockIndicators）
import { getStock, getRealtimeBars } from '../services/api'
```

### 1.2 重构 loadData — 用 mootdx 数据

```typescript
const loadData = async () => {
  if (!code) return

  setLoading(true)
  try {
    const stockInfo = await getStock(code)
    setStockName(stockInfo.name)

    // 直接用 mootdx 实时数据
    const res = await getRealtimeBars(code)

    // 将 RealtimeBar 格式转换为 KlineIndicator 格式（只填必要字段）
    const klineData: KlineIndicator[] = (res.data ?? []).map(bar => ({
      date: bar.date,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
      amount: bar.amount,
      // 技术指标暂无（mootdx 不提供），设为 null
      ma5: null,
      ma10: null,
      ma20: null,
      ma60: null,
      ma120: null,
      dif: null,
      dea: null,
      macd: null,
      kdj_k: null,
      kdj_d: null,
      kdj_j: null,
      rsi6: null,
      rsi12: null,
      rsi24: null,
    }))

    setKlineData(klineData)
  } catch (error) {
    message.error('加载K线数据失败')
  } finally {
    setLoading(false)
  }
}
```

### 1.3 移除 10 秒轮询 useEffect

删除之前添加的 realtime polling useEffect（搜索 "pollRealtime" 找到它并删除整个 useEffect）。

### 1.4 更新 getChartOption

由于 MA/MACD/KDJ 等指标为 null，图表中的均线/MACD/KDJ 子图会显示为空或报错。需要修改 `getChartOption` 让这些子图在数据为空时正常渲染。

在 `series` 数组中过滤掉指标为 null 的 series，或者直接注释/移除均线/MACD/KDJ 的 series 配置（保留 K 线 + 成交量即可）。

简化后的 series：

```typescript
series: [
  {
    name: 'K线',
    type: 'candlestick',
    data: ohlc,
    itemStyle: {
      color: '#EB001B',
      color0: '#F79E1B',
      borderColor: '#EB001B',
      borderColor0: '#F79E1B'
    }
  },
  {
    name: '成交量',
    type: 'bar',
    xAxisIndex: 1,
    yAxisIndex: 1,
    data: volumes
  }
]
```

同时移除 legend 中的均线数据，以及 grid/xAxis/yAxis 中不需要的 index（只保留 K 线和成交量两个 grid）。

### 1.5 保留周期选择但只对日K生效

周K/月K选择器保留，但点击时提示"周K/月K需从数据库读取，请先同步数据"。或者暂时禁用周K/月K选项（只留日K）。

---

**验证：**

```bash
cd frontend && npm run dev
# 打开 K 线页，观察：
# 1. 进入页面立即显示数据（无需等待加载 DB）
# 2. 无 10 秒轮询请求
# 3. 只有 /api/realtime/{code} 请求，无 /api/stocks/{code}/indicators
```

Commit message: `refactor(frontend): StockChart uses mootdx directly, no polling`

---

## Task 2: 更新 KlineIndicator 类型（amount 字段）

**Files:**
- Modify: `frontend/src/types/index.ts`（找到 KlineIndicator 类型定义）

如果 `KlineIndicator` 类型中没有 `amount` 字段，添加它：

```typescript
interface KlineIndicator {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount?: number  // 新增
  ma5: number | null
  ma10: number | null
  // ... 其他字段
}
```

Commit message: `feat(frontend): add amount field to KlineIndicator type`