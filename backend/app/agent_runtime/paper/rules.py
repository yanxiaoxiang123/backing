"""模拟盘确定性规则（规格 v2 决策 21-22；US-3.1/3.2）。

全部为纯函数：给定订单/行情/持仓输入，输出成交决策与费用明细。
无随机、无实时行情、无外部 IO，可确定性重放（US-3.5）。

A 股规则（2023-08-28 后费率）：
- 撮合：日线粒度，审批通过后下一交易日开盘价成交（限价约束）
- T+1：当日买入份额当日不可卖
- 整手：买入必须为 100 股整数倍；卖出允许一次性清仓零股
- 一字板：开=高=低=涨跌停价时不成交（买盘在涨停、卖盘在跌停）
- 涨跌停幅度：主板 10%；创业板(300/301)/科创板(688/689) 20%；ST 5%
- 费用：佣金 0.025%（最低 5 元，双边）+ 卖出印花税 0.05% + 过户费 0.001%（双边）
- 审批一次性窗口：仅对下一个撮合窗口有效，窗口过即失效
"""

from __future__ import annotations

from dataclasses import dataclass

# A 股费用常量（2023-08-28 后费率）
COMMISSION_RATE = 0.00025  # 佣金 0.025%
MIN_COMMISSION = 5.0  # 最低佣金 5 元
STAMP_TAX_RATE = 0.0005  # 印花税 0.05%（仅卖出）
TRANSFER_FEE_RATE = 0.00001  # 过户费 0.001%（双边）

LOT_SIZE = 100  # 一手 100 股


@dataclass(frozen=True)
class Fees:
    commission: float
    stamp_tax: float
    transfer_fee: float

    @property
    def total(self) -> float:
        return round(self.commission + self.stamp_tax + self.transfer_fee, 4)


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class MatchDecision:
    fill: bool
    reason: str
    fill_price: float | None = None
    fees: Fees | None = None


def price_limit_pct(stock_code: str, stock_name: str | None = None) -> float:
    """涨跌停幅度：主板 10%；创业板/科创板 20%；ST 5%（按名称前缀识别）。"""
    name = (stock_name or "").upper()
    if "ST" in name:
        return 0.05
    code = stock_code.split(".")[-1]
    if code.startswith(("300", "301", "688", "689")):
        return 0.20
    return 0.10


def compute_fees(side: str, notional: float) -> Fees:
    """费用明细：佣金（最低 5 元）+ 卖出印花税 + 双边过户费。"""
    commission = max(notional * COMMISSION_RATE, MIN_COMMISSION)
    stamp_tax = notional * STAMP_TAX_RATE if side == "sell" else 0.0
    transfer_fee = notional * TRANSFER_FEE_RATE
    return Fees(
        commission=round(commission, 4),
        stamp_tax=round(stamp_tax, 4),
        transfer_fee=round(transfer_fee, 4),
    )


def validate_order(side: str, quantity: int) -> str | None:
    """订单合法性。返回错误信息；None 表示合法。

    买入必须为 100 股整数倍；卖出必须为正（允许一次性清仓零股）。
    """
    if quantity <= 0:
        return "数量必须为正"
    if side == "buy" and quantity % LOT_SIZE != 0:
        return f"买入数量必须为 {LOT_SIZE} 的整数倍"
    return None


def available_to_sell(position_quantity: int, bought_today_quantity: int) -> int:
    """T+1：当日买入的份额当日不可卖。"""
    return max(0, position_quantity - bought_today_quantity)


def match_order(
    *,
    side: str,
    quantity: int,
    limit_price: float | None,
    bar: Bar,
    prev_close: float,
    limit_pct: float,
) -> MatchDecision:
    """对下一交易日开盘撮合。返回成交或拒绝决策（含原因与费用）。

    - 一字板（开=高=低=涨跌停价）：买盘在涨停不成交、卖盘在跌停不成交
    - 限价约束：买单开盘价 ≤ 限价；卖单开盘价 ≥ 限价
    """
    limit_up = round(prev_close * (1 + limit_pct), 4)
    limit_down = round(prev_close * (1 - limit_pct), 4)
    one_word = bar.open == bar.high == bar.low
    if side == "buy" and one_word and bar.open >= limit_up:
        return MatchDecision(fill=False, reason="一字涨停，买单无法成交")
    if side == "sell" and one_word and bar.open <= limit_down:
        return MatchDecision(fill=False, reason="一字跌停，卖单无法成交")
    if side == "buy" and limit_price is not None and bar.open > limit_price:
        return MatchDecision(
            fill=False, reason=f"开盘价高于限价（{bar.open} > {limit_price}）"
        )
    if side == "sell" and limit_price is not None and bar.open < limit_price:
        return MatchDecision(
            fill=False, reason=f"开盘价低于限价（{bar.open} < {limit_price}）"
        )
    fill_price = round(bar.open, 4)
    notional = round(fill_price * quantity, 4)
    fees = compute_fees(side, notional)
    return MatchDecision(fill=True, reason="成交", fill_price=fill_price, fees=fees)


def window_expired(approval_date: str, trade_date: str) -> bool:
    """一次性撮合窗口：仅当 trade_date 严格晚于审批日才有效。

    窗口过后（含同日）订单过期；停牌/节假日不成交也不延长有效期。
    """
    return trade_date <= approval_date
