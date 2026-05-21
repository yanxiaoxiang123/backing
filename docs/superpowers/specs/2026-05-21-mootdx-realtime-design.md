# mootdx 实时行情集成方案

## 需求

为 backing 项目添加 mootdx 实时日 K 数据源，用于 Dashboard 和 StockChart，每 10 秒刷新一次。

## 设计

### 新增文件

**`backend/app/services/realtime_service.py`**

```python
from mootdx.quotes import Quotes
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class RealtimeService:
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            cls._client = Quotes.factory(market='std', multithread=True, heartbeat=True)
        return cls._client

    def bars(self, symbol: str, frequency: int = 9, offset: int = 10) -> pd.DataFrame:
        """获取实时日K数据
        frequency=9 表示日K线，offset=10 返回最近10条
        """
        client = self.get_client()
        try:
            df = client.bars(symbol=symbol, frequency=frequency, offset=offset)
            return df
        except Exception as e:
            logger.error(f"mootdx bars error for {symbol}: {e}")
            return pd.DataFrame()
```

**`backend/app/api/realtime.py`**（新增路由文件）

- `GET /api/realtime/{code}` → 返回该股票实时日K（最近10条）
- `GET /api/realtime/indices` → 返回主要指数实时数据

### 环境配置

**`.env`** 新增一行：
```
REALTIME_PROVIDER=mootdx
```

### API 返回格式

```json
{
  "code": "000001",
  "name": "平安银行",
  "data": [
    {"date": "2026-05-21", "open": 10.75, "high": 10.80, "low": 10.68, "close": 10.76, "volume": 1234567},
    ...
  ]
}
```

### 错误处理

- mootdx 连接失败：返回空 data 数组，前端使用数据库缓存数据降级
- 收盘后无实时数据：同样降级到数据库

### 前端

- Dashboard 和 StockChart 轮询 `/api/realtime/{code}`，10 秒间隔
- 前端已有基础设施，无需大幅改动

## 实现步骤

1. 新增 `realtime_service.py`
2. 新增 `backend/app/api/realtime.py` 路由
3. 在 `backend/app/api/routes.py` 中注册路由
4. `.env` 添加 REALTIME_PROVIDER
5. 前端 Dashboard / StockChart 添加轮询调用