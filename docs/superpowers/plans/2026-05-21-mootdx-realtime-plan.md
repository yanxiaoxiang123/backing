# mootdx 实时行情集成实现方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 backing 项目添加 mootdx 实时日 K 数据，每 10 秒刷新一次，供 Dashboard 和 StockChart 使用。

**Architecture:** 新增 `RealtimeService` 封装 mootdx_QUOTES，暴露 `bars()` 接口；新增 `GET /api/realtime/{code}` 路由；前端轮询调用替换数据库数据。

**Tech Stack:** Python (mootdx), FastAPI (后端), React (前端轮询)

---

## Task 1: 添加 mootdx 依赖

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 添加 mootdx 到 requirements.txt**

```txt
mootdx>=1.0.0
```

Run: `pip install -U 'mootdx[all]' -r backend/requirements.txt`

- [ ] **Step 2: Commit**

```bash
cd e:/Y/Y2/backing_test/backing
git add backend/requirements.txt
git commit -m "deps: add mootdx for realtime quotes"
```

---

## Task 2: 新建 RealtimeService

**Files:**
- Create: `backend/app/services/realtime_service.py`

- [ ] **Step 1: 编写 realtime_service.py**

```python
import logging
from typing import Optional, List, Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


class RealtimeService:
    """mootdx 实时行情服务"""
    
    _client: Optional[Any] = None

    @classmethod
    def get_client(cls):
        """获取或创建 mootdx Quotes 客户端（单例）"""
        if cls._client is None:
            from mootdx.quotes import Quotes
            cls._client = Quotes.factory(
                market='std',
                multithread=True,
                heartbeat=True,
            )
        return cls._client

    def bars(self, symbol: str, offset: int = 10) -> pd.DataFrame:
        """获取实时日K数据

        Args:
            symbol: 股票代码，如 "600036"（不带市场前缀）
            offset: 返回最近 N 条，默认 10 条

        Returns:
            DataFrame，列名: date, open, high, low, close, volume, amount, symbol
        """
        client = self.get_client()
        try:
            # frequency=9 表示日K线
            df = client.bars(symbol=symbol, frequency=9, offset=offset)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"mootdx bars error for {symbol}: {e}")
            return pd.DataFrame()

    def normalise_bars(self, symbol: str, offset: int = 10) -> List[Dict[str, Any]]:
        """将 bars 数据规范化为 dict 列表"""
        df = self.bars(symbol=symbol, offset=offset)
        if df.empty:
            return []

        # mootdx 列名可能是 date/datetime/open/high/low/close/vol/volume
        date_col = 'date' if 'date' in df.columns else 'datetime'
        if date_col not in df.columns:
            return []

        records = []
        for _, row in df.iterrows():
            records.append({
                'date': str(row.get(date_col, '')),
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'volume': float(row.get('vol', 0)),
                'amount': float(row.get('volume', 0)),
                'symbol': symbol,
            })
        return records


# Singleton instance
realtime_service = RealtimeService()
```

- [ ] **Step 2: Commit**

```bash
cd e:/Y/Y2/backing_test/backing
git add backend/app/services/realtime_service.py
git commit -m "feat(backend): add RealtimeService with mootdx bars()"
```

---

## Task 3: 新建 realtime API 路由

**Files:**
- Create: `backend/app/api/realtime.py`

- [ ] **Step 1: 编写 realtime.py 路由**

```python
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from app.services.realtime_service import realtime_service
from app.auth import get_current_api_key

router = APIRouter()


class RealtimeBar(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    symbol: str


class RealtimeBarsResponse(BaseModel):
    success: bool
    code: str
    data: List[RealtimeBar]


@router.get('/realtime/{code}', response_model=RealtimeBarsResponse)
def get_realtime_bars(
    code: str,
    _: str = Query(None, description="API key", alias='api_key'),
):
    """获取股票实时日K数据（最近10条）"""
    # 去掉市场前缀 (sh.600036 -> 600036)
    symbol = code.split('.')[-1] if '.' in code else code

    data = realtime_service.normalise_bars(symbol=symbol, offset=10)

    return RealtimeBarsResponse(
        success=True,
        code=code,
        data=[RealtimeBar(**item) for item in data],
    )
```

- [ ] **Step 2: 在 main.py 中注册路由**

Modify `backend/main.py`，在 `app.include_router(router, prefix="/api", tags=["api"])` **之前**添加：

```python
from app.api.realtime import router as realtime_router
```

并在 routers 部分添加：

```python
app.include_router(realtime_router, prefix="/api", tags=["realtime"])
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/realtime.py backend/main.py
git commit -m "feat(api): add /api/realtime/{code} endpoint via mootdx"
```

---

## Task 4: 环境配置

**Files:**
- Modify: `backend/.env`

- [ ] **Step 1: 添加 REALTIME_PROVIDER 到 .env**

在 `.env` 文件末尾添加：

```env
REALTIME_PROVIDER=mootdx
```

- [ ] **Step 2: Commit**

```bash
git add backend/.env
git commit -m "config: add REALTIME_PROVIDER=mootdx"
```

---

## Task 5: 前端 API 调用

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: 在 api.ts 中添加实时 API 调用**

找到 api.ts 中现有的函数，在末尾添加：

```typescript
export async function getRealtimeBars(code: string): Promise<{
  success: boolean
  code: string
  data: Array<{
    date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount: number
    symbol: string
  }>
}> {
  const response = await fetch(`${API_BASE_URL}/api/realtime/${code}`, {
    headers: { 'X-API-Key': API_KEY },
  })
  if (!response.ok) throw new Error('Failed to fetch realtime bars')
  return response.json()
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(frontend): add getRealtimeBars API function"
```

---

## Task 6: Dashboard 实时轮询

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: 添加 useEffect 轮询实时数据**

在 Dashboard.tsx 中：
1. 导入 `getRealtimeBars`
2. 在 `useEffect` 中，每 10 秒调用 `getRealtimeBars`，用返回值更新 watchlist 数据的 `current_price` / `change` / `change_percent`

关键逻辑：
- 实时数据的最后一条（最新收盘价）替换 watchlist 中对应股票的当前价
- 涨跌幅通过 `最新价 / 昨收 - 1` 计算
- 若 API 调用失败，捕获异常，不更新数据（保留上一次值）

```typescript
useEffect(() => {
  const pollRealtime = async () => {
    if (watchlist.length === 0) return
    try {
      // 并行请求所有自选股的实时数据
      const results = await Promise.all(
        watchlist.map(item => getRealtimeBars(item.code))
      )
      setWatchlist(prev => prev.map((stock, idx) => {
        const bars = results[idx]?.data ?? []
        if (bars.length === 0) return stock
        const latest = bars[bars.length - 1]  // 最新一根K线
        const prev = bars[bars.length - 2]     // 前一根K线（昨收）
        const currentPrice = latest.close
        const prevClose = prev?.close ?? latest.close
        const change = currentPrice - prevClose
        const changePercent = prevClose ? (change / prevClose) * 100 : 0
        return {
          ...stock,
          current_price: currentPrice,
          change,
          change_percent: changePercent,
        }
      }))
    } catch (e) {
      console.warn('Realtime poll failed:', e)
    }
  }

  pollRealtime()
  const interval = setInterval(pollRealtime, 10_000)
  return () => clearInterval(interval)
}, [watchlist.length])
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat(frontend): poll realtime bars every 10s on Dashboard"
```

---

## Task 7: StockChart 实时轮询

**Files:**
- Modify: `frontend/src/pages/StockChart.tsx`

- [ ] **Step 1: 添加实时K线轮询**

在 StockChart.tsx 中，K 线图加载后，每 10 秒调用 `getRealtimeBars` 获取最新日K，追加到本地 data 列表（若日期已存在则替换）。

关键逻辑：
- 用 `date` 字段去重，新数据与现有数据合并后按日期排序
- 最多保留最近 120 条

```typescript
useEffect(() => {
  if (!stockCode) return

  const pollRealtime = async () => {
    try {
      const res = await getRealtimeBars(stockCode)
      if (!res.data?.length) return
      setKlineData(prev => {
        const merged = [...prev]
        for (const bar of res.data) {
          const idx = merged.findIndex(b => b.date === bar.date)
          if (idx >= 0) {
            merged[idx] = bar
          } else {
            merged.push(bar)
          }
        }
        return merged
          .sort((a, b) => a.date.localeCompare(b.date))
          .slice(-120)
      })
    } catch (e) {
      console.warn('StockChart realtime poll failed:', e)
    }
  }

  pollRealtime()
  const interval = setInterval(pollRealtime, 10_000)
  return () => clearInterval(interval)
}, [stockCode])
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/StockChart.tsx
git commit -m "feat(frontend): poll realtime K-line every 10s on StockChart"
```

---

## 自检清单

完成所有 Task 后，确认以下内容：

1. `pip install 'mootdx[all]'` 成功
2. `python -c "from mootdx.quotes import Quotes; Quotes.factory(market='std')"` 成功
3. `curl http://localhost:8808/api/realtime/600036 -H "X-API-Key: yourkey"` 返回 JSON
4. 前端 Dashboard 打开后 10 秒内价格有变化
5. 前端 StockChart 打开后 10 秒内 K 线图有更新