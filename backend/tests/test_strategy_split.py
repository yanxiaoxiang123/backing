"""策略族拆分回归测试：拆分后注册表、re-export、各模块导入均正常。"""

import app.services.strategy  # noqa: F401  (register all strategies)
from app.services.strategy.registry import StrategyRegistry


EXPECTED = {
    # trend
    "ma_cross",
    "momentum",
    "macd_cross",
    # reversal
    "mean_reversion",
    "rsi_reversal",
    "macd_divergence",
    # breakout
    "breakout",
    "dual_thrust",
    "turtle_trading",
    "bollinger_breakout",
    "donchian_channel",
    "aberration",
    "keltner_channel",
}


class TestStrategySplit:
    def test_all_13_strategies_registered(self):
        registered = set(StrategyRegistry.list_strategies())
        assert registered == EXPECTED

    def test_hub_reexports_all_families(self):
        from app.services.strategy.strategies import (  # noqa: F401
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
            TurtleTradingStrategy,
        )

    def test_family_modules_importable(self):
        from app.services.strategy import breakout, reversal, trend  # noqa: F401

    def test_each_strategy_instantiates_and_generates_signal_column(self):
        import pandas as pd

        df = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=60),
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.0,
                "volume": 100000,
            }
        )
        for name, cls in StrategyRegistry.get_all().items():
            strategy = cls()
            out = strategy.generate_signals(df.copy())
            assert "signal" in out.columns, f"{name} missing signal column"
