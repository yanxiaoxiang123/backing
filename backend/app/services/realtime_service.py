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

    def bars(self, symbol: str, frequency: int = 9, offset: int = 750) -> pd.DataFrame:
        """获取实时K线数据

        Args:
            symbol: 股票代码，如 "600036"（不带市场前缀）
            frequency: 周期，9=日K，5=周K，6=月K
            offset: 返回最近 N 条，默认 750（3年交易日）

        Returns:
            DataFrame，列名: open, close, high, low, vol, amount, datetime, volume
        """
        client = self.get_client()
        try:
            df = client.bars(symbol=symbol, frequency=frequency, offset=offset)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"mootdx bars error for {symbol}: {e}")
            return pd.DataFrame()

    def normalise_bars(self, symbol: str, frequency: int = 9, offset: int = 750) -> List[Dict[str, Any]]:
        """将 bars 数据规范化为 dict 列表"""
        df = self.bars(symbol=symbol, frequency=frequency, offset=offset)
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


# Singleton instance
realtime_service = RealtimeService()