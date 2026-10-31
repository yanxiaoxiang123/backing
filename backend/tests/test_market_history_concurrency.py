"""Interactive history is isolated from unrelated bulk ingestion, not its own symbol."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Base
from app.models.models import Stock
from app.services.market_data import store_bars, store_calendar
from app.services.market_data_sync import ingestion_lock, sync_history

DAY = date(2025, 1, 2)
BAR = {"date": DAY, "open": 10, "high": 11, "low": 9, "close": 10, "volume": 10000}


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent-history.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([Stock(code=code, name=code, market=code[:2]) for code in ("sh.600000", "sz.000001")])
        for exchange in ("sh", "sz"):
            store_calendar(db, exchange, [{"date": DAY, "is_open": True}], provider="fixture")
        db.commit()
    yield factory
    engine.dispose()


def test_unrelated_stock_can_be_fetched_while_bulk_holds_another_symbol(factory):
    class Provider:
        name = "fixture"

        def bars(self, code, start, end):
            assert code == "sz.000001"
            return [BAR]

    with factory() as bulk, factory() as interactive:
        with ingestion_lock(bulk, scope="history:sh.600000"):
            result = sync_history(interactive, ["sz.000001"], DAY, DAY, provider=Provider(), rate_limit_s=0)
            assert result["success"] is True
            with pytest.raises(ValueError, match="ingestion is active"):
                with ingestion_lock(interactive, scope="history:sh.600000"):
                    pytest.fail("Same-security lock was bypassed")


def test_waiting_same_stock_reuses_committed_download_instead_of_fetching_twice(factory):
    class Provider:
        name = "must-not-be-called"

        def bars(self, *args):
            pytest.fail("Already downloaded bars must be reused after the competing writer commits")

    def interactive_sync():
        with factory() as db:
            return sync_history(db, ["sh.600000"], DAY, DAY, provider=Provider(), rate_limit_s=0)

    with ThreadPoolExecutor(max_workers=1) as executor, factory() as bulk:
        with ingestion_lock(bulk, scope="history:sh.600000"):
            future = executor.submit(interactive_sync)
            with pytest.raises(FutureTimeoutError):
                future.result(timeout=0.05)
            store_bars(bulk, "sh.600000", [BAR], provider="fixture")
            bulk.commit()
        assert future.result(timeout=3)["success"] is True
