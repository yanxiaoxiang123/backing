"""
Technical indicators library for trading strategies.

Provides implementations of various technical analysis indicators including:
- Trend indicators (SMA, EMA, WMA, HullMA, MACD, ADX)
- Momentum indicators (RSI, Stochastic, CCI, ROC, Momentum, Williams R)
- Volatility indicators (ATR, Bollinger Bands, StdDev)
- Volume indicators (OBV, VWAP, VolumeMA, VolumeRatio)
"""

import numpy as np
import pandas as pd
from typing import Dict


class TechnicalFactors:
    """Technical analysis factor library with static methods."""

    # ==================== Trend Factors ====================

    @staticmethod
    def SMA(series: pd.Series, period: int) -> pd.Series:
        """
        Simple Moving Average.

        Args:
            series: Price series
            period: Number of periods for moving average

        Returns:
            SMA values as pd.Series
        """
        return series.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def EMA(series: pd.Series, period: int) -> pd.Series:
        """
        Exponential Moving Average.

        Args:
            series: Price series
            period: Number of periods for EMA

        Returns:
            EMA values as pd.Series
        """
        return series.ewm(span=period, adjust=False, min_periods=1).mean()

    @staticmethod
    def WMA(series: pd.Series, period: int) -> pd.Series:
        """
        Weighted Moving Average.

        Args:
            series: Price series
            period: Number of periods for WMA

        Returns:
            WMA values as pd.Series
        """
        weights = np.arange(1, period + 1)

        def weighted_mean(x):
            if len(x) < period:
                return np.nan
            valid_weights = weights[: len(x)]
            return np.sum(valid_weights * x) / np.sum(valid_weights)

        return series.rolling(window=period, min_periods=period).apply(
            weighted_mean, raw=True
        )

    @staticmethod
    def HullMA(series: pd.Series, period: int) -> pd.Series:
        """
        Hull Moving Average.

        Args:
            series: Price series
            period: Number of periods for HullMA

        Returns:
            HullMA values as pd.Series
        """
        wma1 = TechnicalFactors.WMA(series, period)
        wma2 = TechnicalFactors.WMA(series, period // 2)

        # Handle potential NaN values
        if isinstance(wma2, pd.Series):
            hull = 2 * wma2 - TechnicalFactors.WMA(wma1.fillna(series), period)
        else:
            hull = 2 * wma2 - TechnicalFactors.WMA(series, period)

        # Use integer period for sqrt
        sqrt_period = int(np.sqrt(period))
        return TechnicalFactors.WMA(hull, sqrt_period)

    @staticmethod
    def MACD(
        series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Dict[str, pd.Series]:
        """
        Moving Average Convergence Divergence (MACD).

        Args:
            series: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period

        Returns:
            Dictionary with 'dif', 'dea', 'histogram' keys
        """
        ema_fast = TechnicalFactors.EMA(series, fast)
        ema_slow = TechnicalFactors.EMA(series, slow)

        dif = ema_fast - ema_slow
        dea = TechnicalFactors.EMA(dif, signal)
        histogram = dif - dea

        return {"dif": dif, "dea": dea, "histogram": histogram}

    @staticmethod
    def ADX(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> Dict[str, pd.Series]:
        """
        Average Directional Index.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: Number of periods

        Returns:
            Dictionary with 'adx', 'plus_di', 'minus_di' keys
        """
        high_diff = high.diff()
        low_diff = -low.diff()

        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0.0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0.0)

        # True Range
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period, min_periods=period).mean()

        # Handle division by zero
        plus_di = 100 * (
            plus_dm.rolling(window=period, min_periods=period).mean() / atr
        )
        minus_di = 100 * (
            minus_dm.rolling(window=period, min_periods=period).mean() / atr
        )

        # DX calculation
        di_sum = plus_di + minus_di
        dx = 100 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan)

        # ADX calculation
        adx = TechnicalFactors.EMA(dx.fillna(0), period)

        return {"adx": adx, "plus_di": plus_di, "minus_di": minus_di}

    # ==================== Momentum Factors ====================

    @staticmethod
    def RSI(series: pd.Series, period: int = 14) -> pd.Series:
        """
        Relative Strength Index.

        Args:
            series: Price series
            period: Number of periods

        Returns:
            RSI values as pd.Series
        """
        delta = series.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        # Use EMA for subsequent values
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def Stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3,
    ) -> Dict[str, pd.Series]:
        """
        Stochastic Oscillator.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            k_period: %K period
            d_period: %D period

        Returns:
            Dictionary with 'k', 'd' keys
        """
        lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
        highest_high = high.rolling(window=k_period, min_periods=k_period).max()

        # Handle division by zero
        denominator = highest_high - lowest_low
        k = 100 * (close - lowest_low) / denominator.replace(0, np.nan)

        d = k.rolling(window=d_period, min_periods=d_period).mean()

        return {"k": k, "d": d}

    @staticmethod
    def CCI(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20
    ) -> pd.Series:
        """
        Commodity Channel Index.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: Number of periods

        Returns:
            CCI values as pd.Series
        """
        typical_price = (high + low + close) / 3
        sma = typical_price.rolling(window=period, min_periods=period).mean()

        mean_deviation = typical_price.rolling(window=period, min_periods=period).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
        )

        cci = (typical_price - sma) / (0.015 * mean_deviation.replace(0, np.nan))

        return cci

    @staticmethod
    def ROC(series: pd.Series, period: int = 12) -> pd.Series:
        """
        Rate of Change.

        Args:
            series: Price series
            period: Number of periods

        Returns:
            ROC values as pd.Series
        """
        roc = (
            100
            * (series - series.shift(period))
            / series.shift(period).replace(0, np.nan)
        )
        return roc

    @staticmethod
    def Momentum(series: pd.Series, period: int = 10) -> pd.Series:
        """
        Momentum indicator.

        Args:
            series: Price series
            period: Number of periods

        Returns:
            Momentum values as pd.Series
        """
        return series - series.shift(period)

    @staticmethod
    def WilliamsR(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """
        Williams %R.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: Number of periods

        Returns:
            Williams %R values as pd.Series
        """
        highest_high = high.rolling(window=period, min_periods=period).max()
        lowest_low = low.rolling(window=period, min_periods=period).min()

        williams_r = (
            -100
            * (highest_high - close)
            / (highest_high - lowest_low).replace(0, np.nan)
        )

        return williams_r

    # ==================== Volatility Factors ====================

    @staticmethod
    def ATR(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """
        Average True Range.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: Number of periods

        Returns:
            ATR values as pd.Series
        """
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        return tr.rolling(window=period, min_periods=period).mean()

    @staticmethod
    def BollingerBands(
        series: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> Dict[str, pd.Series]:
        """
        Bollinger Bands.

        Args:
            series: Price series
            period: Number of periods for moving average
            std_dev: Number of standard deviations

        Returns:
            Dictionary with 'upper', 'middle', 'lower', 'bandwidth', 'percent' keys
        """
        middle = series.rolling(window=period, min_periods=period).mean()
        std = series.rolling(window=period, min_periods=period).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        bandwidth = (upper - lower) / middle.replace(0, np.nan)
        percent = (series - lower) / (upper - lower).replace(0, np.nan)

        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "bandwidth": bandwidth,
            "percent": percent,
        }

    @staticmethod
    def StdDev(series: pd.Series, period: int = 20) -> pd.Series:
        """
        Standard Deviation.

        Args:
            series: Price series
            period: Number of periods

        Returns:
            Standard deviation values as pd.Series
        """
        return series.rolling(window=period, min_periods=period).std()

    @staticmethod
    def DonchianChannel(
        high: pd.Series, low: pd.Series, period: int = 20
    ) -> Dict[str, pd.Series]:
        """
        Donchian Channel.

        Args:
            high: High price series
            low: Low price series
            period: Number of periods

        Returns:
            Dictionary with 'upper', 'middle', 'lower' keys
        """
        upper = high.rolling(window=period, min_periods=period).max()
        lower = low.rolling(window=period, min_periods=period).min()
        middle = (upper + lower) / 2

        return {"upper": upper, "middle": middle, "lower": lower}

    @staticmethod
    def KeltnerChannel(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        ema_period: int = 20,
        atr_period: int = 10,
        atr_multiplier: float = 1.5,
    ) -> Dict[str, pd.Series]:
        """
        Keltner Channel.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            ema_period: EMA period for middle line
            atr_period: ATR period for channel width
            atr_multiplier: ATR multiplier for channel width

        Returns:
            Dictionary with 'upper', 'middle', 'lower' keys
        """
        middle = TechnicalFactors.EMA(close, ema_period)
        atr = TechnicalFactors.ATR(high, low, close, atr_period)

        upper = middle + atr_multiplier * atr
        lower = middle - atr_multiplier * atr

        return {"upper": upper, "middle": middle, "lower": lower}

    # ==================== Volume Factors ====================

    @staticmethod
    def OBV(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        On-Balance Volume.

        Args:
            close: Close price series
            volume: Volume series

        Returns:
            OBV values as pd.Series
        """
        direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        obv = (direction * volume).cumsum()
        return obv

    @staticmethod
    def VWAP(
        close: pd.Series, high: pd.Series, low: pd.Series, volume: pd.Series
    ) -> pd.Series:
        """
        Volume Weighted Average Price.

        Args:
            close: Close price series
            high: High price series
            low: Low price series
            volume: Volume series

        Returns:
            VWAP values as pd.Series
        """
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        return vwap

    @staticmethod
    def VolumeMA(volume: pd.Series, period: int = 20) -> pd.Series:
        """
        Volume Moving Average.

        Args:
            volume: Volume series
            period: Number of periods

        Returns:
            Volume MA values as pd.Series
        """
        return volume.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def VolumeRatio(volume: pd.Series, period: int = 5) -> pd.Series:
        """
        Volume Ratio.

        Args:
            volume: Volume series
            period: Number of periods for comparison

        Returns:
            Volume ratio values as pd.Series
        """
        volume_ma = volume.rolling(window=period, min_periods=period).mean()
        ratio = volume / volume_ma.replace(0, np.nan)
        return ratio
