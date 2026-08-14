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

from .breakout import (
    AberrationStrategy,
    BollingerBreakoutStrategy,
    BreakoutStrategy,
    DonchianChannelStrategy,
    DualThrustStrategy,
    KeltnerChannelStrategy,
    TurtleTradingStrategy,
)
from .reversal import (
    MACDHistogramDivergenceStrategy,
    MeanReversionStrategy,
    RSIReversalStrategy,
)
from .trend import MACDCrossStrategy, MACrossStrategy, MomentumStrategy

__all__ = [
    "AberrationStrategy",
    "BollingerBreakoutStrategy",
    "BreakoutStrategy",
    "DonchianChannelStrategy",
    "DualThrustStrategy",
    "KeltnerChannelStrategy",
    "MACDCrossStrategy",
    "MACDHistogramDivergenceStrategy",
    "MACrossStrategy",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "RSIReversalStrategy",
    "TurtleTradingStrategy",
]
