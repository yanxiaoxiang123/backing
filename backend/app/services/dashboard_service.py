from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.models.models import DailyKline, Stock, WatchlistItem
from app.services.baostock_service import MAJOR_INDICES


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_summary(self) -> Dict[str, Any]:
        """Get dashboard summary - optimized for watchlist only"""
        # First try to get watchlist from database
        db_watchlist = (
            self.db.query(WatchlistItem.stock_code)
            .order_by(WatchlistItem.added_at.desc())
            .all()
        )
        db_codes = [item.stock_code for item in db_watchlist]

        # Use database watchlist if not empty, otherwise fallback to env variable
        watchlist = db_codes if db_codes else settings.watchlist_stocks

        # Get trend from first watchlist stock, fallback to 300 index if no watchlist
        if watchlist:
            first_stock = watchlist[0]
            trend = self._get_stock_trend(stock_code=first_stock)
        else:
            trend = self._get_index_trend(index_code="sh.000300")

        indices = self._get_major_indices()

        # Get watchlist stocks with latest prices
        watchlist_data = self._get_watchlist_data(watchlist)

        # Calculate stats from watchlist only
        up = sum(1 for s in watchlist_data if s["change_percent"] > 0)
        down = sum(1 for s in watchlist_data if s["change_percent"] < 0)
        flat = len(watchlist_data) - up - down

        return {
            "market_stats": {
                "up": up,
                "down": down,
                "flat": flat,
                "total": len(watchlist_data),
            },
            "indices": indices,
            "trend": trend,
            "watchlist": watchlist_data,
        }

    def _get_watchlist_data(self, watchlist_codes: List[str]) -> List[Dict[str, Any]]:
        """Get latest price data for watchlist stocks only"""
        if not watchlist_codes:
            return []

        # Get the latest date that exists for ANY watchlist stock
        latest_date = (
            self.db.query(func.max(DailyKline.date))
            .filter(DailyKline.stock_code.in_(watchlist_codes))
            .scalar()
        )
        if latest_date is None:
            return []

        previous_date = (
            self.db.query(func.max(DailyKline.date))
            .filter(DailyKline.stock_code.in_(watchlist_codes))
            .filter(DailyKline.date < latest_date)
            .scalar()
        )

        # Query watchlist stocks only
        latest = aliased(DailyKline)
        previous = aliased(DailyKline)

        rows = (
            self.db.query(
                Stock.id,
                Stock.code,
                Stock.name,
                latest.close.label("latest_close"),
                latest.high.label("latest_high"),
                latest.low.label("latest_low"),
                latest.volume.label("latest_volume"),
                previous.close.label("previous_close"),
            )
            .join(
                latest,
                (latest.stock_code == Stock.code) & (latest.date == latest_date),
            )
            .outerjoin(
                previous,
                (previous.stock_code == Stock.code) & (previous.date == previous_date),
            )
            .filter(Stock.code.in_(watchlist_codes))
            .all()
        )

        result: List[Dict[str, Any]] = []
        for row in rows:
            previous_close = row.previous_close or row.latest_close
            if not previous_close or not row.latest_close:
                continue
            change = row.latest_close - previous_close
            change_percent = (change / previous_close) * 100 if previous_close else 0
            result.append(
                {
                    "id": row.id,
                    "code": row.code,
                    "name": row.name,
                    "current_price": round(row.latest_close, 2),
                    "high": round(row.latest_high, 2),
                    "low": round(row.latest_low, 2),
                    "volume": int(row.latest_volume),
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                }
            )

        # Sort by change_percent descending
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

    def _get_stock_trend(self, stock_code: str, days: int = 30) -> Dict[str, Any]:
        """Get trend data for a stock"""
        # Get stock name
        stock = self.db.query(Stock.name).filter(Stock.code == stock_code).first()
        stock_name = stock.name if stock else stock_code

        rows = (
            self.db.query(DailyKline.date, DailyKline.close)
            .filter(DailyKline.stock_code == stock_code)
            .order_by(DailyKline.date.desc())
            .limit(days)
            .all()
        )
        if not rows:
            return {"name": stock_name, "dates": [], "values": []}
        rows = list(reversed(rows))
        return {
            "name": f"{stock_name} ({stock_code})",
            "dates": [row.date.isoformat() for row in rows],
            "values": [round(float(row.close), 2) for row in rows],
        }

    def _get_major_indices(self) -> List[Dict[str, Any]]:
        target_codes = [item["code"] for item in MAJOR_INDICES[:3]]
        latest_subquery = (
            self.db.query(
                DailyKline.stock_code.label("stock_code"),
                func.max(DailyKline.date).label("latest_date"),
            )
            .filter(DailyKline.stock_code.in_(target_codes))
            .group_by(DailyKline.stock_code)
            .subquery()
        )

        latest = aliased(DailyKline)
        previous = aliased(DailyKline)
        previous_subquery = (
            self.db.query(
                DailyKline.stock_code.label("stock_code"),
                func.max(DailyKline.date).label("previous_date"),
            )
            .join(
                latest_subquery,
                (DailyKline.stock_code == latest_subquery.c.stock_code)
                & (DailyKline.date < latest_subquery.c.latest_date),
            )
            .group_by(DailyKline.stock_code)
            .subquery()
        )

        rows = (
            self.db.query(
                latest.stock_code.label("code"),
                latest.close.label("latest_close"),
                previous.close.label("previous_close"),
            )
            .join(
                latest_subquery,
                (latest.stock_code == latest_subquery.c.stock_code)
                & (latest.date == latest_subquery.c.latest_date),
            )
            .outerjoin(
                previous_subquery, latest.stock_code == previous_subquery.c.stock_code
            )
            .outerjoin(
                previous,
                (previous.stock_code == previous_subquery.c.stock_code)
                & (previous.date == previous_subquery.c.previous_date),
            )
            .all()
        )
        data_map = {row.code: row for row in rows}
        results: List[Dict[str, Any]] = []

        for item in MAJOR_INDICES[:3]:
            row = data_map.get(item["code"])
            if row is None:
                results.append(
                    {
                        "code": item["code"],
                        "name": item["name"],
                        "value": 0,
                        "change": 0,
                        "change_percent": 0,
                    }
                )
                continue

            latest_close = float(row.latest_close or 0)
            previous_close = float(row.previous_close or row.latest_close or 0)
            if previous_close == 0:
                previous_close = latest_close or 1
            change = latest_close - previous_close
            change_percent = (change / previous_close) * 100 if previous_close else 0
            results.append(
                {
                    "code": item["code"],
                    "name": item["name"],
                    "value": round(latest_close, 2),
                    "change": round(change, 2),
                    "change_percent": round(change_percent, 2),
                }
            )

        return results
