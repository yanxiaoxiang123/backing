"""
Strategy Engine Module

Provides base classes and registry for quantitative trading strategies.
"""

from .base import Parameter, ParameterType, Strategy
from .factors import TechnicalFactors
from .registry import StrategyRegistry, register_strategy
from .strategies import (
    AberrationStrategy,
    BollingerBreakoutStrategy,
    BreakoutStrategy,
    DonchianChannelStrategy,
    DualThrustStrategy,
    KeltnerChannelStrategy,
    MACDCrossStrategy,
    MACDHistogramDivergenceStrategy,
    MACrossStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    RSIReversalStrategy,
    # New classic strategies
    TurtleTradingStrategy,
)

__all__ = [
    "AberrationStrategy",
    "BollingerBreakoutStrategy",
    "BreakoutStrategy",
    "DonchianChannelStrategy",
    "DualThrustStrategy",
    "KeltnerChannelStrategy",
    "MACDCrossStrategy",
    "MACDHistogramDivergenceStrategy",
    # Strategies
    "MACrossStrategy",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "Parameter",
    "ParameterType",
    "RSIReversalStrategy",
    "Strategy",
    "StrategyRegistry",
    "TechnicalFactors",
    # New classic strategies
    "TurtleTradingStrategy",
    "register_strategy",
]
