from app.services.baostock_rpc import BaostockRPC
from app.services.baostock_rpc import provider_worker
from queue import Queue
import pytest


def echo_worker(requests, responses):
    while (request := requests.get()) is not None:
        responses.put((True, [{"operation": request[0]}]))


def silent_worker(requests, responses):
    while requests.get() is not None:
        pass


def test_isolated_provider_reuses_connection_and_closes_owned_process():
    client = BaostockRPC(timeout_s=10, worker=echo_worker)
    try:
        assert client.query("first") == [{"operation": "first"}]
        process = client._process
        assert client.query("second") == [{"operation": "second"}]
        assert client._process is process
    finally:
        client.close()
    assert client._process is None


def test_hung_provider_is_terminated_and_next_request_can_recover():
    client = BaostockRPC(timeout_s=0.2, worker=silent_worker)
    try:
        with pytest.raises(TimeoutError, match="isolated connection closed"):
            client.query("hung")
        assert client._process is None
        client.worker = echo_worker
        client.timeout_s = 10
        assert client.query("recovered") == [{"operation": "recovered"}]
    finally:
        client.close()


@pytest.mark.parametrize("progress", [False, True])
def test_worker_protocol_remains_compatible_with_already_running_clients(monkeypatch, progress):
    import baostock as bs
    from types import SimpleNamespace

    monkeypatch.setattr(bs, "login", lambda: SimpleNamespace(error_code="0"))
    monkeypatch.setattr(bs, "query_stock_basic", lambda: SimpleNamespace(error_code="0", fields=[], next=lambda: False))
    requests, responses = Queue(), Queue()
    requests.put(("query_stock_basic", (), {}))
    requests.put(None)
    provider_worker(requests, responses, report_progress=progress)
    if progress:
        assert responses.get_nowait() == (None, "login")
        assert responses.get_nowait() == (None, "query")
    assert responses.get_nowait() == (True, [])
    assert responses.empty()
