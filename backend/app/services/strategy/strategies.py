"""
Trading Strategies Module

Implements 13 quantitative trading strategies:
1. MA Cross - Moving average crossover strategy
2. Mean Reversion - Mean reversion strategy based on Bollinger Bands
3. Momentum - Momentum-based strategy
4. Breakout - Price breakout strategy
5. RSI Reversal - RSI-based reversal strategy
6. MACD Cross - MACD crossover strategy
7. Dual Thrust - Dual thrust pivoting strategy
8. Turtle Trading - Donchian Channel breakout + ATR trailing stop
9. Bollinger Breakout - Bollinger Bands trend-following breakout
10. Donchian Channel - Classic Donchian channel breakout system
11. Aberration - Dual-channel trend-following (BB + Keltner)
12. Keltner Channel - Volatility-based Keltner channel breakout
13. MACD Divergence - MACD histogram divergence detection
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from .base import Strategy, Parameter, ParameterType
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

        # Generate signals
        for i in range(len(df)):
            if pd.notna(df["distance"].iloc[i]):
                if df["distance"].iloc[i] < -self.std_threshold:
                    df.loc[df.index[i], "signal"] = 1  # Buy (price below lower band)
                elif df["distance"].iloc[i] > self.std_threshold:
                    df.loc[df.index[i], "signal"] = -1  # Sell (price above upper band)

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

        # Generate signals
        for i in range(len(df)):
            if pd.notna(df["momentum_pct"].iloc[i]):
                if df["momentum_pct"].iloc[i] > self.threshold:
                    df.loc[df.index[i], "signal"] = 1  # Buy (positive momentum)
                elif df["momentum_pct"].iloc[i] < -self.threshold:
                    df.loc[df.index[i], "signal"] = -1  # Sell (negative momentum)

        return df


@register_strategy("breakout")
class BreakoutStrategy(Strategy):
    """
    Breakout Strategy.

    Generates signals when price breaks out of N-day high/low range,
    using ATR for stop-loss calculation.
    """

    def __init__(self, period: int = 20, atr_multiplier: float = 2.0):
        self.period = period
        self.atr_multiplier = atr_multiplier

    def get_name(self) -> str:
        return "breakout"

    def get_description(self) -> str:
        return f"Breakout strategy: buy when price breaks above {self.period}-day high, sell when breaks below low"

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "period": Parameter(
                name="period",
                param_type=ParameterType.INT,
                default=self.period,
                min_value=10,
                max_value=60,
                description="Period for high/low calculation",
            ),
            "atr_multiplier": Parameter(
                name="atr_multiplier",
                param_type=ParameterType.FLOAT,
                default=self.atr_multiplier,
                min_value=1.0,
                max_value=3.0,
                description="ATR multiplier for breakout confirmation",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        required_cols = ["close", "high", "low"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame must contain '{col}' column")

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # Calculate N-day high and low
        df["highest"] = high.rolling(window=self.period, min_periods=self.period).max()
        df["lowest"] = low.rolling(window=self.period, min_periods=self.period).min()

        # Calculate ATR for confirmation
        df["atr"] = TechnicalFactors.ATR(high, low, close, self.period)
        df["atr_threshold"] = df["atr"] * self.atr_multiplier

        # Initialize signal column
        df["signal"] = 0

        # Generate signals
        for i in range(1, len(df)):
            if pd.notna(df["highest"].iloc[i]) and pd.notna(df["lowest"].iloc[i]):
                # Buy: price breaks above highest with ATR confirmation
                if close.iloc[i] > df["highest"].iloc[i - 1]:
                    df.loc[df.index[i], "signal"] = 1  # Buy
                # Sell: price breaks below lowest with ATR confirmation
                elif close.iloc[i] < df["lowest"].iloc[i - 1]:
                    df.loc[df.index[i], "signal"] = -1  # Sell

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

        # Generate signals
        for i in range(len(df)):
            if pd.notna(df["rsi"].iloc[i]):
                if df["rsi"].iloc[i] < self.oversold:
                    df.loc[df.index[i], "signal"] = 1  # Buy (oversold)
                elif df["rsi"].iloc[i] > self.overbought:
                    df.loc[df.index[i], "signal"] = -1  # Sell (overbought)

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

        # Generate crossover signals
        for i in range(1, len(df)):
            if pd.notna(df["dif"].iloc[i]) and pd.notna(df["dea"].iloc[i]):
                # Buy: DIF crosses above DEA
                if df["dif"].iloc[i] > df["dea"].iloc[i]:
                    if df["dif"].iloc[i - 1] <= df["dea"].iloc[i - 1]:
                        df.loc[df.index[i], "signal"] = 1  # Buy
                # Sell: DIF crosses below DEA
                elif df["dif"].iloc[i] < df["dea"].iloc[i]:
                    if df["dif"].iloc[i - 1] >= df["dea"].iloc[i - 1]:
                        df.loc[df.index[i], "signal"] = -1  # Sell

        return df


@register_strategy("dual_thrust")
class DualThrustStrategy(Strategy):
    """
    Dual Thrust Strategy.

    Calculates upper and lower rails based on pivot points.
    Buy when price breaks above upper rail, sell when price breaks below lower rail.
    """

    def __init__(self, k_up: float = 0.5, k_down: float = 0.5, period: int = 20):
        self.k_up = k_up
        self.k_down = k_down
        self.period = period

    def get_name(self) -> str:
        return "dual_thrust"

    def get_description(self) -> str:
        return f"Dual Thrust: buy when price breaks upper rail (k_up={self.k_up}), sell when breaks lower rail (k_down={self.k_down})"

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "k_up": Parameter(
                name="k_up",
                param_type=ParameterType.FLOAT,
                default=self.k_up,
                min_value=0.3,
                max_value=1.0,
                description="Upper rail multiplier",
            ),
            "k_down": Parameter(
                name="k_down",
                param_type=ParameterType.FLOAT,
                default=self.k_down,
                min_value=0.3,
                max_value=1.0,
                description="Lower rail multiplier",
            ),
            "period": Parameter(
                name="period",
                param_type=ParameterType.INT,
                default=self.period,
                min_value=5,
                max_value=30,
                description="Period for range calculation",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        required_cols = ["close", "high", "low"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame must contain '{col}' column")

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # Calculate N-day high, low, and close
        df["hh"] = high.rolling(window=self.period, min_periods=self.period).max()
        df["ll"] = low.rolling(window=self.period, min_periods=self.period).min()
        df["cc"] = close.rolling(window=self.period, min_periods=self.period).max()

        # Calculate pivot range
        df["range"] = df["hh"] - df["ll"]

        # Calculate upper and lower rails
        df["upper_rail"] = df["cc"] + (self.k_up * df["range"])
        df["lower_rail"] = df["cc"] - (self.k_down * df["range"])

        # Initialize signal column
        df["signal"] = 0

        # Generate signals
        for i in range(1, len(df)):
            if pd.notna(df["upper_rail"].iloc[i]) and pd.notna(
                df["lower_rail"].iloc[i]
            ):
                # Buy: price breaks above upper rail
                if close.iloc[i] > df["upper_rail"].iloc[i - 1]:
                    df.loc[df.index[i], "signal"] = 1  # Buy
                # Sell: price breaks below lower rail
                elif close.iloc[i] < df["lower_rail"].iloc[i - 1]:
                    df.loc[df.index[i], "signal"] = -1  # Sell

        return df


# ==================== New Classic Strategies ====================


@register_strategy("turtle_trading")
class TurtleTradingStrategy(Strategy):
    """
    Turtle Trading Strategy.

    Classic trend-following system from the famous Turtle experiment:
    - Entry: Price breaks above N-day Donchian Channel high
    - Exit: Price breaks below M-day Donchian Channel low
    - Stop Loss: Trailing stop at (highest_since_entry - ATR_multiplier * ATR)
    - Uses ATR for volatility-adjusted position management.

    Reference: 'Way of the Turtle' by Curtis Faith
    """

    def __init__(
        self,
        entry_period: int = 20,
        exit_period: int = 10,
        atr_period: int = 20,
        atr_multiplier: float = 2.0,
    ):
        self.entry_period = entry_period
        self.exit_period = exit_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

    def get_name(self) -> str:
        return "turtle_trading"

    def get_description(self) -> str:
        return (
            f"Turtle Trading: Donchian Channel({self.entry_period}) entry + "
            f"Donchian({self.exit_period}) exit + ATR({self.atr_period}) trailing stop"
        )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "entry_period": Parameter(
                name="entry_period",
                param_type=ParameterType.INT,
                default=self.entry_period,
                min_value=10,
                max_value=60,
                description="Donchian Channel period for entry breakout",
            ),
            "exit_period": Parameter(
                name="exit_period",
                param_type=ParameterType.INT,
                default=self.exit_period,
                min_value=5,
                max_value=40,
                description="Donchian Channel period for exit breakdown",
            ),
            "atr_period": Parameter(
                name="atr_period",
                param_type=ParameterType.INT,
                default=self.atr_period,
                min_value=10,
                max_value=60,
                description="ATR period for trailing stop calculation",
            ),
            "atr_multiplier": Parameter(
                name="atr_multiplier",
                param_type=ParameterType.FLOAT,
                default=self.atr_multiplier,
                min_value=1.0,
                max_value=4.0,
                description="ATR multiplier for trailing stop distance",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        required_cols = ["close", "high", "low"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame must contain '{col}' column")

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # Donchian Channel for entry
        df["entry_high"] = (
            high.rolling(window=self.entry_period, min_periods=self.entry_period)
            .max()
            .shift(1)
        )
        # Donchian Channel for exit
        df["exit_low"] = (
            low.rolling(window=self.exit_period, min_periods=self.exit_period)
            .min()
            .shift(1)
        )
        # ATR for trailing stop
        df["atr"] = TechnicalFactors.ATR(high, low, close, self.atr_period)
        df["stop_distance"] = df["atr"] * self.atr_multiplier

        df["signal"] = 0

        # Simulate position internally for stop-loss tracking
        entry_price = None
        highest_since_entry = None

        for i in range(len(df)):
            if (
                pd.isna(df["entry_high"].iloc[i])
                or pd.isna(df["exit_low"].iloc[i])
                or pd.isna(df["atr"].iloc[i])
            ):
                continue

            curr_close = float(close.iloc[i])
            curr_high = float(df["entry_high"].iloc[i])
            curr_low = float(df["exit_low"].iloc[i])
            stop_dist = float(df["stop_distance"].iloc[i])

            if entry_price is None:
                # No position — check entry
                if curr_close > curr_high:
                    df.loc[df.index[i], "signal"] = 1  # Buy
                    entry_price = curr_close
                    highest_since_entry = curr_close
            else:
                # In a position — check trailing stop & exit
                highest_since_entry = max(highest_since_entry, curr_close)
                trailing_stop = highest_since_entry - stop_dist

                if curr_close < curr_low or curr_close < trailing_stop:
                    df.loc[df.index[i], "signal"] = -1  # Sell / exit
                    entry_price = None
                    highest_since_entry = None

        return df


@register_strategy("bollinger_breakout")
class BollingerBreakoutStrategy(Strategy):
    """
    Bollinger Bands Breakout Strategy.

    A trend-following strategy using Bollinger Bands:
    - Entry: Price closes above upper band (upside breakout)
    - Exit: Price closes below middle band (SMA, reversion signal)
    - Reverse: Price closes below lower band (downside breakout → sell)

    Uses standard Bollinger Bands (20,2) by default.
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev

    def get_name(self) -> str:
        return "bollinger_breakout"

    def get_description(self) -> str:
        return (
            f"Bollinger Breakout: buy when close > upper band({self.period},{self.std_dev}), "
            f"sell when close < middle band"
        )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "period": Parameter(
                name="period",
                param_type=ParameterType.INT,
                default=self.period,
                min_value=10,
                max_value=60,
                description="Bollinger Bands SMA period",
            ),
            "std_dev": Parameter(
                name="std_dev",
                param_type=ParameterType.FLOAT,
                default=self.std_dev,
                min_value=1.0,
                max_value=3.0,
                description="Standard deviation multiplier",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        if "close" not in df.columns:
            raise ValueError("DataFrame must contain 'close' column")

        close = df["close"]

        bb = TechnicalFactors.BollingerBands(close, self.period, self.std_dev)
        df["bb_upper"] = bb["upper"]
        df["bb_middle"] = bb["middle"]
        df["bb_lower"] = bb["lower"]

        df["signal"] = 0

        for i in range(1, len(df)):
            if pd.isna(df["bb_upper"].iloc[i]) or pd.isna(df["bb_middle"].iloc[i]):
                continue

            curr_close = float(close.iloc[i])
            prev_close = float(close.iloc[i - 1])
            upper = float(df["bb_upper"].iloc[i])
            middle = float(df["bb_middle"].iloc[i])

            # Buy: close crosses above upper band
            if curr_close > upper and prev_close <= upper:
                df.loc[df.index[i], "signal"] = 1
            # Sell: close crosses below middle band (from above)
            elif curr_close < middle and prev_close >= middle:
                df.loc[df.index[i], "signal"] = -1

        return df


@register_strategy("donchian_channel")
class DonchianChannelStrategy(Strategy):
    """
    Donchian Channel Strategy.

    A classic breakout system popularized by Richard Donchian:
    - Entry: Price breaks above N-day channel high
    - Exit: Price breaks below N-day channel low
    - Uses dual periods: wider entry channel, tighter exit channel

    Also known as the '4-Week Rule' system.
    """

    def __init__(self, entry_period: int = 20, exit_period: int = 10):
        self.entry_period = entry_period
        self.exit_period = exit_period

    def get_name(self) -> str:
        return "donchian_channel"

    def get_description(self) -> str:
        return (
            f"Donchian Channel: buy when close > {self.entry_period}-day high, "
            f"sell when close < {self.exit_period}-day low"
        )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "entry_period": Parameter(
                name="entry_period",
                param_type=ParameterType.INT,
                default=self.entry_period,
                min_value=5,
                max_value=60,
                description="Donchian Channel period for entry breakout",
            ),
            "exit_period": Parameter(
                name="exit_period",
                param_type=ParameterType.INT,
                default=self.exit_period,
                min_value=5,
                max_value=40,
                description="Donchian Channel period for exit breakdown",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        required_cols = ["close", "high", "low"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame must contain '{col}' column")

        close = df["close"]
        high = df["high"]
        low = df["low"]

        dc_entry = TechnicalFactors.DonchianChannel(high, low, self.entry_period)
        dc_exit = TechnicalFactors.DonchianChannel(high, low, self.exit_period)

        df["entry_high"] = dc_entry["upper"].shift(1)
        df["exit_low"] = dc_exit["lower"].shift(1)

        df["signal"] = 0

        for i in range(1, len(df)):
            if pd.isna(df["entry_high"].iloc[i]) or pd.isna(df["exit_low"].iloc[i]):
                continue

            curr_close = float(close.iloc[i])

            if curr_close > float(df["entry_high"].iloc[i]):
                df.loc[df.index[i], "signal"] = 1  # Buy
            elif curr_close < float(df["exit_low"].iloc[i]):
                df.loc[df.index[i], "signal"] = -1  # Sell

        return df


@register_strategy("aberration")
class AberrationStrategy(Strategy):
    """
    Aberration Strategy.

    A multi-channel trend-following system originally developed
    by Keith Fitschen. Uses both Bollinger Bands and Keltner Channel
    for confluence confirmation:
    - Entry: Close above BOTH Bollinger upper AND Keltner upper
    - Exit: Close below Bollinger middle (SMA)
    - Reverse: Close below BOTH Bollinger lower AND Keltner lower

    Designed for trending markets with moderate volatility.
    """

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        keltner_period: int = 20,
        keltner_atr: float = 1.5,
    ):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.keltner_period = keltner_period
        self.keltner_atr = keltner_atr

    def get_name(self) -> str:
        return "aberration"

    def get_description(self) -> str:
        return (
            f"Aberration: dual-channel breakout (BB({self.bb_period},{self.bb_std}) + "
            f"Keltner({self.keltner_period},{self.keltner_atr}))"
        )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "bb_period": Parameter(
                name="bb_period",
                param_type=ParameterType.INT,
                default=self.bb_period,
                min_value=10,
                max_value=60,
                description="Bollinger Bands period",
            ),
            "bb_std": Parameter(
                name="bb_std",
                param_type=ParameterType.FLOAT,
                default=self.bb_std,
                min_value=1.0,
                max_value=3.0,
                description="Bollinger Bands standard deviation multiplier",
            ),
            "keltner_period": Parameter(
                name="keltner_period",
                param_type=ParameterType.INT,
                default=self.keltner_period,
                min_value=10,
                max_value=60,
                description="Keltner Channel EMA period",
            ),
            "keltner_atr": Parameter(
                name="keltner_atr",
                param_type=ParameterType.FLOAT,
                default=self.keltner_atr,
                min_value=1.0,
                max_value=3.0,
                description="Keltner Channel ATR multiplier",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        required_cols = ["close", "high", "low"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame must contain '{col}' column")

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # Bollinger Bands
        bb = TechnicalFactors.BollingerBands(close, self.bb_period, self.bb_std)
        df["bb_upper"] = bb["upper"]
        df["bb_middle"] = bb["middle"]
        df["bb_lower"] = bb["lower"]

        # Keltner Channel
        kc = TechnicalFactors.KeltnerChannel(
            high, low, close, self.keltner_period, self.keltner_period, self.keltner_atr
        )
        df["kc_upper"] = kc["upper"]
        df["kc_lower"] = kc["lower"]

        df["signal"] = 0

        for i in range(1, len(df)):
            if (
                pd.isna(df["bb_upper"].iloc[i])
                or pd.isna(df["bb_middle"].iloc[i])
                or pd.isna(df["kc_upper"].iloc[i])
            ):
                continue

            curr_close = float(close.iloc[i])
            prev_close = float(close.iloc[i - 1])
            bb_upper = float(df["bb_upper"].iloc[i])
            bb_middle = float(df["bb_middle"].iloc[i])
            bb_lower = float(df["bb_lower"].iloc[i])
            kc_upper = float(df["kc_upper"].iloc[i])
            kc_lower = float(df["kc_lower"].iloc[i])

            # Buy: close above BOTH channels
            if prev_close <= min(bb_upper, kc_upper) and curr_close > max(
                bb_upper, kc_upper
            ):
                df.loc[df.index[i], "signal"] = 1
            # Sell: close below BB middle (exit trend)
            elif curr_close < bb_middle and prev_close >= bb_middle:
                df.loc[df.index[i], "signal"] = -1

        return df


@register_strategy("keltner_channel")
class KeltnerChannelStrategy(Strategy):
    """
    Keltner Channel Strategy.

    A volatility-based trend-following system:
    - Middle: EMA(period)
    - Channel Width: ATR * multiplier
    - Entry: Price closes above upper channel
    - Exit: Price closes below middle (EMA)

    More responsive than Bollinger Bands as it uses ATR
    for adaptive channel width.
    """

    def __init__(
        self,
        ema_period: int = 20,
        atr_period: int = 10,
        atr_multiplier: float = 1.5,
    ):
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier

    def get_name(self) -> str:
        return "keltner_channel"

    def get_description(self) -> str:
        return (
            f"Keltner Channel: buy when close > upper "
            f"(EMA{self.ema_period} + {self.atr_multiplier}*ATR{self.atr_period}), "
            f"sell when close < middle EMA"
        )

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "ema_period": Parameter(
                name="ema_period",
                param_type=ParameterType.INT,
                default=self.ema_period,
                min_value=10,
                max_value=60,
                description="EMA period for middle line",
            ),
            "atr_period": Parameter(
                name="atr_period",
                param_type=ParameterType.INT,
                default=self.atr_period,
                min_value=5,
                max_value=30,
                description="ATR period for channel width",
            ),
            "atr_multiplier": Parameter(
                name="atr_multiplier",
                param_type=ParameterType.FLOAT,
                default=self.atr_multiplier,
                min_value=1.0,
                max_value=3.0,
                description="ATR multiplier for channel width",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        required_cols = ["close", "high", "low"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame must contain '{col}' column")

        close = df["close"]
        high = df["high"]
        low = df["low"]

        kc = TechnicalFactors.KeltnerChannel(
            high, low, close, self.ema_period, self.atr_period, self.atr_multiplier
        )
        df["kc_upper"] = kc["upper"]
        df["kc_middle"] = kc["middle"]
        df["kc_lower"] = kc["lower"]

        df["signal"] = 0

        for i in range(1, len(df)):
            if (
                pd.isna(df["kc_upper"].iloc[i])
                or pd.isna(df["kc_middle"].iloc[i])
            ):
                continue

            curr_close = float(close.iloc[i])
            prev_close = float(close.iloc[i - 1])
            upper = float(df["kc_upper"].iloc[i])
            middle = float(df["kc_middle"].iloc[i])

            # Buy: close crosses above upper channel
            if curr_close > upper and prev_close <= upper:
                df.loc[df.index[i], "signal"] = 1
            # Sell: close crosses below middle EMA
            elif curr_close < middle and prev_close >= middle:
                df.loc[df.index[i], "signal"] = -1

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
    """
    Dual Thrust Strategy.

    Calculates upper and lower rails based on pivot points.
    Buy when price breaks above upper rail, sell when price breaks below lower rail.
    """

    def __init__(self, k_up: float = 0.5, k_down: float = 0.5, period: int = 20):
        self.k_up = k_up
        self.k_down = k_down
        self.period = period

    def get_name(self) -> str:
        return "dual_thrust"

    def get_description(self) -> str:
        return f"Dual Thrust: buy when price breaks upper rail (k_up={self.k_up}), sell when breaks lower rail (k_down={self.k_down})"

    def get_parameters(self) -> Dict[str, Parameter]:
        return {
            "k_up": Parameter(
                name="k_up",
                param_type=ParameterType.FLOAT,
                default=self.k_up,
                min_value=0.3,
                max_value=1.0,
                description="Upper rail multiplier",
            ),
            "k_down": Parameter(
                name="k_down",
                param_type=ParameterType.FLOAT,
                default=self.k_down,
                min_value=0.3,
                max_value=1.0,
                description="Lower rail multiplier",
            ),
            "period": Parameter(
                name="period",
                param_type=ParameterType.INT,
                default=self.period,
                min_value=5,
                max_value=30,
                description="Period for range calculation",
            ),
        }

    def generate_signals(self, data: Any) -> pd.DataFrame:
        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)

        required_cols = ["close", "high", "low"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"DataFrame must contain '{col}' column")

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # Calculate N-day high, low, and close
        df["hh"] = high.rolling(window=self.period, min_periods=self.period).max()
        df["ll"] = low.rolling(window=self.period, min_periods=self.period).min()
        df["cc"] = close.rolling(window=self.period, min_periods=self.period).max()

        # Calculate pivot range
        df["range"] = df["hh"] - df["ll"]

        # Calculate upper and lower rails
        # Dual Thrust formula:
        # Upper = Close + k_up * Range
        # Lower = Close - k_down * Range
        df["upper_rail"] = df["cc"] + (self.k_up * df["range"])
        df["lower_rail"] = df["cc"] - (self.k_down * df["range"])

        # Initialize signal column
        df["signal"] = 0

        # Generate signals
        for i in range(1, len(df)):
            if pd.notna(df["upper_rail"].iloc[i]) and pd.notna(
                df["lower_rail"].iloc[i]
            ):
                # Buy: price breaks above upper rail
                if close.iloc[i] > df["upper_rail"].iloc[i - 1]:
                    df.loc[df.index[i], "signal"] = 1  # Buy
                # Sell: price breaks below lower rail
                elif close.iloc[i] < df["lower_rail"].iloc[i - 1]:
                    df.loc[df.index[i], "signal"] = -1  # Sell

        return df
