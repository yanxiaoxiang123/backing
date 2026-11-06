"""Anonymous read-only public market endpoints for the landing page.

Only the fixed representative stocks and indices in
``app.services.public_market`` are reachable.  The endpoints never require a
session or API key, but are rate-limited per IP and served from a bounded
shared cache so they cannot be used as an arbitrary market-data proxy.
"""

from fastapi import APIRouter, Query, Request

from app.exceptions import ValidationError
from app.limiter import limiter
from app.services.public_market import (
    PUBLIC_INTRADAY_CODES,
    public_market_service,
)

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.get("/market")
@limiter.limit("30/minute")
def get_public_market(request: Request) -> dict:
    """Return fixed index and stock quote envelopes.

    Each section carries its own ``status`` (``ok`` / ``empty`` /
    ``unavailable``), provider, market time and cache metadata.  A partial
    provider outage degrades only that section; the request itself stays 200.
    """
    return public_market_service.get_market()


@router.get("/market/intraday")
@limiter.limit("30/minute")
def get_public_intraday(
    request: Request,
    code: str = Query(..., description="固定公开股票代码，如 sh.600519"),
) -> dict:
    """Return the real Tencent minute series for one allowlisted stock."""
    if code not in PUBLIC_INTRADAY_CODES:
        raise ValidationError(
            "Unsupported public stock code",
            error_code="invalid_symbol",
        )
    return public_market_service.get_intraday(code)
