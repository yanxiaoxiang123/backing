"""
技术指标计算服务
"""

import time
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import date
from sqlalchemy.orm import Session


class IndicatorService:
    """技术指标计算服务"""

    def __init__(self):
        self._cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._cache_ttl: int = 300  # 5 分钟缓存有效期

    def _cache_key(
        self,
        stock_code: str,
        period: str,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> str:
        return f"indicator:{stock_code}:{period}:{start_date}:{end_date}"

    def _cache_get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, result = entry
        if time.monotonic() - ts > self._cache_ttl:
            del self._cache[key]
            return None
        return result

    def _cache_set(self, key: str, result: List[Dict[str, Any]]) -> None:
        self._cache[key] = (time.monotonic(), result)

    def clear_cache(self, stock_code: Optional[str] = None) -> None:
        """清除全部或指定股票的缓存"""
        if stock_code is None:
            self._cache.clear()
        else:
            self._cache = {
                k: v for k, v in self._cache.items() if stock_code not in k
            }

    @staticmethod
    def calculate_ma(series: pd.Series, periods: List[int]) -> Dict[str, pd.Series]:
        """
        计算移动平均线

        Args:
            series: 收盘价序列
            periods: 周期列表，如 [5, 10, 20, 60, 120]

        Returns:
            字典，键为MA周期，值为对应的MA序列
        """
        result = {}
        for period in periods:
            result[f"ma{period}"] = series.rolling(window=period).mean()
        return result

    @staticmethod
    def calculate_macd(
        series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, pd.Series]:
        """
        计算MACD指标

        Args:
            series: 收盘价序列
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期

        Returns:
            字典，包含 dif, dea, macd
        """
        # 计算EMA
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()

        # DIF = 快线 - 慢线
        dif = ema_fast - ema_slow

        # DEA = DIF的EMA
        dea = dif.ewm(span=signal, adjust=False).mean()

        # MACD柱 = (DIF - DEA) * 2
        macd = (dif - dea) * 2

        return {"dif": dif, "dea": dea, "macd": macd}

    @staticmethod
    def calculate_kdj(
        high: pd.Series, low: pd.Series, close: pd.Series
    ) -> Dict[str, pd.Series]:
        """
        计算KDJ指标

        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列

        Returns:
            字典，包含 k, d, j
        """
        period = 9

        # 计算RSV (Raw Stochastic Value)
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()

        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        rsv = rsv.fillna(50)

        # 计算K、D、J值
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d

        return {"k": k, "d": d, "j": j}

    @staticmethod
    def calculate_rsi(
        series: pd.Series, periods: Optional[List[int]] = None
    ) -> Dict[str, pd.Series]:
        """
        计算RSI指标

        Args:
            series: 收盘价序列
            periods: 周期列表，如 [6, 12, 24]

        Returns:
            字典，键为RSI周期，值为对应的RSI序列
        """
        if periods is None:
            periods = [6, 12, 24]

        result = {}

        for period in periods:
            # 计算价格变化
            delta = series.diff()

            # 分离上涨和下跌
            gain = delta.where(delta > 0, 0)
            loss = (-delta).where(delta < 0, 0)

            # 计算平均上涨和下跌
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()

            # 计算RS和RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            rsi = rsi.fillna(50)

            result[f"rsi{period}"] = rsi

        return result

    def get_kline_with_indicators(
        self,
        db: Session,
        stock_code: str,
        period: str = "daily",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """获取K线数据及技术指标（带 5 分钟缓存）"""
        cache_key = self._cache_key(stock_code, period, start_date, end_date)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        from app.models.models import DailyKline

        # 查询K线数据
        query = db.query(DailyKline).filter(DailyKline.stock_code == stock_code)

        if start_date:
            query = query.filter(DailyKline.date >= start_date)
        if end_date:
            query = query.filter(DailyKline.date <= end_date)

        klines = query.order_by(DailyKline.date).all()

        if not klines:
            return []

        # 转换为DataFrame
        df = pd.DataFrame(
            [
                {
                    "date": k.date,
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "volume": k.volume,
                }
                for k in klines
            ]
        )

        # 聚合周期数据 (周K/月K)
        if period == "weekly":
            df = IndicatorService._aggregate_to_weekly(df)
        elif period == "monthly":
            df = IndicatorService._aggregate_to_monthly(df)

        # 计算技术指标
        close_series = df["close"]

        # MA
        ma_result = IndicatorService.calculate_ma(close_series, [5, 10, 20, 60, 120])
        for key, value in ma_result.items():
            df[key] = value

        # MACD
        macd_result = IndicatorService.calculate_macd(close_series)
        df["dif"] = macd_result["dif"]
        df["dea"] = macd_result["dea"]
        df["macd"] = macd_result["macd"]

        # KDJ
        kdj_result = IndicatorService.calculate_kdj(df["high"], df["low"], df["close"])
        df["kdj_k"] = kdj_result["k"]
        df["kdj_d"] = kdj_result["d"]
        df["kdj_j"] = kdj_result["j"]

        # RSI
        rsi_result = IndicatorService.calculate_rsi(close_series, [6, 12, 24])
        for key, value in rsi_result.items():
            df[key] = value

        # 转换为字典列表
        result = []
        for _, row in df.iterrows():
            result.append(
                {
                    "date": row["date"].isoformat()
                    if isinstance(row["date"], (pd.Timestamp, date))
                    else str(row["date"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "ma5": float(row["ma5"]) if pd.notna(row["ma5"]) else None,
                    "ma10": float(row["ma10"]) if pd.notna(row["ma10"]) else None,
                    "ma20": float(row["ma20"]) if pd.notna(row["ma20"]) else None,
                    "ma60": float(row["ma60"]) if pd.notna(row["ma60"]) else None,
                    "ma120": float(row["ma120"]) if pd.notna(row["ma120"]) else None,
                    "dif": float(row["dif"]) if pd.notna(row["dif"]) else None,
                    "dea": float(row["dea"]) if pd.notna(row["dea"]) else None,
                    "macd": float(row["macd"]) if pd.notna(row["macd"]) else None,
                    "kdj_k": float(row["kdj_k"]) if pd.notna(row["kdj_k"]) else None,
                    "kdj_d": float(row["kdj_d"]) if pd.notna(row["kdj_d"]) else None,
                    "kdj_j": float(row["kdj_j"]) if pd.notna(row["kdj_j"]) else None,
                    "rsi6": float(row["rsi6"]) if pd.notna(row["rsi6"]) else None,
                    "rsi12": float(row["rsi12"]) if pd.notna(row["rsi12"]) else None,
                    "rsi24": float(row["rsi24"]) if pd.notna(row["rsi24"]) else None,
                }
            )

        self._cache_set(cache_key, result)
        return result

    @staticmethod
    def _aggregate_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
        """聚合为周K线"""
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        # 按周聚合
        weekly = (
            df.resample("W", on="date")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )

        weekly = weekly.reset_index()
        return weekly

    @staticmethod
    def _aggregate_to_monthly(df: pd.DataFrame) -> pd.DataFrame:
        """聚合为月K线"""
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        # 按月聚合
        monthly = (
            df.resample("M", on="date")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )

        monthly = monthly.reset_index()
        return monthly


# 单例
indicator_service = IndicatorService()
