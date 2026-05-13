import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import time
import logging
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.config import settings

try:
    import akshare as ak
except Exception:  # pragma: no cover - optional dependency at runtime
    ak = None

logger = logging.getLogger(__name__)


class BaostockService:
    def __init__(self):
        self.is_login = False

    def login(self) -> bool:
        """Login to baostock"""
        if not self.is_login:
            lg = bs.login()
            if lg.error_code != "0":
                logger.error(f"Baostock login failed: {lg.error_msg}")
                return False
            self.is_login = True
        return True

    def logout(self) -> None:
        """Logout from baostock"""
        if self.is_login:
            bs.logout()
            self.is_login = False

    def _infer_market_by_code(self, code_digits: str) -> str:
        if code_digits.startswith(("8", "4")):
            return "bj"
        if code_digits.startswith(("6", "9", "5")):
            return "sh"
        return "sz"

    def _normalize_code_with_market(
        self, code_digits: str, market: Optional[str] = None
    ) -> str:
        mkt = (market or self._infer_market_by_code(code_digits)).lower()
        return f"{mkt}.{code_digits}"

    def _get_stock_list_baostock(self) -> List[dict]:
        if not self.login():
            return []

        rs = bs.query_stock_basic()
        stocks: List[dict] = []
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            # row: code,name,ipoDate,outDate,type,status
            if len(row) < 6:
                continue
            # Filter: type=1 (A股), status=1 (上市)
            if row[4] != "1" or row[5] != "1":
                continue
            code = row[0]
            market = (
                code.split(".")[0] if "." in code else self._infer_market_by_code(code)
            )
            stocks.append(
                {
                    "code": code,
                    "name": row[1],
                    "list_date": row[2] or None,
                    "market": market,
                }
            )
        return stocks

    def _get_stock_list_akshare(self) -> List[dict]:
        if ak is None:
            logger.warning(
                "akshare is not installed, fallback to baostock for stock list"
            )
            return []
        try:
            raw = ak.stock_info_a_code_name()
        except Exception as exc:
            logger.warning("AKShare stock list fetch failed: %s", exc)
            return []

        if raw is None or raw.empty:
            return []

        code_col = (
            "code"
            if "code" in raw.columns
            else ("证券代码" if "证券代码" in raw.columns else None)
        )
        name_col = (
            "name"
            if "name" in raw.columns
            else ("证券简称" if "证券简称" in raw.columns else None)
        )
        if not code_col or not name_col:
            logger.warning("AKShare stock list columns mismatch: %s", list(raw.columns))
            return []

        stocks: List[dict] = []
        for row in raw.itertuples(index=False):
            code_digits = str(getattr(row, code_col)).strip()
            if not code_digits or code_digits.lower() == "nan":
                continue
            code_digits = code_digits.zfill(6)
            market = self._infer_market_by_code(code_digits)
            stocks.append(
                {
                    "code": self._normalize_code_with_market(code_digits, market),
                    "name": str(getattr(row, name_col)).strip(),
                    "list_date": None,
                    "market": market,
                }
            )
        return stocks

    def get_stock_list(self) -> List[dict]:
        """Get A stock list using configured provider with fallback."""
        provider = (settings.STOCK_LIST_PROVIDER or "akshare").strip().lower()
        if provider == "baostock":
            return self._get_stock_list_baostock()
        if provider == "akshare":
            stocks = self._get_stock_list_akshare()
            if stocks:
                return stocks
            return self._get_stock_list_baostock()
        logger.warning(
            "Unknown STOCK_LIST_PROVIDER '%s', fallback to akshare then baostock",
            provider,
        )
        stocks = self._get_stock_list_akshare()
        if stocks:
            return stocks
        return self._get_stock_list_baostock()

    def get_daily_kline(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get daily kline data using configured provider with fallback."""
        provider = (settings.KLINE_PROVIDER or "akshare").strip().lower()

        if provider == "baostock":
            return self._get_daily_kline_baostock(stock_code, start_date, end_date)

        if provider == "akshare":
            ak_df = self._get_daily_kline_akshare(stock_code, start_date, end_date)
            if not ak_df.empty:
                return ak_df
            return self._get_daily_kline_baostock(stock_code, start_date, end_date)

        logger.warning(
            "Unknown KLINE_PROVIDER '%s', fallback to akshare then baostock", provider
        )
        ak_df = self._get_daily_kline_akshare(stock_code, start_date, end_date)
        if not ak_df.empty:
            return ak_df
        return self._get_daily_kline_baostock(stock_code, start_date, end_date)

    def _to_akshare_symbol(self, stock_code: str) -> str:
        if "." in stock_code:
            return stock_code.split(".", 1)[1]
        return stock_code

    def _get_daily_kline_akshare(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        if ak is None:
            logger.warning("akshare is not installed, fallback to baostock")
            return pd.DataFrame()

        symbol = self._to_akshare_symbol(stock_code)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                raw = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust="qfq",
                )
                break  # success, exit retry loop
            except Exception as exc:
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 2  # 2, 4, 6 seconds backoff
                    logger.warning(
                        "AKShare fetch retry %d/%d for %s after %ds: %s",
                        attempt + 1, max_retries, stock_code, wait, exc
                    )
                    time.sleep(wait)
                else:
                    logger.warning("AKShare fetch failed for %s: %s", stock_code, exc)
                    return pd.DataFrame()

        if raw is None or raw.empty:
            return pd.DataFrame()

        def pick_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
            for col in candidates:
                if col in df.columns:
                    return col
            return None

        date_col = pick_column(raw, ["日期", "date", "Date"])
        open_col = pick_column(raw, ["开盘", "open", "Open"])
        high_col = pick_column(raw, ["最高", "high", "High"])
        low_col = pick_column(raw, ["最低", "low", "Low"])
        close_col = pick_column(raw, ["收盘", "close", "Close"])
        volume_col = pick_column(raw, ["成交量", "volume", "Volume"])
        amount_col = pick_column(raw, ["成交额", "amount", "Amount"])

        required_cols = [date_col, open_col, high_col, low_col, close_col, volume_col]
        if any(c is None for c in required_cols):
            logger.warning(
                "AKShare columns mismatch for %s, columns=%s",
                stock_code,
                list(raw.columns),
            )
            return pd.DataFrame()

        df = pd.DataFrame(
            {
                "date": pd.to_datetime(raw[date_col]).dt.strftime("%Y-%m-%d"),
                "open": pd.to_numeric(raw[open_col], errors="coerce").fillna(0),
                "high": pd.to_numeric(raw[high_col], errors="coerce").fillna(0),
                "low": pd.to_numeric(raw[low_col], errors="coerce").fillna(0),
                "close": pd.to_numeric(raw[close_col], errors="coerce").fillna(0),
                "volume": pd.to_numeric(raw[volume_col], errors="coerce").fillna(0),
                "amount": pd.to_numeric(raw[amount_col], errors="coerce").fillna(0)
                if amount_col
                else 0,
                "stock_code": stock_code,
            }
        )

        return df[df["date"].notna()].reset_index(drop=True)

    def _get_daily_kline_baostock(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get daily kline data from baostock."""
        if not self.login():
            return pd.DataFrame()

        # Format stock code for baostock (already has prefix like "sh.600000")
        if "." in stock_code:
            bs_code = stock_code
        elif stock_code.startswith("6"):
            bs_code = f"sh.{stock_code}"
        else:
            bs_code = f"sz.{stock_code}"

        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2",  # 前复权
        )

        data_list = []
        while rs.error_code == "0" and rs.next():
            try:
                row = rs.get_row_data()
                # Skip rows with invalid data (encoding issues)
                if not row or len(row) < 7:
                    continue
                # Try to convert each value to handle encoding issues
                cleaned_row = []
                for val in row:
                    if val is None:
                        cleaned_row.append("0")
                    else:
                        try:
                            # Try to encode/decode to handle encoding issues
                            str(val).encode("utf-8").decode("utf-8")
                            cleaned_row.append(val)
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            cleaned_row.append("0")
                data_list.append(cleaned_row)
            except Exception as e:
                logger.warning("处理数据行时跳过异常行: %s", e)

        if not data_list:
            return pd.DataFrame()

        df = pd.DataFrame(data_list, columns=rs.fields)
        df["stock_code"] = stock_code

        # Convert types and replace NaN with None
        df["open"] = pd.to_numeric(df["open"], errors="coerce").fillna(0)
        df["high"] = pd.to_numeric(df["high"], errors="coerce").fillna(0)
        df["low"] = pd.to_numeric(df["low"], errors="coerce").fillna(0)
        df["close"] = pd.to_numeric(df["close"], errors="coerce").fillna(0)
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

        return df

    def sync_stock_list(self, db) -> Tuple[int, str]:
        """Sync stock list to database"""
        from app.models.models import Stock

        stocks = self.get_stock_list()
        if not stocks:
            return 0, "No stock list data from provider"
        count = 0

        # Check if already synced
        existing_count = db.query(Stock).count()
        if existing_count >= len(stocks):
            return 0, f"股票列表已是最新 (共 {existing_count} 只)"

        for stock in stocks:
            code = stock.get("code")
            name = stock.get("name")
            list_date = stock.get("list_date")
            market = stock.get("market") or (
                code.split(".")[0] if code and "." in code else "sh"
            )

            if not code or not name:
                continue

            existing = db.query(Stock).filter(Stock.code == code).first()
            if existing:
                continue

            parsed_date = None
            if list_date:
                try:
                    parsed_date = datetime.strptime(str(list_date), "%Y-%m-%d").date()
                except ValueError:
                    parsed_date = None

            new_stock = Stock(
                code=code, name=name, market=market, list_date=parsed_date
            )
            db.add(new_stock)
            count += 1

            if count % 200 == 0:
                db.commit()

        db.commit()
        return count, "Stock list synced"

    def sync_kline_data(
        self,
        db,
        stock_codes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[int, str]:
        """Sync kline data for stocks"""
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            # Incremental sync: default to 30 days before end_date
            end = datetime.strptime(end_date, "%Y-%m-%d")
            start_date = (end - timedelta(days=30)).strftime("%Y-%m-%d")

        from app.models.models import Stock, DailyKline

        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        if start_date_obj > end_date_obj:
            return 0, "Invalid date range: start_date is after end_date"

        # Get stocks to sync
        if stock_codes:
            stocks = (
                db.query(Stock)
                .filter(Stock.code.in_(stock_codes))
                .order_by(Stock.code)
                .all()
            )
        else:
            stocks = db.query(Stock).order_by(Stock.code).all()

        if not stocks:
            return 0, "No stocks found to sync"

        stock_code_list = [s.code for s in stocks]
        latest_rows = (
            db.query(DailyKline.stock_code, func.max(DailyKline.date))
            .filter(DailyKline.stock_code.in_(stock_code_list))
            .group_by(DailyKline.stock_code)
            .all()
        )
        latest_dates = {
            code: latest_date
            for code, latest_date in latest_rows
            if latest_date is not None
        }

        # Tuned for reduced DB round-trips and memory pressure.
        batch_size = 5000
        rate_limit_seconds = 1.0

        total_klines = 0
        processed_stocks = 0
        skipped_up_to_date = 0
        failed_stocks = 0
        pending_rows: list[dict] = []

        def flush_pending_rows() -> int:
            if not pending_rows:
                return 0
            rows = list(pending_rows)
            pending_rows.clear()
            try:
                db.execute(DailyKline.__table__.insert(), rows)
                db.commit()
                return len(rows)
            except IntegrityError:
                db.rollback()
                inserted = 0
                for row in rows:
                    try:
                        db.execute(DailyKline.__table__.insert(), [row])
                        inserted += 1
                    except IntegrityError:
                        db.rollback()
                db.commit()
                return inserted

        for stock in stocks:
            # Check if stock is already up to date (no DB operation needed)
            latest_date = latest_dates.get(stock.code)
            if latest_date:
                next_date = latest_date + timedelta(days=1)
            effective_date = (
                max(start_date_obj, next_date) if latest_date else start_date_obj
            )

            if effective_date > end_date_obj:
                skipped_up_to_date += 1
                continue

            df = self.get_daily_kline(
                stock.code, effective_date.strftime("%Y-%m-%d"), end_date
            )

            # Rate limiting — always wait after every API call
            if rate_limit_seconds > 0:
                time.sleep(rate_limit_seconds)

            if df.empty:
                continue

            try:
                for row in df.itertuples(index=False):
                    close_price = float(getattr(row, "close", 0) or 0)
                    if close_price == 0:
                        continue

                    pending_rows.append(
                        {
                            "stock_code": stock.code,
                            "date": datetime.strptime(row.date, "%Y-%m-%d").date(),
                            "open": float(getattr(row, "open", 0) or 0),
                            "high": float(getattr(row, "high", 0) or 0),
                            "low": float(getattr(row, "low", 0) or 0),
                            "close": close_price,
                            "volume": float(getattr(row, "volume", 0) or 0),
                            "amount": float(getattr(row, "amount", 0) or 0),
                        }
                    )

                if len(pending_rows) >= batch_size:
                    total_klines += flush_pending_rows()

                processed_stocks += 1

            except Exception as e:
                logger.error(f"Error syncing {stock.code}: {e}")
                db.rollback()
                failed_stocks += 1

        total_klines += flush_pending_rows()
        return (
            total_klines,
            f"Kline data synced for {processed_stocks} stocks, "
            f"skipped up-to-date: {skipped_up_to_date}, failed: {failed_stocks}",
        )

    def get_index_list(self) -> List[dict]:
        """Get major market indices"""
        return MAJOR_INDICES

    def get_index_daily_kline(
        self, index_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Get index daily kline data"""
        if not self.login():
            return pd.DataFrame()

        rs = bs.query_history_k_data_plus(
            index_code,
            "date,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3",  # 不复权
        )

        data_list = []
        while rs.error_code == "0" and rs.next():
            try:
                row = rs.get_row_data()
                if not row or len(row) < 7:
                    continue
                cleaned_row = []
                for val in row:
                    if val is None:
                        cleaned_row.append("0")
                    else:
                        try:
                            str(val).encode("utf-8").decode("utf-8")
                            cleaned_row.append(val)
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            cleaned_row.append("0")
                data_list.append(cleaned_row)
            except Exception as e:
                logger.warning("处理数据行时跳过异常行: %s", e)

        if not data_list:
            return pd.DataFrame()

        df = pd.DataFrame(data_list, columns=rs.fields)
        df["stock_code"] = index_code

        df["open"] = pd.to_numeric(df["open"], errors="coerce").fillna(0)
        df["high"] = pd.to_numeric(df["high"], errors="coerce").fillna(0)
        df["low"] = pd.to_numeric(df["low"], errors="coerce").fillna(0)
        df["close"] = pd.to_numeric(df["close"], errors="coerce").fillna(0)
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

        return df

    def sync_index_kline_data(
        self,
        db,
        index_codes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[int, str]:
        """Sync index kline data to database"""
        from app.models.models import DailyKline

        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            start_date = (end - timedelta(days=30)).strftime("%Y-%m-%d")

        indices = self.get_index_list()
        if index_codes:
            indices = [idx for idx in indices if idx["code"] in index_codes]

        if not indices:
            return 0, "No indices found"

        total_klines = 0
        rate_limit_seconds = 0.1

        for index_info in indices:
            try:
                df = self.get_index_daily_kline(
                    index_info["code"], start_date, end_date
                )

                if df.empty:
                    continue

                pending_rows = []
                for row in df.itertuples(index=False):
                    close_price = float(getattr(row, "close", 0) or 0)
                    if close_price == 0:
                        continue

                    pending_rows.append(
                        {
                            "stock_code": index_info["code"],
                            "date": datetime.strptime(row.date, "%Y-%m-%d").date(),
                            "open": float(getattr(row, "open", 0) or 0),
                            "high": float(getattr(row, "high", 0) or 0),
                            "low": float(getattr(row, "low", 0) or 0),
                            "close": close_price,
                            "volume": float(getattr(row, "volume", 0) or 0),
                            "amount": float(getattr(row, "amount", 0) or 0),
                        }
                    )

                if pending_rows:
                    try:
                        db.execute(DailyKline.__table__.insert(), pending_rows)
                        db.commit()
                        total_klines += len(pending_rows)
                    except IntegrityError:
                        db.rollback()
                        for row in pending_rows:
                            try:
                                db.execute(DailyKline.__table__.insert(), [row])
                                total_klines += 1
                            except IntegrityError:
                                db.rollback()
                        db.commit()

                if rate_limit_seconds > 0:
                    time.sleep(rate_limit_seconds)

            except Exception as e:
                logger.error(f"Error syncing {index_info['code']}: {e}")
                continue

        return total_klines, f"Index kline data synced: {total_klines} records"


# Singleton instance
baostock_service = BaostockService()

# Major China market indices
MAJOR_INDICES = [
    {"code": "sh.000001", "name": "上证指数"},
    {"code": "sh.000016", "name": "上证50"},
    {"code": "sh.000300", "name": "沪深300"},
    {"code": "sz.399001", "name": "深证成指"},
    {"code": "sz.399006", "name": "创业板指"},
    {"code": "sz.000688", "name": "科创50"},
]
