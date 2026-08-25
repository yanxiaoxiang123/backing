from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from app.services.screener_service import completed_daily_bars

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _bars(latest_volume: float = 2000) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-08-24",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
            },
            {
                "date": "2026-08-25",
                "open": 10.5,
                "high": 11.2,
                "low": 10.4,
                "close": 11,
                "volume": latest_volume,
            },
        ]
    )


def test_drops_todays_daily_bar_before_market_close():
    result = completed_daily_bars(
        _bars(), now=datetime(2026, 8, 25, 9, 15, tzinfo=SHANGHAI)
    )
    assert result["date"].tolist() == ["2026-08-24"]


def test_keeps_complete_daily_bar_after_market_close():
    result = completed_daily_bars(
        _bars(), now=datetime(2026, 8, 25, 15, 5, tzinfo=SHANGHAI)
    )
    assert result["date"].tolist() == ["2026-08-24", "2026-08-25"]


def test_drops_mootdx_placeholder_even_after_market_close():
    result = completed_daily_bars(
        _bars(5.877471754111438e-39),
        now=datetime(2026, 8, 25, 15, 5, tzinfo=SHANGHAI),
    )
    assert result["date"].tolist() == ["2026-08-24"]


def test_timezone_conversion_uses_shanghai_market_time():
    result = completed_daily_bars(
        _bars(), now=datetime(2026, 8, 25, 7, 30, tzinfo=ZoneInfo("UTC"))
    )
    assert result["date"].tolist() == ["2026-08-24", "2026-08-25"]
