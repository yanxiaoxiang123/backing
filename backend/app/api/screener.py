"""Stock screener / scanner API.

Supports multi-condition screening with AND/OR logic across:
- RSI thresholds
- MACD crossover (golden/death cross)
- Volume breakout (vs. N-day average)
- Bollinger Band squeeze (bandwidth threshold)
- MA crossover (short MA crosses above/below long MA)
- Price change percent
"""

import logging
from datetime import date, timedelta
from typing import Optional, List, Dict

import pandas as pd
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_api_key
from app.config import get_db
from app.limiter import limiter
from app.models.models import Stock, DailyKline
from app.services.strategy.factors import TechnicalFactors

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------------

SUPPORTED_INDICATORS = {
    "rsi": {
        "label": "RSI 相对强弱",
        "params": {"period": 14},
        "default_op": "lt",
    },
    "macd_golden_cross": {
        "label": "MACD 金叉",
        "params": {"fast": 12, "slow": 26, "signal": 9},
        "default_op": "cross_above",
    },
    "macd_death_cross": {
        "label": "MACD 死叉",
        "params": {"fast": 12, "slow": 26, "signal": 9},
        "default_op": "cross_below",
    },
    "volume_ratio": {
        "label": "成交量放量",
        "params": {"period": 20},
        "default_op": "gt",
    },
    "bollinger_bandwidth": {
        "label": "布林带宽",
        "params": {"period": 20, "std_dev": 2.0},
        "default_op": "lt",
    },
    "ma_golden_cross": {
        "label": "均线金叉",
        "params": {"short": 5, "long": 20},
        "default_op": "cross_above",
    },
    "ma_death_cross": {
        "label": "均线死叉",
        "params": {"short": 5, "long": 20},
        "default_op": "cross_below",
    },
    "price_change": {
        "label": "涨跌幅",
        "params": {"days": 1},
        "default_op": "gt",
    },
    "close_above_ma": {
        "label": "收盘价站上均线",
        "params": {"period": 20},
        "default_op": "cross_above",
    },
}


class ScreenerCondition(BaseModel):
    indicator: str = Field(description="Indicator key, e.g. rsi, macd_golden_cross")
    operator: str = Field("lt", description="lt/gt/lte/gte/eq/cross_above/cross_below")
    value: float = Field(0, description="Threshold value")
    params: Dict[str, int] = Field(
        default_factory=dict,
        description="Indicator-specific parameters",
    )

    def effective_params(self) -> dict:
        defaults = SUPPORTED_INDICATORS.get(self.indicator, {}).get("params", {})
        merged = {**defaults, **self.params}
        return merged


class ScreenerRequest(BaseModel):
    conditions: List[ScreenerCondition] = Field(min_length=1, max_length=10)
    logic: str = Field("AND", description="AND or OR")
    market: Optional[str] = Field(None, description="Filter by market (sh/sz/bj)")
    max_results: int = Field(100, ge=1, le=500, description="Max results to return")


class ScreenerResultItem(BaseModel):
    stock_code: str
    stock_name: str
    close: float
    volume: int
    change_pct: Optional[float] = None
    indicators: Dict[str, Optional[float]] = {}
    matched_conditions: List[str] = []


class ScreenerResponse(BaseModel):
    success: bool
    total_stocks_scanned: int
    total_matched: int
    conditions_used: List[str]
    logic: str
    results: List[ScreenerResultItem] = []
    execution_time_s: float = 0


# ---------------------------------------------------------------------------
# indicator computation helpers
# ---------------------------------------------------------------------------


def _compute_indicators(
    df: pd.DataFrame, conditions: List[ScreenerCondition]
) -> Dict[str, Optional[float]]:
    """Compute all requested indicator values for the latest bar.

    Returns a dict with the latest value for each indicator.  Crossover
    indicators return ``True`` as a float (1.0 / 0.0) at the
    ``matched_conditions`` layer.
    """
    values: Dict[str, Optional[float]] = {}
    if df.empty or len(df) < 5:
        return values

    close = df["close"]
    volume = df["volume"]

    for cond in conditions:
        indicator = cond.indicator
        params = cond.effective_params()

        try:
            if indicator == "rsi":
                period = params.get("period", 14)
                rsi = TechnicalFactors.RSI(close, period)
                values["rsi"] = (
                    float(rsi.iloc[-1])
                    if not rsi.empty and pd.notna(rsi.iloc[-1])
                    else None
                )

            elif indicator in ("macd_golden_cross", "macd_death_cross"):
                fast = params.get("fast", 12)
                slow = params.get("slow", 26)
                signal = params.get("signal", 9)
                macd = TechnicalFactors.MACD(close, fast, slow, signal)
                dif = macd["dif"]
                dea = macd["dea"]
                if len(dif) >= 2 and len(dea) >= 2:
                    values["macd_dif"] = (
                        float(dif.iloc[-1]) if pd.notna(dif.iloc[-1]) else None
                    )
                    values["macd_dea"] = (
                        float(dea.iloc[-1]) if pd.notna(dea.iloc[-1]) else None
                    )
                    prev_dif, cur_dif = dif.iloc[-2], dif.iloc[-1]
                    prev_dea, cur_dea = dea.iloc[-2], dea.iloc[-1]
                    if (
                        pd.notna(prev_dif)
                        and pd.notna(cur_dif)
                        and pd.notna(prev_dea)
                        and pd.notna(cur_dea)
                    ):
                        values["macd_cross_up"] = (
                            1.0 if (prev_dif <= prev_dea and cur_dif > cur_dea) else 0.0
                        )
                        values["macd_cross_down"] = (
                            1.0 if (prev_dif >= prev_dea and cur_dif < cur_dea) else 0.0
                        )

            elif indicator == "volume_ratio":
                period = params.get("period", 20)
                vol_ma = TechnicalFactors.VolumeMA(volume, period)
                if (
                    len(vol_ma) >= 1
                    and vol_ma.iloc[-1] > 0
                    and pd.notna(vol_ma.iloc[-1])
                ):
                    values["volume_ratio"] = float(volume.iloc[-1] / vol_ma.iloc[-1])

            elif indicator == "bollinger_bandwidth":
                period = params.get("period", 20)
                std_dev = params.get("std_dev", 2.0)
                bb = TechnicalFactors.BollingerBands(close, period, std_dev)
                bw = bb["bandwidth"]
                if len(bw) >= 1 and pd.notna(bw.iloc[-1]):
                    values["bollinger_bandwidth"] = float(bw.iloc[-1])
                    values["bollinger_upper"] = (
                        float(bb["upper"].iloc[-1])
                        if pd.notna(bb["upper"].iloc[-1])
                        else None
                    )
                    values["bollinger_lower"] = (
                        float(bb["lower"].iloc[-1])
                        if pd.notna(bb["lower"].iloc[-1])
                        else None
                    )

            elif indicator in ("ma_golden_cross", "ma_death_cross"):
                short_p = params.get("short", 5)
                long_p = params.get("long", 20)
                ma_s = TechnicalFactors.SMA(close, short_p)
                ma_l = TechnicalFactors.SMA(close, long_p)
                if len(ma_s) >= 2 and len(ma_l) >= 2:
                    values["ma_short"] = (
                        float(ma_s.iloc[-1]) if pd.notna(ma_s.iloc[-1]) else None
                    )
                    values["ma_long"] = (
                        float(ma_l.iloc[-1]) if pd.notna(ma_l.iloc[-1]) else None
                    )
                    prev_s, cur_s = ma_s.iloc[-2], ma_s.iloc[-1]
                    prev_l, cur_l = ma_l.iloc[-2], ma_l.iloc[-1]
                    if all(pd.notna(x) for x in (prev_s, cur_s, prev_l, cur_l)):
                        values["ma_cross_up"] = (
                            1.0 if (prev_s <= prev_l and cur_s > cur_l) else 0.0
                        )
                        values["ma_cross_down"] = (
                            1.0 if (prev_s >= prev_l and cur_s < cur_l) else 0.0
                        )

            elif indicator == "price_change":
                days = params.get("days", 1)
                if len(close) > days:
                    prev = close.iloc[-(days + 1)]
                    cur = close.iloc[-1]
                    if prev > 0:
                        values["price_change"] = float((cur - prev) / prev * 100)

            elif indicator == "close_above_ma":
                period = params.get("period", 20)
                ma = TechnicalFactors.SMA(close, period)
                if len(ma) >= 2 and pd.notna(ma.iloc[-1]):
                    values["ma"] = float(ma.iloc[-1])
                    values["close_to_ma"] = (
                        float(close.iloc[-1] / ma.iloc[-1] - 1) * 100
                    )
                    prev_c = close.iloc[-2]
                    prev_ma = ma.iloc[-2]
                    cur_c = close.iloc[-1]
                    cur_ma = ma.iloc[-1]
                    if all(pd.notna(x) for x in (prev_c, prev_ma, cur_c, cur_ma)):
                        values["close_cross_above_ma"] = (
                            1.0 if (prev_c <= prev_ma and cur_c > cur_ma) else 0.0
                        )

        except Exception:
            logger.debug(
                "Indicator computation failed for %s", indicator, exc_info=True
            )

    return values


def _check_condition(value: Optional[float], operator: str, threshold: float) -> bool:
    """Evaluate a single condition against a computed value."""
    if value is None:
        return False

    try:
        if operator == "lt":
            return value < threshold
        if operator == "gt":
            return value > threshold
        if operator == "lte":
            return value <= threshold
        if operator == "gte":
            return value >= threshold
        if operator == "eq":
            return abs(value - threshold) < 0.0001
        if operator == "cross_above":
            return value > 0.5  # 1.0 = cross happened
        if operator == "cross_below":
            return value > 0.5
    except (TypeError, ValueError):
        return False

    return False


def _value_key_for_indicator(indicator: str) -> str:
    """Map an indicator name to the dict key that holds its computed value."""
    mapping = {
        "rsi": "rsi",
        "macd_golden_cross": "macd_cross_up",
        "macd_death_cross": "macd_cross_down",
        "volume_ratio": "volume_ratio",
        "bollinger_bandwidth": "bollinger_bandwidth",
        "ma_golden_cross": "ma_cross_up",
        "ma_death_cross": "ma_cross_down",
        "price_change": "price_change",
        "close_above_ma": "close_cross_above_ma",
    }
    return mapping.get(indicator, indicator)


# ---------------------------------------------------------------------------
# endpoint
# ---------------------------------------------------------------------------


@router.post("/screener", response_model=ScreenerResponse)
@limiter.limit("5/minute")
def run_screener(
    request: Request,
    response: Response,
    req: ScreenerRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_api_key),
):
    """Run a stock screener with the given conditions."""
    import time

    t0 = time.monotonic()

    # validate conditions
    for cond in req.conditions:
        if cond.indicator not in SUPPORTED_INDICATORS:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail=f"Unsupported indicator: {cond.indicator}. "
                f"Supported: {list(SUPPORTED_INDICATORS)}",
            )

    logic_and = req.logic.upper() == "AND"
    condition_labels = [
        SUPPORTED_INDICATORS[c.indicator]["label"] for c in req.conditions
    ]

    # load stocks (with optional market filter)
    stock_query = db.query(Stock)
    if req.market:
        stock_query = stock_query.filter(Stock.market == req.market)
    stocks = stock_query.order_by(Stock.code).all()

    total_scanned = 0
    matched: List[ScreenerResultItem] = []

    # pre-load lookback period: need enough bars for the longest indicator param
    max_lookback = 120  # generous default
    end_date_obj = date.today()
    start_date_obj = end_date_obj - timedelta(days=max_lookback + 10)

    for stock in stocks:
        if len(matched) >= req.max_results:
            break

        klines = (
            db.query(DailyKline)
            .filter(
                DailyKline.stock_code == stock.code,
                DailyKline.date >= start_date_obj,
                DailyKline.date <= end_date_obj,
            )
            .order_by(DailyKline.date)
            .all()
        )

        if len(klines) < 20:
            continue

        total_scanned += 1

        df = pd.DataFrame(
            [
                {
                    "date": k.date,
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "volume": k.volume,
                }
                for k in klines
            ]
        )

        indicators = _compute_indicators(df, req.conditions)
        if not indicators:
            continue

        # evaluate conditions
        matched_conds: List[str] = []
        for cond in req.conditions:
            key = _value_key_for_indicator(cond.indicator)
            val = indicators.get(key)
            if _check_condition(val, cond.operator, cond.value):
                matched_conds.append(cond.indicator)

        if logic_and:
            ok = len(matched_conds) == len(req.conditions)
        else:
            ok = len(matched_conds) > 0

        if not ok:
            continue

        # compute price change for display
        change_pct = None
        if len(df) >= 2:
            prev = df["close"].iloc[-2]
            cur = df["close"].iloc[-1]
            if prev > 0:
                change_pct = round((cur - prev) / prev * 100, 2)

        # pick display-safe indicator values
        display_indicators: Dict[str, Optional[float]] = {}
        for cond in req.conditions:
            key = _value_key_for_indicator(cond.indicator)
            display_indicators[cond.indicator] = (
                round(indicators[key], 2) if indicators.get(key) is not None else None
            )

        matched.append(
            ScreenerResultItem(
                stock_code=stock.code,
                stock_name=stock.name,
                close=round(df["close"].iloc[-1], 2),
                volume=int(df["volume"].iloc[-1]),
                change_pct=change_pct,
                indicators=display_indicators,
                matched_conditions=matched_conds,
            )
        )

    elapsed = round(time.monotonic() - t0, 2)
    return ScreenerResponse(
        success=True,
        total_stocks_scanned=total_scanned,
        total_matched=len(matched),
        conditions_used=condition_labels,
        logic=req.logic.upper(),
        results=matched,
        execution_time_s=elapsed,
    )
