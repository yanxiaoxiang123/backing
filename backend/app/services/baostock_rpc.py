"""Isolate the SDK's blocking socket loop behind a killable request deadline."""

import atexit
import multiprocessing
from queue import Empty
import threading
import time


def records(result) -> list[dict]:
    if result.error_code != "0":
        raise RuntimeError(f"Baostock error {result.error_code}: {result.error_msg}")
    rows = []
    while result.next():
        rows.append(dict(zip(result.fields, result.get_row_data(), strict=True)))
    if result.error_code != "0":
        raise RuntimeError(f"Baostock incomplete response: {result.error_msg}")
    return rows


def provider_worker(requests, responses, *, report_progress=False):
    import baostock as bs

    allowed = {"query_trade_dates", "query_stock_basic", "query_history_k_data_plus",
               "query_all_stock", "query_adjust_factor", "query_dividend_data"}
    logged_in = False
    while (request := requests.get()) is not None:
        name, args, kwargs = request
        try:
            if name not in allowed:
                raise ValueError("Unsupported market-data operation")
            if not logged_in:
                if report_progress:
                    responses.put((None, "login"))
                login = bs.login()
                if login.error_code != "0":
                    raise RuntimeError(f"Baostock login error: {login.error_code}")
                logged_in = True
            if report_progress:
                responses.put((None, "query"))
            responses.put((True, records(getattr(bs, name)(*args, **kwargs))))
        except Exception as exc:
            responses.put((False, str(exc)[:500]))


class BaostockRPC:
    def __init__(self, timeout_s: float = 45, *, worker=provider_worker):
        if timeout_s <= 0:
            raise ValueError("Provider deadline must be positive")
        self.timeout_s, self.worker = timeout_s, worker
        self._lock = threading.Lock()
        self._process = self._requests = self._responses = None

    def _stop(self):
        if self._process is not None:
            if self._process.is_alive():
                self._process.terminate()
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.kill()
                self._process.join(timeout=2)
            self._process.close()
            self._process = None
        for queue in (self._requests, self._responses):
            if queue is not None:
                queue.cancel_join_thread()
                queue.close()
        self._requests = self._responses = None

    def query(self, name: str, *args, **kwargs) -> list[dict]:
        with self._lock:
            if self._process is None or not self._process.is_alive():
                self._stop()
                context = multiprocessing.get_context("spawn")
                self._requests, self._responses = context.Queue(), context.Queue()
                progress = {"report_progress": True} if self.worker is provider_worker else {}
                self._process = context.Process(target=self.worker, args=(self._requests, self._responses),
                                                 kwargs=progress, daemon=True)
                self._process.start()
            self._requests.put((name, args, kwargs))
            stage = "worker_startup"
            deadline = time.monotonic() + self.timeout_s
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise Empty
                    success, payload = self._responses.get(timeout=remaining)
                    if success is None:
                        stage = str(payload)
                        continue
                    break
            except Empty as exc:
                self._stop()
                raise TimeoutError(f"Baostock {name} exceeded {self.timeout_s:g}s at {stage}; isolated connection closed") from exc
            if not success:
                # Discard a potentially desynchronized SDK connection.
                self._stop()
                raise RuntimeError(payload)
            return payload

    def close(self):
        with self._lock:
            self._stop()


market_data_rpc = BaostockRPC()
atexit.register(market_data_rpc.close)
