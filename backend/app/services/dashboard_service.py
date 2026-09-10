from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import DEFAULT_USER_ID, DailyKline, Stock, WatchlistItem
from app.services.baostock_service import MAJOR_INDICES
from app.services.realtime_service import STATUS_OK, realtime_service


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_summary(self) -> Dict[str, Any]:
        """Get dashboard summary - optimized for watchlist only"""
        # First try to get watchlist from database (scoped to the current
        # single-user deployment; see DEFAULT_USER_ID)
        db_watchlist = (
            self.db.query(WatchlistItem.stock_code)
            .filter(WatchlistItem.user_id == DEFAULT_USER_ID)
            .order_by(WatchlistItem.added_at.desc())
            .all()
        )
        db_codes = [item.stock_code for item in db_watchlist]

        # Use database watchlist if not empty, otherwise fallback to env variable
        watchlist = db_codes if db_codes else settings.watchlist_stocks

        indices = self._get_major_indices()

        # Get watchlist stocks with latest prices
        watchlist_data = self._get_watchlist_data(watchlist)

        # Get trend from first watchlist stock, fallback to 300 index if no watchlist
        if watchlist_data:
            trend = self._get_stock_trend(
                stock_code=watchlist_data[0]["code"],
                stock_name=watchlist_data[0]["name"],
            )
        elif watchlist:
            trend = self._get_stock_trend(stock_code=watchlist[0])
        else:
            trend = self._get_index_trend(index_code="sh.000300")

        # Calculate stats from watchlist only
        up = sum(1 for s in watchlist_data if s["change_percent"] > 0)
        down = sum(1 for s in watchlist_data if s["change_percent"] < 0)
        flat = len(watchlist_data) - up - down

        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "market_stats": {
                "up": up,
                "down": down,
                "flat": flat,
                "total": len(watchlist_data),
            },
            "indices": indices,
            "trend": trend,
            "watchlist": watchlist_data,
            "research_queue": [
                {
                    "code": item["code"],
                    "name": item["name"],
                    "reason": "自选股异动" if item["change_percent"] >= 0 else "关注回撤",
                    "change_percent": item["change_percent"],
                    "href": f"/stocks/{item['code']}",
                }
                for item in watchlist_data[:5]
            ],
            "recent_activity": [],
            "alerts": [],
        }

    def _get_watchlist_data(self, watchlist_codes: List[str]) -> List[Dict[str, Any]]:
        """Get current watchlist quotes from the shared Mootdx service."""
        if not watchlist_codes:
            return []

        stocks = (
            self.db.query(Stock.id, Stock.code, Stock.name)
            .filter(Stock.code.in_(watchlist_codes))
            .all()
        )
        code_to_stock = {row.code: row for row in stocks}
        symbols = [str(code).split(".")[-1] for code in watchlist_codes]
        quotes = realtime_service.fetch_quotes(symbols)
        if quotes.status != STATUS_OK:
            return []
        quote_map = {str(item.get("symbol")): item for item in quotes.data}
        result: List[Dict[str, Any]] = []
        for code in watchlist_codes:
            symbol = str(code).split(".")[-1]
            quote = quote_map.get(symbol)
            stock = code_to_stock.get(code)
            if quote is None or stock is None:
                continue
            result.append(
                {
                    "id": stock.id,
                    "code": code,
                    "name": stock.name,
                    "current_price": round(float(quote["close"]), 2),
                    "high": round(float(quote["high"]), 2),
                    "low": round(float(quote["low"]), 2),
                    "volume": int(float(quote["volume"])),
                    "change": round(float(quote["change"]), 2),
                    "change_percent": round(float(quote["change_percent"]), 2),
                }
            )
        return sorted(result, key=lambda x: x["change_percent"], reverse=True)

    def _get_index_trend(self, index_code: str, days: int = 30) -> Dict[str, Any]:
        rows = (
            self.db.query(DailyKline.date, DailyKline.close)
            .filter(DailyKline.stock_code == index_code)
            .order_by(DailyKline.date.desc())
            .limit(days)
            .all()
        )
        if not rows:
            return {"name": index_code, "dates": [], "values": []}
        rows = list(reversed(rows))
        return {
            "name": next(
                (item["name"] for item in MAJOR_INDICES if item["code"] == index_code),
                index_code,
            ),
            "dates": [row.date.isoformat() for row in rows],
            "values": [round(float(row.close), 2) for row in rows],
        }

    def _get_stock_trend(self, stock_code: str, days: int = 30, stock_name: str | None = None) -> Dict[str, Any]:
        """Get trend data for a stock"""
        if stock_name is None:
            stock = self.db.query(Stock.name).filter(Stock.code == stock_code).first()
            stock_name = stock.name if stock else stock_code

        result = realtime_service.fetch_bars(str(stock_code).split(".")[-1], "daily")
        if result.status != STATUS_OK or not result.data:
            return {"name": stock_name, "dates": [], "values": []}
        rows = result.data[-days:]
        return {
            "name": f"{stock_name} ({stock_code})",
            "dates": [str(row["date"]) for row in rows],
            "values": [round(float(row["close"]), 2) for row in rows],
            "stale": result.stale,
            "cache_age_ms": result.cache_age_ms,
        }

    def _get_major_indices(self) -> List[Dict[str, Any]]:
        realtime = realtime_service.fetch_indices()
        if realtime.status == STATUS_OK:
            names = {str(item["code"]).split(".")[-1]: item["name"] for item in MAJOR_INDICES}
            return [
                {
                    "code": f"{('sh' if str(item['symbol']).startswith(('0', '6')) else 'sz')}.{item['symbol']}",
                    "name": names.get(str(item["symbol"]), str(item["symbol"])),
                    "value": round(float(item["close"]), 2),
                    "change": round(float(item["change"]), 2),
                    "change_percent": round(float(item["change_percent"]), 2),
                }
                for item in realtime.data
            ]
        return []
