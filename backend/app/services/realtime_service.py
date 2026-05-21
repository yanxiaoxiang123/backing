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
            cls._client = Quotes.factory(market='std')
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
        if df is None or (hasattr(df, 'empty') and df.empty):
            return []

        records = []
        for _, row in df.iterrows():
            # 从 datetime 列提取日期字符串
            dt = str(row.get('datetime', ''))
            date_str = dt[:10] if len(dt) >= 10 else dt
            records.append({
                'date': date_str,
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'volume': float(row.get('vol', row.get('volume', 0))),
                'amount': float(row.get('amount', 0)),
                'symbol': symbol,
            })
        return records


# Singleton instance
realtime_service = RealtimeService()