"""Corporate-action entitlements, receivables and share availability for research."""

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from fractions import Fraction
from math import isfinite

from app.services.market_data import as_date, digest, number


@dataclass(frozen=True)
class EconomicAction:
    action_id: str
    record_date: date
    ex_date: date
    cash_per_share: float = 0
    bonus_ratio: float = 0
    cash_date: date | None = None
    stock_date: date | None = None

    def __post_init__(self):
        if self.record_date >= self.ex_date:
            raise ValueError("Corporate action requires a record date before its ex-date")
        if any(not isfinite(value) or value < 0 for value in (self.cash_per_share, self.bonus_ratio)):
            raise ValueError("Corporate action amounts must be finite and nonnegative")
        if self.cash_per_share and (self.cash_date is None or self.cash_date < self.ex_date):
            raise ValueError("Cash dividend requires a verified payment date on/after ex-date")
        if self.bonus_ratio and (self.stock_date is None or self.stock_date < self.ex_date):
            raise ValueError("Bonus shares require a verified listing date on/after ex-date")

    def snapshot(self) -> dict:
        return {key: value.isoformat() if isinstance(value, date) else value
                for key, value in asdict(self).items()}

    @classmethod
    def from_snapshot(cls, row: dict):
        return cls(**{key: as_date(value) if key.endswith("date") and value else value
                      for key, value in row.items()})


def normalize_dividends(rows: list[dict]) -> list[EconomicAction]:
    actions = {}
    for row in rows:
        ex_date = as_date(row["dividOperateDate"])
        # A proposed plan is insufficient evidence for the implemented distribution.
        publication = row.get("dividPlanDate")
        if not publication or as_date(publication) + timedelta(days=1) > ex_date:
            raise ValueError("Implemented dividend lacks timely implementation-announcement evidence")
        if not row.get("dividRegistDate"):
            raise ValueError("Dividend record date is missing")
        action = EconomicAction(
            action_id=digest(row), record_date=as_date(row["dividRegistDate"]), ex_date=ex_date,
            cash_per_share=float(number(row.get("dividCashPsBeforeTax") or 0)),
            bonus_ratio=float(number(row.get("dividStocksPs") or 0)
                              + number(row.get("dividReserveToStockPs") or 0)),
            cash_date=as_date(row["dividPayDate"]) if row.get("dividPayDate") else None,
            stock_date=as_date(row["dividStockMarketDate"]) if row.get("dividStockMarketDate") else None,
        )
        if ex_date in actions and actions[ex_date] != action:
            raise ValueError("Conflicting corporate-action records for the same ex-date")
        actions[ex_date] = action
    return sorted(actions.values(), key=lambda action: action.ex_date)


class CorporateActionLedger:
    def __init__(self, actions: list[EconomicAction], sessions: list[date], tax_rate: float = 0):
        if not isfinite(tax_rate) or not 0 <= tax_rate <= 1:
            raise ValueError("Dividend tax research assumption must be in [0,1]")
        if len({action.action_id for action in actions}) != len(actions):
            raise ValueError("Duplicate corporate action IDs")
        if any(sessions[0] <= action.record_date <= sessions[-1] and action.record_date not in sessions
               for action in actions):
            raise ValueError("Corporate-action record date missing from execution calendar")
        self.actions = sorted(actions, key=lambda action: action.ex_date)
        self.tax_rate = tax_rate
        self.entitlements: dict[str, tuple[int, date | None]] = {}
        self.applied, self.paid, self.listed = set(), set(), set()
        self.receivable = 0.0
        self.pending_shares = 0
        self.income: list[dict] = []

    def capture(self, day: date, position: int, bought_on: date | None) -> None:
        for action in self.actions:
            if action.record_date == day:
                self.entitlements[action.action_id] = (position, bought_on)

    def advance(self, day: date, cash: float, position: int, last_close: float):
        for action in self.actions:
            key = action.action_id
            if day < action.ex_date:
                continue
            quantity, entry_date = self.entitlements.get(key, (0, None))
            fractional = Fraction(str(action.bonus_ratio)) * quantity
            if fractional.denominator != 1:
                raise ValueError("Fractional bonus-share allocation requires explicit settlement evidence")
            shares = fractional.numerator
            distribution = round(quantity * action.cash_per_share * (1 - self.tax_rate), 4)
            if key not in self.applied:
                self.receivable = round(self.receivable + distribution, 4)
                self.pending_shares += shares
                if quantity:
                    self.income.append({"action_id": key, "ex_date": action.ex_date.isoformat(),
                                        "entry_date": entry_date.isoformat() if entry_date else None,
                                        "cash_income": distribution, "bonus_shares": shares,
                                        "eligible_shares": quantity})
                # Reference valuation for a suspended ex-date; never stored as OHLC.
                if last_close:
                    last_close = (last_close - action.cash_per_share) / (1 + action.bonus_ratio)
                    if last_close <= 0:
                        raise ValueError("Invalid corporate-action reference valuation")
                self.applied.add(key)
            if action.cash_date and action.cash_date <= day and key not in self.paid:
                cash = round(cash + distribution, 4)
                self.receivable = round(self.receivable - distribution, 4)
                self.paid.add(key)
            if action.stock_date and action.stock_date <= day and key not in self.listed:
                position += shares
                self.pending_shares -= shares
                self.listed.add(key)
        return cash, position, last_close
