# StockChart 实时数据写入数据库实现方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 进入 StockChart 页面时，先用 mootdx 实时数据写入数据库，再从 DB 读取；每 10 秒轮询同样写入 DB 并返回带指标的 K 线数据。

**Architecture:** `RealtimeService` 新增 `save_to_db()` 方法做 upsert；新增 `POST /api/realtime/{code}/save` 接口；前端重构 `loadData()` 先 save 再读，10 秒轮询改用同一接口，按周期控制加载范围。

**Tech Stack:** Python (SQLAlchemy ORM, mootdx), FastAPI, React

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/app/services/realtime_service.py` | 新增 `save_to_db()` upsert 方法 |
| `backend/app/api/realtime.py` | 新增 `POST /api/realtime/{code}/save` 接口 |
| `frontend/src/pages/StockChart.tsx` | 重构 loadData + 10秒轮询改用 save 接口 |

---

## Task 1: RealtimeService.save_to_db()

**Files:**
- Modify: `backend/app/services/realtime_service.py`

**新增方法：**

在 `RealtimeService` 类中添加：

```python
def save_to_db(self, symbol: str, db_session, offset: int = 10) -> List[Dict[str, Any]]:
    """将 mootdx bars 数据 upsert 到 DailyKline 表

    Args:
        symbol: 股票代码（不带市场前缀，如 "600036"）
        db_session: SQLAlchemy session
        offset: 获取最近 N 条数据，默认 10 条

    Returns:
        已写入的 bars 数据列表（dict 格式）
    """
    from app.models.models import DailyKline
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    bars = self.normalise_bars(symbol=symbol, offset=offset)
    if not bars:
        return []

    written = []
    for bar in bars:
        parsed_date = datetime.strptime(bar['date'], '%Y-%m-%d').date()

        # 使用 INSERT OR REPLACE (upsert)
        stmt = sqlite_insert(DailyKline).values(
            stock_code=symbol,
            date=parsed_date,
            open=bar['open'],
            high=bar['high'],
            low=bar['low'],
            close=bar['close'],
            volume=bar['volume'],
            amount=bar.get('amount', 0),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=['stock_code', 'date'],
            set_={
                'open': stmt.excluded.open,
                'high': stmt.excluded.high,
                'low': stmt.excluded.low,
                'close': stmt.excluded.close,
                'volume': stmt.excluded.volume,
                'amount': stmt.excluded.amount,
            }
        )
        db_session.execute(stmt)
        written.append(bar)

    db_session.commit()
    return written
```

**注意：** 需要在文件顶部添加 `from datetime import datetime`。

**验证：**
```
cd e:/Y/Y2/backing_test/backing/backend && D:/anaconda3/envs/backing/python.exe -c "
from app.services.realtime_service import realtime_service
from app.config import SessionLocal
db = SessionLocal()
result = realtime_service.save_to_db('000001', db, offset=3)
print(f'Saved {len(result)} bars')
db.commit()
db.close()
"
```

Commit message: `feat(backend): add RealtimeService.save_to_db() upsert method`

---

## Task 2: POST /api/realtime/{code}/save 接口

**Files:**
- Modify: `backend/app/api/realtime.py`

**新增 import：**

```python
from datetime import date
from sqlalchemy.orm import Session
from app.config import SessionLocal
from app.services.indicator_service import indicator_service
```

**新增 schema（在现有 schema 之后）：**

```python
class RealtimeSaveRequest(BaseModel):
    period: str = "daily"
    offset: int = 10
```

**新增接口（添加在现有路由之后）：**

```python
@router.post('/realtime/{code}/save')
def save_realtime_kline(
    code: str,
    req: RealtimeSaveRequest,
    _: str = Query(None, alias='api_key'),
):
    """将实时日K数据写入数据库，并返回带指标的K线数据"""
    symbol = code.split('.')[-1] if '.' in code else code
    db = SessionLocal()
    try:
        # 写入 DB
        realtime_service.save_to_db(symbol=symbol, db_session=db, offset=req.offset)

        # 按周期计算日期范围
        today = date.today()
        if req.period == 'daily':
            start_date = today - timedelta(days=7)
        elif req.period == 'weekly':
            start_date = today - timedelta(days=365)
        else:  # monthly
            start_date = today - timedelta(days=365 * 3)

        # 读取带指标的 K 线数据
        data = indicator_service.get_kline_with_indicators(
            db=db,
            stock_code=code,
            period=req.period,
            start_date=start_date,
            end_date=today,
        )
        return {
            'success': True,
            'code': code,
            'period': req.period,
            'data': data,
        }
    except Exception as e:
        logger.error(f'save_realtime_kline error: {e}')
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
```

**注意：** 需要在文件顶部添加 `from datetime import timedelta` 和 `import logging`，以及 `logger = logging.getLogger(__name__)`。

**验证：**
```
curl -X POST "http://localhost:8808/api/realtime/000001/save?api_key=yourkey" \
  -H "Content-Type: application/json" \
  -d '{"period":"daily","offset":5}'
```

应返回包含技术指标的 K 线 JSON。

Commit message: `feat(api: add POST /api/realtime/{code}/save upsert + return indicators`

---

## Task 3: 前端 StockChart 重构

**Files:**
- Modify: `frontend/src/pages/StockChart.tsx`

### 3.1 更新 import

```typescript
// 改前
import { getStockIndicators, getStock } from '../services/api'
import type { KlineIndicator } from '../types'

// 改后
import { getStockIndicators, getStock, getRealtimeBars, saveRealtimeKline } from '../services/api'
import type { KlineIndicator } from '../types'
```

### 3.2 重构 loadData()

将现有的 `loadData` 函数改为：

```typescript
const loadData = async () => {
  if (!code) return

  setLoading(true)
  try {
    const stockInfo = await getStock(code)
    setStockName(stockInfo.name)

    // 先写入实时数据到 DB，再从 DB 读取带指标的 K 线
    const today = new Date().toISOString().split('T')[0]
    let startDate: string
    if (period === 'daily') {
      startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    } else if (period === 'weekly') {
      startDate = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    } else {
      startDate = new Date(Date.now() - 3 * 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
    }

    let klineData: KlineIndicator[]

    if (period === 'daily') {
      // 日K：先 save 再读
      const saved = await saveRealtimeKline(code, period, 10)
      klineData = saved?.data ?? []
    } else {
      // 周K/月K：从 DB 直接读
      const response = await getStockIndicators(code, period, startDate, today)
      klineData = response.data
    }

    setKlineData(klineData)
  } catch (error) {
    message.error('加载K线数据失败')
  } finally {
    setLoading(false)
  }
}
```

### 3.3 重构 10 秒轮询 useEffect

将现有的 realtime polling useEffect 改为：

```typescript
// Realtime polling every 10 seconds - save to DB + update frontend state
useEffect(() => {
  if (!code) return

  const pollRealtime = async () => {
    try {
      // 日K时才写入DB并更新
      if (period !== 'daily') return
      const saved = await saveRealtimeKline(code, 'daily', 5)
      if (saved?.data?.length) {
        setKlineData(prev => {
          const merged = [...prev]
          for (const bar of saved.data ?? []) {
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
      }
    } catch (e) {
      console.warn('Realtime poll failed:', e)
    }
  }

  pollRealtime()
  const interval = setInterval(pollRealtime, 10_000)
  return () => clearInterval(interval)
}, [code, period])
```

### 3.4 调整 useEffect 依赖

将原有的依赖 `[code, period]` 的 useEffect 改为调用 `loadData` 时带上正确的日期参数（已在 loadData 内部处理）。

---

**验证：**
```bash
cd frontend && npm run dev
```
打开浏览器，进入股票 K 线页，观察 Network 面板：
- 每次进入页面，应该先有一个 `POST /api/realtime/.../save` 请求
- 然后有 `GET /api/stocks/.../indicators` 请求
- 每 10 秒有一次 `POST /api/realtime/.../save` 请求

Commit message: `feat(frontend): use save-then-read pattern on StockChart entry`

---

## Task 4: 前端 API 新增 saveRealtimeKline

**Files:**
- Modify: `frontend/src/services/api.ts`

**新增函数（添加在 getRealtimeBars 之后）：**

```typescript
export async function saveRealtimeKline(
  code: string,
  period: string,
  offset: number
): Promise<{
  success: boolean
  code: string
  period: string
  data: KlineIndicator[]
}> {
  const response = await fetch(`${API_BASE_URL}/api/realtime/${code}/save?api_key=${API_KEY}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ period, offset }),
  })
  if (!response.ok) throw new Error('Failed to save realtime kline')
  return response.json()
}
```

**验证：**
```bash
cd frontend && npx tsc --noEmit src/services/api.ts 2>&1 | head -10
```

Commit message: `feat(frontend): add saveRealtimeKline API function`

---

## 自检清单

1. `D:/anaconda3/envs/backing/python.exe -c "from app.services.realtime_service import realtime_service; print('OK')"`
2. `curl -X POST "http://localhost:8808/api/realtime/000001/save?api_key=xxx" -H "Content-Type: application/json" -d '{"period":"daily","offset":5}'` 返回带指标 JSON
3. 前端 StockChart 进入页面时 Network 有 save 请求
4. 日K时每10秒有一次 save 请求