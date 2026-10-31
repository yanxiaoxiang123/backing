"""Baostock adapter for raw history, calendars and metadata (no generated data)."""

from datetime import date
from functools import lru_cache

import baostock as bs

from app.services.baostock_rpc import market_data_rpc, records as _records  # noqa: F401


class BaostockMarketDataProvider:
    name = "baostock"

    def _query(self, function, *args, **kwargs) -> list[dict]:
        return market_data_rpc.query(function.__name__, *args, **kwargs)

    def calendar(self, start: date, end: date) -> list[dict]:
        rows = self._query(bs.query_trade_dates, start_date=start.isoformat(), end_date=end.isoformat())
        return [{"date": row["calendar_date"], "is_open": row["is_trading_day"] == "1"} for row in rows]

    def securities(self) -> list[dict]:
        rows = self._query(bs.query_stock_basic)
        return [{"stock_code": row["code"], "name": row["code_name"],
                 "listed_on": row.get("ipoDate") or None, "delisted_on": row.get("outDate") or None,
                 "status": "listed" if row["status"] == "1" else "delisted"}
                for row in rows if row.get("type") == "1"]

    def bars(self, code: str, start: date, end: date) -> list[dict]:
        rows = self._query(bs.query_history_k_data_plus, code,
                           "date,open,high,low,close,volume,amount,tradestatus,isST",
                           start_date=start.isoformat(), end_date=end.isoformat(),
                           frequency="d", adjustflag="3")
        # Suspended rows may carry no OHLC. Keep absence visible as a gap until
        # explicit status data is present; do not invent a zero-priced candle.
        return [{**row, "suspended": row["tradestatus"] == "0", "is_st": row["isST"] == "1"}
                for row in rows if all(row.get(key) for key in ("open", "high", "low", "close", "volume"))]

    def factors(self, code: str, start: date, end: date) -> list[dict]:
        return self._query(bs.query_adjust_factor, code, start_date=start.isoformat(), end_date=end.isoformat())

    @lru_cache(maxsize=16)
    def session_statuses(self, day: date) -> tuple[dict, ...]:
        rows = self._query(bs.query_all_stock, day=day.isoformat())
        return tuple({"stock_code": row["code"], "date": day,
                      "suspended": row["tradeStatus"] == "0"}
                     for row in rows if row.get("tradeStatus") in {"0", "1"})

    def dividends(self, code: str, year: int) -> list[dict]:
        return self._query(bs.query_dividend_data, code, year=str(year), yearType="operate")
