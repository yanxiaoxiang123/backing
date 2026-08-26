from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import DEFAULT_USER_ID, DailyKline, Stock, WatchlistItem
from app.services.baostock_service import MAJOR_INDICES


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
        """Get latest price data for watchlist stocks only - single query with window functions"""
        if not watchlist_codes:
            return []

        # Use window functions to get latest and previous in one query
        ranked_subquery = (
            self.db.query(
                DailyKline.stock_code,
                DailyKline.date,
                DailyKline.close,
                DailyKline.high,
                DailyKline.low,
                DailyKline.volume,
                func.dense_rank().over(
                    partition_by=DailyKline.stock_code,
                    order_by=DailyKline.date.desc()
                ).label("dr")
            )
            .filter(DailyKline.stock_code.in_(watchlist_codes))
            .subquery()
        )

        rows = (
            self.db.query(
                Stock.id,
                Stock.code,
                Stock.name,
                func.max(
                    case(
                        (ranked_subquery.c.dr == 1, ranked_subquery.c.close),
                        else_=None
                    )
                ).label("latest_close"),
                func.max(
                    case(
                        (ranked_subquery.c.dr == 1, ranked_subquery.c.high),
                        else_=None
                    )
                ).label("latest_high"),
                func.max(
                    case(
                        (ranked_subquery.c.dr == 1, ranked_subquery.c.low),
                        else_=None
                    )
                ).label("latest_low"),
                func.max(
                    case(
                        (ranked_subquery.c.dr == 1, ranked_subquery.c.volume),
                        else_=None
                    )
                ).label("latest_volume"),
                func.max(
                    case(
                        (ranked_subquery.c.dr == 2, ranked_subquery.c.close),
                        else_=None
                    )
                ).label("previous_close"),
            )
            .join(ranked_subquery, ranked_subquery.c.stock_code == Stock.code)
            .filter(Stock.code.in_(watchlist_codes))
            .group_by(Stock.id, Stock.code, Stock.name)
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

    def _get_stock_trend(self, stock_code: str, days: int = 30, stock_name: str | None = None) -> Dict[str, Any]:
        """Get trend data for a stock"""
        if stock_name is None:
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

        ranked = (
            self.db.query(
                DailyKline.stock_code,
                DailyKline.close,
                func.dense_rank()
                .over(partition_by=DailyKline.stock_code, order_by=DailyKline.date.desc())
                .label("dr"),
            )
            .filter(DailyKline.stock_code.in_(target_codes))
            .subquery()
        )

        rows = (
            self.db.query(
                ranked.c.stock_code.label("code"),
                func.max(
                    case((ranked.c.dr == 1, ranked.c.close), else_=None)
                ).label("latest_close"),
                func.max(
                    case((ranked.c.dr == 2, ranked.c.close), else_=None)
                ).label("previous_close"),
            )
            .filter(ranked.c.dr.in_([1, 2]))
            .group_by(ranked.c.stock_code)
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
