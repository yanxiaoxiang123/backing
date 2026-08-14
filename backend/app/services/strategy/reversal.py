"""Reversal strategies: Mean Reversion, RSI Reversal, and MACD Divergence."""

from typing import Any, Dict

import numpy as np
import pandas as pd

from .base import Parameter, ParameterType, Strategy
from .factors import TechnicalFactors
from .registry import register_strategy


@register_strategy("mean_reversion")
class MeanReversionStrategy(Strategy):
    """
    Mean Reversion Strategy.

    Generates signals when price deviates from moving average
    by more than a specified number of standard deviations.
    """

    def __init__(self, period: int = 20, std_threshold: float = 2.0):
        self.period = period
        self.std_threshold = std_threshold

    def get_name(self) -> str:
        return "mean_reversion"

    def get_description(self) -> str:
        return "Mean reversion strategy: buy when price is below MA by std_threshold times, sell when above"

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "period": Parameter(
                name="period",
                param_type=ParameterType.INT,
                default=self.period,
                min_value=10,
                max_value=60,
                description="MA period for mean calculation",
            ),
            "std_threshold": Parameter(
                name="std_threshold",
                param_type=ParameterType.FLOAT,
                default=self.std_threshold,
                min_value=1.0,
                max_value=3.0,
                description="Standard deviation threshold for signals",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        close = df["close"]

        # Calculate moving average and standard deviation
        df["ma"] = TechnicalFactors.SMA(close, self.period)
        df["std"] = TechnicalFactors.StdDev(close, self.period)

        # Calculate upper and lower bands
        df["upper_band"] = df["ma"] + (df["std"] * self.std_threshold)
        df["lower_band"] = df["ma"] - (df["std"] * self.std_threshold)

        # Calculate distance from MA in terms of std
        df["distance"] = (close - df["ma"]) / df["std"].replace(0, np.nan)

        # Initialize signal column
        df["signal"] = 0

        # Generate signals using vectorized operations
        buy_condition = (df["distance"] < -self.std_threshold) & pd.notna(df["distance"])
        sell_condition = (df["distance"] > self.std_threshold) & pd.notna(df["distance"])
        df.loc[buy_condition, "signal"] = 1
        df.loc[sell_condition, "signal"] = -1

        return df


@register_strategy("rsi_reversal")
class RSIReversalStrategy(Strategy):
    """
    RSI Reversal Strategy.

    Generates buy signals when RSI falls below oversold level,
    and sell signals when RSI rises above overbought level.
    """

    def __init__(self, rsi_period: int = 14, oversold: int = 30, overbought: int = 70):
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    def get_name(self) -> str:
        return "rsi_reversal"

    def get_description(self) -> str:
        return f"RSI reversal: buy when RSI < {self.oversold}, sell when RSI > {self.overbought}"

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "rsi_period": Parameter(
                name="rsi_period",
                param_type=ParameterType.INT,
                default=self.rsi_period,
                min_value=5,
                max_value=30,
                description="RSI calculation period",
            ),
            "oversold": Parameter(
                name="oversold",
                param_type=ParameterType.INT,
                default=self.oversold,
                min_value=20,
                max_value=40,
                description="Oversold threshold (buy below this)",
            ),
            "overbought": Parameter(
                name="overbought",
                param_type=ParameterType.INT,
                default=self.overbought,
                min_value=60,
                max_value=80,
                description="Overbought threshold (sell above this)",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        close = df["close"]

        # Calculate RSI
        df["rsi"] = TechnicalFactors.RSI(close, self.rsi_period)

        # Initialize signal column
        df["signal"] = 0

        # Generate signals using vectorized operations
        buy_condition = (df["rsi"] < self.oversold) & pd.notna(df["rsi"])
        sell_condition = (df["rsi"] > self.overbought) & pd.notna(df["rsi"])
        df.loc[buy_condition, "signal"] = 1
        df.loc[sell_condition, "signal"] = -1

        return df


@register_strategy("macd_divergence")
class MACDHistogramDivergenceStrategy(Strategy):
    """
    MACD Histogram Divergence Strategy.

    Detects divergences between price action and MACD histogram:
    - Bullish Divergence: Price makes lower low, MACD histogram makes higher low → BUY
    - Bearish Divergence: Price makes higher high, MACD histogram makes lower high → SELL

    Uses swing detection to find pivot points in both series,
    then compares the most recent pair of swings for divergence.
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def get_name(self) -> str:
        return "macd_divergence"

    def get_description(self) -> str:
        return (
            f"MACD Divergence: detects price-histogram divergences "
            f"(fast={self.fast}, slow={self.slow}, signal={self.signal})"
        )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "fast": Parameter(
                name="fast",
                param_type=ParameterType.INT,
                default=self.fast,
                min_value=5,
                max_value=20,
                description="Fast EMA period",
            ),
            "slow": Parameter(
                name="slow",
                param_type=ParameterType.INT,
                default=self.slow,
                min_value=15,
                max_value=50,
                description="Slow EMA period",
            ),
            "signal": Parameter(
                name="signal",
                param_type=ParameterType.INT,
                default=self.signal,
                min_value=5,
                max_value=15,
                description="Signal line period",
            ),
        }

    def _find_pivots(
        self, series: pd.Series, lookback: int = 5
    ) -> tuple[pd.Series, pd.Series]:
        """
        Find pivot highs and lows in a series.

        Returns (pivot_highs, pivot_lows) where each is a Series
        with the pivot value at the pivot index and NaN elsewhere.
        """
        pivot_high = pd.Series(np.nan, index=series.index)
        pivot_low = pd.Series(np.nan, index=series.index)

        for i in range(lookback, len(series) - lookback):
            window = series.iloc[i - lookback : i + lookback + 1]
            center = series.iloc[i]

            if center == window.max() and not pd.isna(center):
                pivot_high.iloc[i] = center
            if center == window.min() and not pd.isna(center):
                pivot_low.iloc[i] = center

        return pivot_high, pivot_low

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        close = df["close"]

        # Calculate MACD
        macd = TechnicalFactors.MACD(close, self.fast, self.slow, self.signal)
        df["dif"] = macd["dif"]
        df["dea"] = macd["dea"]
        df["histogram"] = macd["histogram"]

        df["signal"] = 0

        # Find pivots in price and histogram
        lookback = 5
        price_high, price_low = self._find_pivots(close, lookback)
        hist_high, hist_low = self._find_pivots(df["histogram"], lookback)

        # Detect divergences
        for i in range(lookback * 2 + 1, len(df)):
            # --- Bearish Divergence ---
            # Price makes higher high, histogram makes lower high
            if pd.notna(price_high.iloc[i]) and pd.notna(hist_high.iloc[i]):
                # Find previous price high and histogram high
                prev_price_high_idx = price_high.iloc[:i].last_valid_index()
                prev_hist_high_idx = hist_high.iloc[:i].last_valid_index()

                if prev_price_high_idx is not None and prev_hist_high_idx is not None:
                    prev_price_val = float(price_high.loc[prev_price_high_idx])
                    prev_hist_val = float(hist_high.loc[prev_hist_high_idx])
                    curr_price_val = float(price_high.iloc[i])
                    curr_hist_val = float(hist_high.iloc[i])

                    if curr_price_val > prev_price_val and curr_hist_val < prev_hist_val:
                        df.loc[df.index[i], "signal"] = -1  # Sell

            # --- Bullish Divergence ---
            # Price makes lower low, histogram makes higher low
            if pd.notna(price_low.iloc[i]) and pd.notna(hist_low.iloc[i]):
                prev_price_low_idx = price_low.iloc[:i].last_valid_index()
                prev_hist_low_idx = hist_low.iloc[:i].last_valid_index()

                if prev_price_low_idx is not None and prev_hist_low_idx is not None:
                    prev_price_val = float(price_low.loc[prev_price_low_idx])
                    prev_hist_val = float(hist_low.loc[prev_hist_low_idx])
                    curr_price_val = float(price_low.iloc[i])
                    curr_hist_val = float(hist_low.iloc[i])

                    if curr_price_val < prev_price_val and curr_hist_val > prev_hist_val:
                        df.loc[df.index[i], "signal"] = 1  # Buy

        return df
