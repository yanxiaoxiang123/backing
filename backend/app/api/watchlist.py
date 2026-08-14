from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_db
from app.auth import get_current_api_key
from app.models.models import DEFAULT_USER_ID, WatchlistItem, Stock
from app.schemas.schemas import (
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistListResponse,
)

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


def _current_user_id() -> int:
    """当前用户 id。

    多用户就绪：目前前端无登录态，全部请求归属默认用户（DEFAULT_USER_ID）。
    接入认证后改为从 request/session 解析用户。
    """
    return DEFAULT_USER_ID


@router.get("", response_model=WatchlistListResponse)
def get_watchlist(db: Session = Depends(get_db), _: str = Depends(get_current_api_key)):
    """Get all watchlist items with stock details"""
    items = (
        db.query(WatchlistItem)
        .join(Stock, WatchlistItem.stock_code == Stock.code)
        .filter(WatchlistItem.user_id == _current_user_id())
        .order_by(WatchlistItem.added_at.desc())
        .all()
    )

    return {
        "items": [
            {
                "id": item.id,
                "stock_code": item.stock_code,
                "stock_name": item.stock.name if item.stock else None,
                "added_at": item.added_at,
            }
            for item in items
        ],
        "total": len(items),
    }


@router.get("/codes", response_model=List[str])
def get_watchlist_codes(
    db: Session = Depends(get_db), _: str = Depends(get_current_api_key)
):
    """Get just the stock codes from watchlist"""
    items = (
        db.query(WatchlistItem.stock_code)
        .filter(WatchlistItem.user_id == _current_user_id())
        .order_by(WatchlistItem.added_at.desc())
        .all()
    )
    codes = [item.stock_code for item in items]

    # If empty, return empty list (dashboard will handle fallback)
    return codes


@router.post("", response_model=WatchlistItemResponse)
def add_to_watchlist(
    item: WatchlistItemCreate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Add a stock to watchlist"""
    # Check if stock exists
    stock = db.query(Stock).filter(Stock.code == item.stock_code).first()
    if not stock:
        raise HTTPException(
            status_code=404, detail=f"Stock {item.stock_code} not found"
        )

    # Check if already in watchlist
    existing = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.user_id == _current_user_id(),
            WatchlistItem.stock_code == item.stock_code,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail=f"Stock {item.stock_code} is already in watchlist"
        )

    # Add to watchlist
    watchlist_item = WatchlistItem(
        stock_code=item.stock_code, user_id=_current_user_id()
    )
    db.add(watchlist_item)
    db.commit()
    db.refresh(watchlist_item)

    return {
        "id": watchlist_item.id,
        "stock_code": watchlist_item.stock_code,
        "stock_name": stock.name,
        "added_at": watchlist_item.added_at,
    }


@router.delete("/{stock_code}")
def remove_from_watchlist(
    stock_code: str,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Remove a stock from watchlist"""
    item = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.user_id == _current_user_id(),
            WatchlistItem.stock_code == stock_code,
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=404, detail=f"Stock {stock_code} not in watchlist"
        )

    db.delete(item)
    db.commit()

    return {"success": True, "message": f"Removed {stock_code} from watchlist"}
