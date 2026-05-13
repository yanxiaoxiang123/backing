"""
预测服务模块
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any
from datetime import timedelta
import logging

from app.services.dl_prediction.features import DLFeatures
from app.services.dl_prediction.model_loader import DLModelLoader
from app.config import settings

logger = logging.getLogger(__name__)


class TechnicalIndicatorPredictor:
    """基于技术指标的预测器 - 当PyTorch模型不可用时的备选方案"""

    @staticmethod
    def predict(df: pd.DataFrame, days: int = 5) -> np.ndarray:
        """
        使用技术指标进行价格预测

        Args:
            df: 包含OHLCV数据的DataFrame
            days: 预测天数

        Returns:
            预测价格数组
        """
        close = df["close"].values
        volume = df.get("vol", df.get("volume", pd.Series([0] * len(close)))).values

        current_price = float(close[-1])

        # 计算各种技术指标
        # 1. 简单移动平均线 (SMA)
        sma_5 = np.mean(close[-5:]) if len(close) >= 5 else current_price
        sma_10 = np.mean(close[-10:]) if len(close) >= 10 else sma_5
        sma_20 = np.mean(close[-20:]) if len(close) >= 20 else sma_10

        # 2. 指数移动平均 (EMA)
        def calc_ema(data, period):
            if len(data) < period:
                return np.mean(data)
            ema = data[0]
            alpha = 2 / (period + 1)
            for price in data[1:]:
                ema = alpha * price + (1 - alpha) * ema
            return ema

        ema_12 = calc_ema(close, 12) if len(close) >= 12 else sma_10
        ema_26 = calc_ema(close, 26) if len(close) >= 26 else sma_20

        # 3. MACD
        macd_line = ema_12 - ema_26
        signal_line = calc_ema(close, 9) if len(close) >= 9 else macd_line
        macd_histogram = macd_line - signal_line

        # 4. RSI (相对强弱指数)
        def calc_rsi(data, period=14):
            if len(data) < period + 1:
                return 50  # 中性值
            deltas = np.diff(data[-period - 1 :])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            if avg_loss == 0:
                return 100
            rs = avg_gain / avg_loss
            return 100 - (100 / (1 + rs))

        rsi = calc_rsi(close)

        # 5. 布林带
        def calc_bollinger_bands(data, period=20):
            if len(data) < period:
                return np.mean(data), np.mean(data), np.mean(data)
            sma = np.mean(data[-period:])
            std = np.std(data[-period:])
            return sma, sma + 2 * std, sma - 2 * std

        bb_middle, bb_upper, bb_lower = calc_bollinger_bands(close)

        # 6. 支撑位和阻力位 (基于最近的高低点)
        _ = np.max(close[-10:]) if len(close) >= 10 else current_price
        _ = np.min(close[-10:]) if len(close) >= 10 else current_price

        # 7. 价格动量
        momentum_5 = (close[-1] - close[-6]) / close[-6] if len(close) >= 6 else 0

        # 8. 成交量趋势
        if len(volume) >= 10:
            vol_ma = np.mean(volume[-10:])
            vol_trend = np.mean(volume[-5:]) / vol_ma if vol_ma > 0 else 1
        else:
            vol_trend = 1

        # 综合预测算法
        predictions = []

        for day in range(1, days + 1):
            # 基础预测：使用趋势外推
            trend_factor = 1.0

            # 基于MA判断趋势方向
            if sma_5 > sma_10 > sma_20:
                trend_factor = 1.005  # 上升趋势
            elif sma_5 < sma_10 < sma_20:
                trend_factor = 0.995  # 下降趋势

            # 基于RSI调整
            if rsi > 70:  # 超买
                trend_factor *= 0.998
            elif rsi < 30:  # 超卖
                trend_factor *= 1.002

            # 基于MACD调整
            if macd_histogram > 0:
                trend_factor *= 1.002
            else:
                trend_factor *= 0.998

            # 基于动量调整
            trend_factor *= 1 + momentum_5 * 0.1

            # 基于成交量调整
            if vol_trend > 1.2:
                trend_factor *= 1.001
            elif vol_trend < 0.8:
                trend_factor *= 0.999

            # 基于布林带位置调整
            if current_price > bb_upper:
                trend_factor *= 0.995  # 价格超过上轨，可能回调
            elif current_price < bb_lower:
                trend_factor *= 1.005  # 价格低于下轨，可能反弹

            # 限制每日变化幅度在 ±3% 以内
            trend_factor = max(0.97, min(1.03, trend_factor))

            # 计算预测价格
            predicted_price = current_price * (trend_factor**day)
            predictions.append(predicted_price)

        return np.array(predictions)


class DLPredictor:
    """预测服务"""

    def __init__(self):
        self.model_loader = DLModelLoader()
        self.features = DLFeatures()

    def predict(
        self, stock_code: str, kline_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        预测未来5天收盘价

        Args:
            stock_code: 股票代码
            kline_data: K线数据列表

        Returns:
            预测结果字典
        """
        try:
            # 转换为 DataFrame
            df = pd.DataFrame(kline_data)

            # 确保日期格式正确
            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"])
            elif "date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["date"])
                df = df.drop(columns=["date"])

            # 字段名映射：baostock 返回 volume，需要转换为 vol
            if "volume" in df.columns and "vol" not in df.columns:
                df["vol"] = df["volume"]

            # 计算技术指标
            df_with_features = self.features.compute_features(df)

            # 获取特征列
            feature_cols = self.features.get_feature_columns()

            # 检查数据是否足够
            time_steps = settings.DL_TIME_STEPS
            if len(df_with_features) < time_steps:
                logger.warning(f"数据不足 {time_steps} 天，使用全部数据")
                time_steps = len(df_with_features)

            # 获取最后 time_steps 天的特征
            features = df_with_features[feature_cols].values[-time_steps:]

            # 模型预测
            try:
                predicted_prices = self.model_loader.predict(features)
            except Exception as e:
                logger.warning(f"模型预测失败: {e}，使用技术指标预测")
                # 使用基于技术指标的预测
                predicted_prices = TechnicalIndicatorPredictor.predict(
                    df, days=settings.DL_OUTPUT_SIZE
                )

            # 获取当前价格和最后日期
            current_price = float(df["close"].iloc[-1])
            last_date = df["trade_date"].iloc[-1]

            # 生成预测日期
            prediction_dates = []
            current_date = pd.Timestamp(last_date)
            for i in range(settings.DL_OUTPUT_SIZE):
                next_date = current_date + timedelta(days=i + 1)
                # 跳过周末
                while next_date.dayofweek >= 5:
                    next_date = next_date + timedelta(days=1)
                prediction_dates.append(next_date.strftime("%Y-%m-%d"))

            # 返回预测结果
            result = {
                "stock_code": stock_code,
                "current_price": current_price,
                "last_date": last_date.strftime("%Y-%m-%d"),
                "prediction_dates": prediction_dates,
                "predicted_prices": [float(p) for p in predicted_prices],
                "kline_data": self._format_kline_data(df),
            }

            logger.info(f"预测完成: {stock_code}, 预测价格: {predicted_prices}")

            # 预测完成后清除模型，释放显存
            self.model_loader.clear_model()

            return result

        except Exception as e:
            logger.error(f"预测失败: {e}")
            raise

    def _format_kline_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """格式化K线数据"""
        result = []
        for _, row in df.iterrows():
            date_val = row["trade_date"]
            if isinstance(date_val, str):
                date_str = date_val
            else:
                date_str = date_val.strftime("%Y-%m-%d")

            result.append(
                {
                    "date": date_str,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["vol"])
                    if "vol" in row
                    else float(row.get("volume", 0)),
                }
            )
        return result
