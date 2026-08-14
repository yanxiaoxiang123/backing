"""Trend-following strategies: MA Cross, Momentum, and MACD Cross."""

from typing import Any, Dict

import numpy as np
import pandas as pd

from .base import Parameter, ParameterType, Strategy
from .factors import TechnicalFactors
from .registry import register_strategy


@register_strategy("ma_cross")
class MACrossStrategy(Strategy):
    """
    Moving Average Crossover Strategy.

    Generates buy signals when short MA crosses above long MA,
    and sell signals when short MA crosses below long MA.
    """

    def __init__(self, short_period: int = 5, long_period: int = 20):
        self.short_period = short_period
        self.long_period = long_period

    def get_name(self) -> str:
        return "ma_cross"

    def get_description(self) -> str:
        return "Moving average crossover strategy: buy when short MA crosses above long MA, sell when it crosses below"

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "short_period": Parameter(
                name="short_period",
                param_type=ParameterType.INT,
                default=self.short_period,
                min_value=1,
                max_value=30,
                description="Short MA period (days)",
            ),
            "long_period": Parameter(
                name="long_period",
                param_type=ParameterType.INT,
                default=self.long_period,
                min_value=10,
                max_value=120,
                description="Long MA period (days)",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        close = df["close"]

        # Calculate moving averages
        df["ma_short"] = TechnicalFactors.SMA(close, self.short_period)
        df["ma_long"] = TechnicalFactors.SMA(close, self.long_period)

        # Initialize signal column
        df["signal"] = 0

        # Generate crossover signals using vectorized operations
        # Buy when short MA crosses above long MA
        # Sell when short MA crosses below long MA
        buy_cross = (df["ma_short"] > df["ma_long"]) & (
            df["ma_short"].shift(1) <= df["ma_long"].shift(1)
        )
        df.loc[buy_cross, "signal"] = 1

        sell_cross = (df["ma_short"] < df["ma_long"]) & (
            df["ma_short"].shift(1) >= df["ma_long"].shift(1)
        )
        df.loc[sell_cross, "signal"] = -1

        return df


@register_strategy("momentum")
class MomentumStrategy(Strategy):
    """
    Momentum Strategy.

    Generates signals based on price momentum - buy when momentum
    is positive and above threshold, sell when negative and below threshold.
    """

    def __init__(self, period: int = 20, threshold: float = 0.02):
        self.period = period
        self.threshold = threshold

    def get_name(self) -> str:
        return "momentum"

    def get_description(self) -> str:
        return f"Momentum strategy: buy when momentum > {self.threshold}, sell when momentum < -{self.threshold}"

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "period": Parameter(
                name="period",
                param_type=ParameterType.INT,
                default=self.period,
                min_value=5,
                max_value=60,
                description="Period for momentum calculation",
            ),
            "threshold": Parameter(
                name="threshold",
                param_type=ParameterType.FLOAT,
                default=self.threshold,
                min_value=0.01,
                max_value=0.1,
                description="Momentum threshold for signals (as decimal)",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        close = df["close"]

        # Calculate momentum as percentage change
        df["momentum"] = TechnicalFactors.Momentum(close, self.period)
        df["momentum_pct"] = (close - close.shift(self.period)) / close.shift(
            self.period
        ).replace(0, np.nan)

        # Initialize signal column
        df["signal"] = 0

        # Generate signals using vectorized operations
        buy_condition = (df["momentum_pct"] > self.threshold) & pd.notna(df["momentum_pct"])
        sell_condition = (df["momentum_pct"] < -self.threshold) & pd.notna(df["momentum_pct"])
        df.loc[buy_condition, "signal"] = 1
        df.loc[sell_condition, "signal"] = -1

        return df


@register_strategy("macd_cross")
class MACDCrossStrategy(Strategy):
    """
    MACD Crossover Strategy.

    Generates buy signals when DIF crosses above DEA,
    and sell signals when DIF crosses below DEA.
    """

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def get_name(self) -> str:
        return "macd_cross"

    def get_description(self) -> str:
        return f"MACD crossover: buy when DIF crosses above DEA (fast={self.fast}, slow={self.slow}, signal={self.signal})"

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

        # Initialize signal column
        df["signal"] = 0

        # Generate crossover signals using vectorized operations
        # DIF crosses above DEA -> buy
        buy_cross = (df["dif"] > df["dea"]) & (df["dif"].shift(1) <= df["dea"].shift(1))
        # DIF crosses below DEA -> sell
        sell_cross = (df["dif"] < df["dea"]) & (df["dif"].shift(1) >= df["dea"].shift(1))
        df.loc[buy_cross, "signal"] = 1
        df.loc[sell_cross, "signal"] = -1

        return df
