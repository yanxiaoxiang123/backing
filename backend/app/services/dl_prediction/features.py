"""
19个技术指标计算模块
与 data_preprocessing.py 中的特征保持一致
"""

import numpy as np
import pandas as pd
from typing import List


class DLFeatures:
    """19个技术指标计算"""

    FEATURE_NAMES: List[str] = [
        "open",
        "high",
        "low",
        "volatility_20",
        "daily_range",
        "volume_change",
        "macd",
        "rsi",
        "ma5",
        "ma20",
        "ema12",
        "ema26",
        "momentum",
        "vol_ma5",
        "atr",
        "obv",
        "bollinger_upper",
        "bollinger_lower",
        "price_volume_ratio",
    ]

    @staticmethod
    def compute_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        从K线数据计算19个特征

        Args:
            df: 包含 K线数据的 DataFrame
                必须包含: open, high, low, close, vol, trade_date

        Returns:
            添加了19个特征列的 DataFrame
        """
        result = df.copy()

        # 字段名映射：baostock 返回 volume，需要转换为 vol
        if "volume" in result.columns and "vol" not in result.columns:
            result["vol"] = result["volume"]
        elif "vol" not in result.columns:
            raise KeyError("数据中缺少成交量字段 (vol 或 volume)")

        # 基础价格数据
        result["open"] = result["open"]
        result["high"] = result["high"]
        result["low"] = result["low"]

        # 1. volatility_20: 20日波动率
        result["volatility_20"] = result["close"].pct_change().rolling(20).std()

        # 2. daily_range: 日内振幅
        result["daily_range"] = (result["high"] - result["low"]) / result["low"]

        # 3. volume_change: 成交量变化率
        result["volume_change"] = result["vol"].pct_change()

        # 4. MACD
        ema12 = result["close"].ewm(span=12, adjust=False).mean()
        ema26 = result["close"].ewm(span=26, adjust=False).mean()
        result["macd"] = ema12 - ema26

        # 5. RSI
        delta = result["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-8)
        result["rsi"] = 100 - (100 / (1 + rs))

        # 6. ma5: 5日移动平均
        result["ma5"] = result["close"].rolling(5).mean()

        # 7. ma20: 20日移动平均
        result["ma20"] = result["close"].rolling(20).mean()

        # 8. ema12
        result["ema12"] = ema12

        # 9. ema26
        result["ema26"] = ema26

        # 10. momentum: 动量 (5日涨幅)
        result["momentum"] = result["close"].pct_change(5)

        # 11. vol_ma5: 5日成交量均值
        result["vol_ma5"] = result["vol"].rolling(5).mean()

        # 12. ATR: 平均真实波幅
        result["atr"] = (result["high"] - result["low"]).rolling(14).mean()

        # 13. OBV: 能量潮指标
        result["obv"] = (np.sign(result["close"].diff()) * result["vol"]).cumsum()

        # 14. Bollinger Bands
        result["bollinger_upper"] = (
            result["ma20"] + 2 * result["close"].rolling(20).std()
        )
        result["bollinger_lower"] = (
            result["ma20"] - 2 * result["close"].rolling(20).std()
        )

        # 15. price_volume_ratio: 价格成交量比
        result["price_volume_ratio"] = result["close"] / result["vol"].replace(
            0, np.nan
        )

        # 删除包含 NaN 的行
        result = result.dropna().reset_index(drop=True)

        return result

    @staticmethod
    def get_feature_columns() -> List[str]:
        """获取特征列名列表"""
        return DLFeatures.FEATURE_NAMES.copy()
