# 全量实时数据 mootdx 统一方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 所有页面的实时价格/指数数据全部改为 mootdx 获取，数据库仅用于股票元数据（名称/代码/上市日期）。

**Architecture:** 新增 `get_realtime_quotes()` 方法批量获取多只股票最新价；新增 `get_index_realtime()` 获取主要指数；前端 Dashboard/Watchlist/StockList 全部改为调用新 API。

**Tech Stack:** Python (mootdx), FastAPI, React

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/app/services/realtime_service.py` | 新增 `get_realtime_quotes()` 和 `get_index_realtime()` |
| `backend/app/api/realtime.py` | 新增 `GET /api/realtime/quotes` 和 `GET /api/realtime/indices` |
| `frontend/src/services/api.ts` | 新增 `getRealtimeQuotes()` 和 `getRealtimeIndices()` |
| `frontend/src/pages/Dashboard.tsx` | 改用 mootdx 获取实时价格和指数 |
| `frontend/src/pages/Watchlist.tsx` | 改用 mootdx 获取自选股实时价格 |
| `frontend/src/pages/StockList.tsx` | 改用 mootdx 实时价格替代 DB 数据 |

---

## Task 1: RealtimeService 新增 quotes 和 indices 方法

**Files:**
- Modify: `backend/app/services/realtime_service.py`

**新增方法：**

在 `RealtimeService` 类中添加两个方法：

```python
def get_realtime_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
    """批量获取多只股票最新行情

    Args:
        symbols: 股票代码列表，如 ["600036", "000001"]

    Returns:
        每只股票的 {symbol, last_close, open, high, low, close, volume, change, change_percent}
    """
    client = self.get_client()
    results = []
    for symbol in symbols:
        try:
            # offset=2 拿最近2条（第1条是今天，第2条是昨天）
            df = client.bars(symbol=symbol, frequency=9, offset=2)
            if df is None or len(df) < 2:
                continue
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            close = float(today.get('close', 0))
            prev_close = float(yesterday.get('close', close))
            change = close - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0
            results.append({
                'symbol': symbol,
                'open': float(today.get('open', 0)),
                'high': float(today.get('high', 0)),
                'low': float(today.get('low', 0)),
                'close': close,
                'volume': float(today.get('vol', 0)),
                'amount': float(today.get('amount', 0)),
                'change': change,
                'change_percent': change_percent,
                'prev_close': prev_close,
            })
        except Exception as e:
            logger.error(f"get_realtime_quotes error for {symbol}: {e}")
            continue
    return results

def get_index_realtime(self) -> List[Dict[str, Any]]:
    """获取主要指数实时数据（上证/深证/沪深300/创业板/科创50）

    Returns:
        每只指数的 {symbol, name, close, change, change_percent}
    """
    client = self.get_client()
    index_codes = ['000001', '399001', '000300', '399006', '000688']
    index_names = {'000001': '上证指数', '399001': '深证成指', '000300': '沪深300',
                   '399006': '创业板指', '000688': '科创50'}
    results = []
    for code in index_codes:
        try:
            df = client.index(symbol=code, frequency=9, offset=2)
            if df is None or len(df) < 2:
                continue
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            close = float(today.get('close', 0))
            prev_close = float(yesterday.get('close', close))
            change = close - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0
            results.append({
                'symbol': code,
                'name': index_names.get(code, code),
                'close': close,
                'change': change,
                'change_percent': change_percent,
                'prev_close': prev_close,
            })
        except Exception as e:
            logger.error(f"get_index_realtime error for {code}: {e}")
            continue
    return results
```

**验证：**
```bash
cd e:/Y/Y2/backing_test/backing/backend && D:/anaconda3/envs/backing/python.exe -c "
from app.services.realtime_service import realtime_service
quotes = realtime_service.get_realtime_quotes(['600036', '000001'])
print(f'quotes: {len(quotes)} stocks')
for q in quotes:
    print(f'  {q[\"symbol\"]}: close={q[\"close\"]}, change={q[\"change_percent\"]:.2f}%')
indices = realtime_service.get_index_realtime()
print(f'indices: {len(indices)}')
for i in indices:
    print(f'  {i[\"name\"]}: {i[\"close\"]}')
"
```

Commit message: `feat(backend): add get_realtime_quotes and get_index_realtime`

---

## Task 2: 新增 API 路由

**Files:**
- Modify: `backend/app/api/realtime.py`

**新增 import：**

```python
from typing import List
from fastapi import Query
```

**新增 schema（在 RealtimeBarsResponse 之后）：**

```python
class RealtimeQuote(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    change: float
    change_percent: float
    prev_close: float


class RealtimeIndex(BaseModel):
    symbol: str
    name: str
    close: float
    change: float
    change_percent: float
    prev_close: float


class RealtimeQuotesResponse(BaseModel):
    success: bool
    data: List[RealtimeQuote]


class RealtimeIndicesResponse(BaseModel):
    success: bool
    data: List[RealtimeIndex]
```

**新增路由（添加在现有路由之后）：**

```python
@router.get('/realtime/quotes', response_model=RealtimeQuotesResponse)
def get_realtime_quotes(
    codes: str = Query(..., description="股票代码，逗号分隔，如 600036,000001"),
    _: str = Query(None, alias='api_key'),
):
    """批量获取股票实时行情（最新价格/涨跌幅）"""
    symbol_list = [s.strip() for s in codes.split(',') if s.strip()]
    data = realtime_service.get_realtime_quotes(symbol_list)
    return RealtimeQuotesResponse(success=True, data=[RealtimeQuote(**item) for item in data])


@router.get('/realtime/indices', response_model=RealtimeIndicesResponse)
def get_realtime_indices(
    _: str = Query(None, alias='api_key'),
):
    """获取主要指数实时行情"""
    data = realtime_service.get_index_realtime()
    return RealtimeIndicesResponse(success=True, data=[RealtimeIndex(**item) for item in data])
```

**验证：**
```bash
curl "http://localhost:8808/api/realtime/quotes?codes=600036,000001&api_key=yourkey"
curl "http://localhost:8808/api/realtime/indices?api_key=yourkey"
```

Commit message: `feat(api): add /api/realtime/quotes and /api/realtime/indices`

---

## Task 3: 前端 API 函数

**Files:**
- Modify: `frontend/src/services/api.ts`

**新增函数（添加在 getRealtimeBars 之后）：**

```typescript
export async function getRealtimeQuotes(codes: string[]): Promise<{
  success: boolean
  data: Array<{
    symbol: string
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount: number
    change: number
    change_percent: number
    prev_close: number
  }>
}> {
  const response = await api.get<any>(`/realtime/quotes?codes=${codes.join(',')}`)
  return response.data
}

export async function getRealtimeIndices(): Promise<{
  success: boolean
  data: Array<{
    symbol: string
    name: string
    close: number
    change: number
    change_percent: number
    prev_close: number
  }>
}> {
  const response = await api.get<any>('/realtime/indices')
  return response.data
}
```

**验证：**
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -10
```

Commit message: `feat(frontend): add getRealtimeQuotes and getRealtimeIndices API`

---

## Task 4: Dashboard 改用 mootdx

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

### 4.1 更新 import

```typescript
// 改前
import { getDashboardSummary, getStockKline, getRealtimeBars } from '../services/api'

// 改后
import { getRealtimeQuotes, getRealtimeIndices } from '../services/api'
```

### 4.2 重构 loadData（替换整个 loadData 函数）

```typescript
const loadData = useCallback(async () => {
  try {
    setLoading(true)
    const [quotes, indices] = await Promise.all([
      getRealtimeQuotes(watchlistCodes),
      getRealtimeIndices(),
    ])

    // 构建 watchlist 数据
    const watchlistData = quotes.data.map((q) => ({
      id: 0,
      code: q.symbol,
      name: '',  // 暂时留空，后面用 watchlist 里的名称填充
      current_price: q.close,
      high: q.high,
      low: q.low,
      volume: q.volume,
      change: q.change,
      change_percent: q.change_percent,
    }))

    // 指数数据
    const indicesData = indices.data.map((idx) => ({
      code: idx.symbol,
      name: idx.name,
      value: idx.close,
      change: idx.change,
      change_percent: idx.change_percent,
    }))

    // 构建 market_stats
    const up = watchlistData.filter(s => s.change_percent > 0).length
    const down = watchlistData.filter(s => s.change_percent < 0).length
    const flat = watchlistData.length - up - down

    setSummary({
      watchlist: watchlistData,
      indices: indicesData,
      market_stats: { up, down, flat, total: watchlistData.length },
      trend: { name: watchlistData[0]?.name || '', dates: [], values: [] },
    })
  } catch (error) {
    logger.error('Failed to load dashboard data:', error)
  } finally {
    setLoading(false)
  }
}, [watchlistCodes])
```

### 4.3 移除 10 秒轮询 useEffect

删除之前添加的 `pollRealtime` 实时轮询 useEffect（搜索 `pollRealtime` 找到它并删除）。

### 4.4 保留原有结构，替换数据来源

Dashboard 页面仍然使用原有的 UI 组件（IndexCard、WatchlistTable 等），数据结构保持兼容：
- `indices` → 来自 `getRealtimeIndices()`
- `watchlist` → 来自 `getRealtimeQuotes()`
- `market_stats` → 从 watchlist 计算

**注意：** watchlist 股票名称暂时为空字符串，Dashboard 表格显示时名称列会留空。如需显示名称，需要额外获取股票名称（可以新建 API `/api/stocks/names?codes=...` 获取名称映射）。

### 4.5 验证

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -10
```

Commit message: `feat(frontend): Dashboard uses mootdx for realtime quotes and indices`

---

## Task 5: Watchlist 改用 mootdx

**Files:**
- Modify: `frontend/src/pages/Watchlist.tsx`

### 5.1 更新 import

```typescript
// 改前
import { getWatchlist, addToWatchlist, removeFromWatchlist, getWatchlistCodes, syncKline, getDashboardSummary } from '../services/api'

// 改后
import { getWatchlist, addToWatchlist, removeFromWatchlist, getWatchlistCodes, getRealtimeQuotes } from '../services/api'
```

### 5.2 重构 loadWatchlistWithPrices

```typescript
const loadWatchlistWithPrices = async () => {
  try {
    setLoading(true)
    const watchlistData = await getWatchlist()
    setWatchlist(watchlistData.items)

    const codes = watchlistData.items.map((item: WatchlistItem) => item.stock_code)
    if (codes.length === 0) {
      setLoading(false)
      return
    }

    const quotes = await getRealtimeQuotes(codes)
    const priceMap: Record<string, any> = {}
    for (const q of quotes.data) {
      priceMap[q.symbol] = {
        current_price: q.close,
        change: q.change,
        change_percent: q.change_percent,
      }
    }
    setStockPriceMap(priceMap)
  } catch (error) {
    message.error('加载自选股失败')
  } finally {
    setLoading(false)
  }
}
```

### 5.3 验证

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -10
```

Commit message: `feat(frontend): Watchlist uses mootdx for realtime prices`

---

## Task 6: StockList 改用 mootdx

**Files:**
- Modify: `frontend/src/pages/StockList.tsx`

StockList 页面点击"K线"跳转到 StockChart，K线数据来自 mootdx（已实现）。价格显示在 StockChart 里，不需要在 StockList 显示。

StockList 的主要功能是股票列表管理和数据同步，这部分保持不变。

**验证：**
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -10
```

Commit message: `refactor(frontend): StockList ready for mootdx integration`

---

## 自检清单

1. `curl "http://localhost:8808/api/realtime/quotes?codes=600036,000001&api_key=yourkey"` 返回批量股票价格
2. `curl "http://localhost:8808/api/realtime/indices?api_key=yourkey"` 返回指数数据
3. Dashboard 页面显示实时价格和指数
4. Watchlist 页面显示自选股实时价格
5. StockChart 页面正常显示 K 线