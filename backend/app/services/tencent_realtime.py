"""HTTPS stock and index snapshots; volumes are lots and amounts are yuan."""

import json
import math
import re
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def fetch_bars(
    symbol: str, period: str = "daily", *, count: int = 750, timeout: float = 5.0,
) -> list[dict]:
    """Read unadjusted candles. Tencent does not supply historical turnover here.

    ``amount=0`` follows the existing bar contract for unavailable turnover;
    volume is reported in lots, matching the mootdx realtime adapter.
    """
    frequency = {"daily": "day", "weekly": "week", "monthly": "month"}[period]
    code = tencent_symbol(symbol)
    query = urlencode({"param": f"{code},{frequency},,,{min(max(count, 1), 640)},"})
    request = Request(
        "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?" + query,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(2_097_153)
    if len(raw) > 2_097_152:
        raise ValueError("Tencent K-line response exceeds size limit")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise ValueError("Tencent K-line request failed")
    data = payload.get("data")
    entry = data.get(code) if isinstance(data, dict) else None
    rows = entry.get(frequency) if isinstance(entry, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Missing unadjusted Tencent K-line series")
    records = {}
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError("Malformed Tencent candle")
        date = datetime.strptime(row[0], "%Y-%m-%d").date().isoformat()
        open_, close, high, low, volume = map(float, row[1:6])
        if not all(math.isfinite(v) for v in (open_, close, high, low, volume)):
            raise ValueError("Non-finite Tencent candle")
        if min(open_, close, low) <= 0 or volume < 0 or not low <= min(open_, close) <= max(open_, close) <= high:
            raise ValueError("Invalid Tencent candle prices or volume")
        records[date] = {
            "date": date, "symbol": symbol, "open": open_, "close": close,
            "high": high, "low": low, "volume": volume, "amount": 0.0,
        }
    return [records[date] for date in sorted(records)][-count:]


def tencent_symbol(symbol: str) -> str:
    value = symbol.lower().replace(".", "")
    if re.fullmatch(r"(?:sh|sz|bj)\d{6}", value):
        return value
    if not re.fullmatch(r"\d{6}", value):
        raise ValueError("Invalid quote symbol")
    exchange = "sh" if value.startswith(("5", "6", "9")) else "sz"
    if value.startswith(("4", "8")):
        exchange = "bj"
    return exchange + value


def parse_quotes(text: str) -> dict[str, dict]:
    matches = re.findall(r'v_((?:sh|sz|bj)\d{6})="([^"\r\n]*)";', text)
    if not matches:
        raise ValueError("Unrecognised Tencent quote response")
    records = {}
    for symbol, payload in matches:
        if not payload:
            continue
        fields = payload.split("~")
        if len(fields) < 38 or fields[2] != symbol[2:]:
            raise ValueError("Malformed Tencent quote record")
        values = [float(fields[i]) for i in (3, 4, 5, 6, 31, 32, 33, 34, 37)]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Non-finite Tencent quote value")
        close, prev_close, open_, volume, change, percent, high, low, amount = values
        market_at = datetime.strptime(fields[30], "%Y%m%d%H%M%S").isoformat() + "+08:00"
        records[symbol] = {
            "name": fields[1], "close": close, "prev_close": prev_close,
            "open": open_, "high": high, "low": low, "volume": volume,
            "amount": amount * 10000, "change": change,
            "change_percent": percent, "market_at": market_at,
        }
    return records


def fetch_quotes(symbols: list[str], timeout: float = 5.0) -> list[dict]:
    records = []
    unique = list(dict.fromkeys(symbols))
    for start in range(0, len(unique), 50):
        batch = unique[start:start + 50]
        codes = [tencent_symbol(symbol) for symbol in batch]
        request = Request(
            "https://qt.gtimg.cn/q=" + ",".join(codes),
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(1_048_577)
        if len(payload) > 1_048_576:
            raise ValueError("Tencent quote response exceeds size limit")
        parsed = parse_quotes(payload.decode("gb18030"))
        for symbol, code in zip(batch, codes, strict=True):
            if code in parsed:
                records.append({**parsed[code], "symbol": symbol})
    return records
