"""
Strategy Engine Module

Provides base classes and registry for quantitative trading strategies.
"""

from .base import Strategy, Parameter, ParameterType
from .registry import StrategyRegistry, register_strategy
from .factors import TechnicalFactors
from .strategies import (
    MACrossStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    BreakoutStrategy,
    RSIReversalStrategy,
    MACDCrossStrategy,
    DualThrustStrategy,
    # New classic strategies
    TurtleTradingStrategy,
    BollingerBreakoutStrategy,
    DonchianChannelStrategy,
    AberrationStrategy,
    KeltnerChannelStrategy,
    MACDHistogramDivergenceStrategy,
)

__all__ = [
    "Strategy",
    "Parameter",
    "ParameterType",
    "StrategyRegistry",
    "register_strategy",
    "TechnicalFactors",
    # Strategies
    "MACrossStrategy",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "BreakoutStrategy",
    "RSIReversalStrategy",
    "MACDCrossStrategy",
    "DualThrustStrategy",
    # New classic strategies
    "TurtleTradingStrategy",
    "BollingerBreakoutStrategy",
    "DonchianChannelStrategy",
    "AberrationStrategy",
    "KeltnerChannelStrategy",
    "MACDHistogramDivergenceStrategy",
]
