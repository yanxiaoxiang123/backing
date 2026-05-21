# StockChart 实时数据写入数据库方案

## 需求

1. 进入 StockChart 页面时，用 mootdx 实时数据写入数据库
2. 每 10 秒轮询时，同样写入数据库（upsert）
3. 切换周期时按需加载：
   - 日 K → 加载最近 7 天
   - 周 K → 加载最近 1 年
   - 月 K → 加载最近 3 年

## 架构

### 数据流

```
用户进入 StockChart
  │
  ├→ mootdx.get_realtime_bars(code)  → 拿最新日K数据
  │                                   ↓
  └──────────────────────────────→ upsert 到 DailyKline 表
                                        ↓
                              从 DB 读取所有周期数据
                                        ↓
                              getStockIndicators(code)
                                        ↓
                              返回带指标的 K 线数据

每 10 秒轮询：
  └→ mootdx → upsert 最新日K到 DB → 更新前端状态（setKlineData）
```

### 关键改动

**后端：**
- `realtime_service.py` 新增 `save_to_db()` 方法：将 bars 数据 upsert 到 DailyKline 表
- `realtime.py` 路由新增 `POST /api/realtime/{code}/save` 接口：写入 DB 并返回指标数据

**前端 StockChart：**
- 进入页面时：先调用 `/api/realtime/{code}/save`，再从 DB 读取指标
- 10 秒轮询：调用同一个 save 接口（upsert），前端用返回数据更新状态
- 周期切换：按周期调整 offset（7天/1年/3年）传给 mootdx

### API 设计

`POST /api/realtime/{code}/save`

**请求体：**
```json
{
  "period": "daily" | "weekly" | "monthly",
  "offset": 7  // 加载数据条数
}
```

**响应：** 同 `getStockIndicators` 的返回结构（带技术指标）

### 数据库写入逻辑

`realtime_service.save_to_db()`：
1. 调用 `normalise_bars(symbol, offset)` 获取规范化的 bars 数据
2. 对每条 bar 执行 upsert（`INSERT OR REPLACE INTO daily_kline ...`）
3. 通过 `indicator_service` 计算技术指标
4. 返回带指标的完整 K 线数据

### 频率控制

- mootdx 本身有频率限制，每 10 秒调用一次是安全的
- upsert 使用 SQLite 的 `INSERT OR REPLACE`，同一主键重复写入无影响

## 实现步骤

1. `RealtimeService.save_to_db()` 方法（backend/app/services/realtime_service.py）
2. `POST /api/realtime/{code}/save` 路由（backend/app/api/realtime.py）
3. 前端 `StockChart.tsx` 重构 `loadData()`：进入时先 save 再读
4. 10 秒轮询改用 save 接口
5. 周期切换逻辑调整（offset 参数）