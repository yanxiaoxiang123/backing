"""Remote DL contracts, causal inputs, cancellation and strict calendar behavior."""

from datetime import date, datetime, timedelta, timezone
from contextlib import nullcontext
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import threading
from unittest.mock import Mock
import weakref
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_authenticated_actor, get_current_api_key
from app.config import Base
from app.exceptions import ExternalServiceError, ProviderTimeoutError, ProviderUnavailableError
from app.models.market_data import TradingSession
from app.models.models import JobDbRecord
from app.services.dl_prediction import experiments as exp
from app.services.dl_prediction.contracts import BacktestExperimentRequest, ExperimentRequest
from app.services.dl_prediction.remote import (
    KronosClient, MODEL_REVISIONS, SOURCE_REVISION, TOKENIZER_REVISION, TIMESFM_SOURCE_REVISION, source_revision,
)
from app.services.tasks import TaskCancelledError


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


def bars(count=80):
    days = pd.bdate_range("2026-05-04", periods=count).date
    return pd.DataFrame([{
        "date": day, "open": 10.0, "high": 11.0, "low": 9.0,
        "close": 10.0, "volume": 100000.0, "amount": 1000000.0,
    } for day in days])


@pytest.mark.parametrize("changes", [
    {"model": "other"}, {"kline_days": 59}, {"kline_days": 513},
    {"prediction_days": 0}, {"prediction_days": 31},
    {"model": "legacy", "kline_days": 200, "prediction_days": 10},
    {"stock_code": "invalid"}, {"stock_code": "bj.430047"},
])
def test_experiment_rejects_invalid_limits(changes):
    with pytest.raises(ValueError):
        ExperimentRequest.model_validate({"stock_code": "600000", **changes})


def test_calendar_skips_verified_holiday_and_never_guesses(sessions, monkeypatch):
    with sessions() as db:
        # October 1-7 are known closed, unlike a weekday-only forecast calendar.
        begin = date(2026, 9, 30)
        for i in range(10):
            day = begin + timedelta(days=i)
            db.add(TradingSession(exchange="sh", date=day, is_open=day >= date(2026, 10, 8),
                                  provider="fixture", observed_at=datetime(2026, 1, 1)))
        db.commit()
        assert exp.future_dates(db, "sh.600000", begin, 2) == ["2026-10-08", "2026-10-09"]
        monkeypatch.setattr(exp, "sync_calendar", Mock(side_effect=ValueError("calendar unavailable")))
        with pytest.raises(ValueError, match="calendar unavailable"):
            exp.future_dates(db, "sh.600000", date(2026, 10, 9), 5)


def test_forecast_cutoff_waits_for_daily_provider_publication():
    shanghai = ZoneInfo("Asia/Shanghai")
    assert exp.forecast_cutoff(datetime(2026, 11, 4, 15, 45, tzinfo=shanghai)) == date(2026, 11, 3)
    assert exp.forecast_cutoff(datetime(2026, 11, 4, 17, 30, tzinfo=shanghai)) == date(2026, 11, 4)
    assert exp.forecast_cutoff(datetime(2026, 11, 4, 9, 29, tzinfo=timezone.utc)) == date(2026, 11, 3)


@pytest.mark.parametrize("field,value", [
    ("amount", None), ("volume", -1), ("close", float("inf")), ("low", 12),
])
def test_history_rejects_missing_units_and_bad_ohlc(field, value):
    frame = bars(60)
    frame.loc[0, field] = value
    with pytest.raises(ValueError):
        exp.validate_history(frame, 60)


def test_history_rejects_duplicate_dates():
    frame = bars(60)
    frame.loc[1, "date"] = frame.loc[0, "date"]
    with pytest.raises(ValueError, match="唯一"):
        exp.validate_history(frame, 60)


def test_infer_sends_raw_shares_yuan_and_dates_without_future_prices(monkeypatch):
    history = bars(60)
    request = ExperimentRequest(stock_code="600000", kline_days=60)
    dates = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]
    monkeypatch.setattr(exp, "future_dates", lambda *args: dates)
    client = Mock()
    client.predict.return_value = {"predictions": [{"date": day, "close": 11.0} for day in dates]}
    _, audit = exp.infer(client, None, request, history, 5, "job", lambda: None, lambda x: None)
    payload = client.predict.call_args.args[0]
    assert payload["bars"][0]["volume"] == 100000
    assert payload["bars"][0]["amount"] == 1000000
    assert set(payload) == {"model", "bars", "history_dates", "future_dates", "prediction_days", "request_id"}
    assert len(payload["bars"]) == len(payload["history_dates"]) == 60
    assert audit["input"] == payload


def test_cancelled_job_cannot_be_overwritten_by_gpu_completion(sessions, monkeypatch):
    monkeypatch.setattr(exp, "SessionLocal", sessions)
    with sessions() as db:
        db.add(JobDbRecord(id="cancelled", job_type="dl_predict", status="failed", error="Cancelled"))
        db.commit()
    with pytest.raises(TaskCancelledError):
        exp.update_job("cancelled", status="completed", result={"success": True})
    with sessions() as db:
        assert db.get(JobDbRecord, "cancelled").status == "failed"


def test_cancelled_job_transport_failure_cannot_trigger_retry(sessions, monkeypatch):
    monkeypatch.setattr(exp, "SessionLocal", sessions)
    with sessions() as db:
        db.add(JobDbRecord(id="cancel-race", job_type="dl_predict", status="running"))
        db.commit()

    def interrupted_forecast(*args):
        with sessions() as db:
            job = db.get(JobDbRecord, "cancel-race")
            job.status, job.error = "failed", "Cancelled"
            db.commit()
        raise ProviderTimeoutError("timeout", provider="kronos")

    def current_job(job_id):
        with sessions() as db:
            return SimpleNamespace(status=db.get(JobDbRecord, job_id).status)

    monkeypatch.setattr(exp, "forecast", interrupted_forecast)
    monkeypatch.setattr(exp.job_store, "get", current_job)
    with pytest.raises(TaskCancelledError):
        exp.run_experiment("cancel-race", ExperimentRequest(stock_code="600000").model_dump(mode="json"), False)


@pytest.mark.parametrize("model", ["kronos-small", "timesfm-2.5"])
def test_rolling_backtest_is_causal_and_uses_next_open(monkeypatch, sessions, model):
    frame = bars(80)
    period_start = frame.iloc[60]["date"]
    request = BacktestExperimentRequest(stock_code="600000", model=model, kline_days=60,
                                        start_date=period_start, end_date=frame.iloc[-1]["date"])
    monkeypatch.setattr(exp, "SessionLocal", sessions)
    monkeypatch.setattr(exp, "prepare_history", Mock())
    monkeypatch.setattr(exp, "sync_calendar", Mock())
    monkeypatch.setattr(exp, "load_research_bars", lambda *a, **kw: frame.copy())
    monkeypatch.setattr(exp, "execution_actions", lambda *a: ([], {"limitations": []}))
    monkeypatch.setattr(exp, "open_sessions", lambda *a: list(frame.iloc[60:]["date"]))
    monkeypatch.setattr(exp, "future_dates", lambda db, code, day, n: [
        (day + timedelta(days=i + 1)).isoformat() for i in range(n)
    ])
    monkeypatch.setattr(exp, "update_job", Mock())
    monkeypatch.setattr(exp.job_store, "get", lambda _: None)
    captured = []

    class Client:
        def predict(self, payload, check, progress):
            captured.append(payload)
            return {"predictions": [{"date": d, "close": 11.0} for d in payload["future_dates"]]}

    monkeypatch.setattr(exp, "KronosClient", Client)
    first = exp.rolling_backtest(request, "job", lambda: None, lambda x: None)
    assert len(first["anchors"]) == 4
    assert len(first["dates"]) == 20  # Warmup does not consume requested backtest dates.
    assert first["trades"][0]["date"] == frame.iloc[61]["date"].isoformat()
    original_input = captured[0]
    frame.loc[frame["date"] > period_start, ["open", "close"]] = 10.5
    captured.clear()
    second = exp.rolling_backtest(request, "job", lambda: None, lambda x: None)
    assert captured[0] == original_input
    assert first["anchors"][0]["signal"] == second["anchors"][0]["signal"]
    assert all(max(item["input"]["history_dates"]) == item["anchor_date"] for item in second["anchors"])


def test_client_rejects_model_version_change(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "KRONOS_SERVICE_URL", "http://fixture")
    monkeypatch.setattr(settings, "KRONOS_SERVICE_TOKEN", "private-fixture-token")
    client = KronosClient()
    result = {"model": "kronos-small", "model_revision": "changed", "source_revision": SOURCE_REVISION,
              "tokenizer_revision": TOKENIZER_REVISION}
    monkeypatch.setattr(client, "status", lambda: {"busy": False, "loaded_model": "kronos-small"})
    monkeypatch.setattr(client, "_request", lambda *a, **kw: httpx.Response(200, json=result))
    with pytest.raises(ValueError, match="版本"):
        client.predict({"model": "kronos-small"}, lambda: None, lambda x: None)


def test_client_status_rejects_unpinned_catalog(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "KRONOS_SERVICE_URL", "http://fixture")
    monkeypatch.setattr(settings, "KRONOS_SERVICE_TOKEN", "private-fixture-token")
    client = KronosClient()
    catalog = {"source_revision": SOURCE_REVISION, "tokenizer_revision": TOKENIZER_REVISION,
               "models": [{"id": name, "revision": revision, "source_revision": source_revision(name)}
                          for name, revision in MODEL_REVISIONS.items()]}
    monkeypatch.setattr(client, "_request", lambda *a, **kw: httpx.Response(200, json=catalog))
    assert client.status() == catalog
    catalog["models"][0]["revision"] = "changed"
    with pytest.raises(ValueError, match="版本"):
        client.status()


@pytest.mark.parametrize("code", ["gpu_oom", "model_unavailable", "inference_failed", "unauthorized"])
def test_client_maps_remote_errors_without_leaking_details(code):
    with pytest.raises(ExternalServiceError) as caught:
        KronosClient._error(httpx.Response(503, json={"detail": {"code": code, "message": "private details"}}))
    assert caught.value.error_code == code
    assert "private details" not in str(caught.value)
    assert not caught.value.retryable


@pytest.mark.parametrize("failure,expected", [
    (httpx.ReadTimeout("timeout"), ProviderTimeoutError),
    (httpx.ConnectError("unreachable"), ProviderUnavailableError),
])
def test_client_maps_transport_failure(monkeypatch, failure, expected):
    from app.config import settings

    monkeypatch.setattr(settings, "KRONOS_SERVICE_URL", "http://fixture")
    monkeypatch.setattr(settings, "KRONOS_SERVICE_TOKEN", "private-fixture-token")

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(httpx.Client, "request", fail)
    with pytest.raises(expected):
        KronosClient()._request("GET", "/v1/status")


def test_client_busy_wait_checks_cancellation(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "KRONOS_SERVICE_URL", "http://fixture")
    monkeypatch.setattr(settings, "KRONOS_SERVICE_TOKEN", "private-fixture-token")
    client = KronosClient()
    monkeypatch.setattr(client, "status", lambda: {"busy": True, "phase": "loading_model"})
    progress = Mock()
    checks = Mock(side_effect=[None, TaskCancelledError("cancelled")])
    with pytest.raises(TaskCancelledError):
        client.predict({"model": "kronos-small"}, checks, progress)
    progress.assert_called_once_with("等待 GPU · 加载模型")


def test_client_reports_actual_remote_loading_and_inference_phases(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "KRONOS_SERVICE_URL", "http://fixture")
    monkeypatch.setattr(settings, "KRONOS_SERVICE_TOKEN", "private-fixture-token")
    client = KronosClient()
    finish = threading.Event()
    states = iter([{"busy": False}, {"phase": "loading_model"}, {"phase": "inference"}])

    def status():
        state = next(states)
        if state.get("phase") == "inference":
            finish.set()
        return state

    result = {"model": "kronos-small", "model_revision": MODEL_REVISIONS["kronos-small"],
              "source_revision": SOURCE_REVISION, "tokenizer_revision": TOKENIZER_REVISION}

    def request(*args, **kwargs):
        assert finish.wait(timeout=5), "Progress polling must continue during the HTTP inference"
        return httpx.Response(200, json=result)

    monkeypatch.setattr(client, "status", status)
    monkeypatch.setattr(client, "_request", request)
    progress = Mock()
    assert client.predict({"model": "kronos-small"}, lambda: None, progress) == result
    assert "加载模型" in [call.args[0] for call in progress.call_args_list]
    assert "推理中" in [call.args[0] for call in progress.call_args_list]


def test_async_api_contract_and_idempotency_conflict(monkeypatch):
    from app.api import dl_prediction as api
    from app.error_handlers import register_error_handlers

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(api.router, prefix="/api/v1/dl")
    app.dependency_overrides[get_current_api_key] = lambda: "test"
    app.dependency_overrides[get_authenticated_actor] = lambda: "actor"
    executor = Mock()
    executor.submit.return_value = SimpleNamespace(id="one", status="pending", message="queued")
    monkeypatch.setattr(api, "get_task_executor", lambda: executor)
    monkeypatch.setattr(api.job_store, "_find_by_key", lambda _: None)
    client = TestClient(app)
    response = client.post("/api/v1/dl/predict/submit", json={"stock_code": "600000"},
                           headers={"Idempotency-Key": "test-one"})
    assert response.status_code == 202
    assert response.json()["job_id"] == "one"
    assert executor.submit.call_args.kwargs["payload"]["stock_code"] == "sh.600000"
    monkeypatch.setattr(api.job_store, "_find_by_key", lambda _: SimpleNamespace(payload={"other": True}))
    assert client.post("/api/v1/dl/predict/submit", json={"stock_code": "600000"},
                       headers={"Idempotency-Key": "test-one"}).status_code == 409


@pytest.fixture
def remote_service():
    location = Path(__file__).resolve().parents[2] / "deploy/kronos/service.py"
    spec = importlib.util.spec_from_file_location("kronos_deploy_fixture", location)
    service = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = service
    spec.loader.exec_module(service)
    return service


def test_remote_auth_validation_and_serial_execution(monkeypatch, remote_service):
    service = remote_service
    monkeypatch.setenv("KRONOS_SERVICE_TOKEN", "private-fixture-token")
    client = TestClient(service.app)
    assert client.get("/v1/status").status_code == 401
    headers = {"Authorization": "Bearer private-fixture-token"}
    assert client.get("/v1/status", headers=headers).status_code == 200
    payload = {
        "model": "kronos-small", "bars": bars(60).drop(columns="date").to_dict("records"),
        "history_dates": [d.isoformat() for d in bars(60)["date"]],
        "future_dates": ["2026-08-03"], "prediction_days": 1,
    }
    service.runtime.lock.acquire()
    try:
        assert client.post("/v1/predict", headers=headers, json=payload).status_code == 429
    finally:
        service.runtime.lock.release()
    payload["model"] = "/tmp/arbitrary-model"
    assert client.post("/v1/predict", headers=headers, json=payload).status_code == 422
    assert MODEL_REVISIONS["kronos-small"] in str(client.get("/v1/status", headers=headers).json())


def test_remote_reuses_one_model_switches_and_releases_idle_weights(monkeypatch, remote_service):
    service = remote_service
    alive = weakref.WeakSet()
    loads = []

    class Weight:
        @classmethod
        def from_pretrained(cls, path):
            assert not alive, "A previous model must be released before loading a new one"
            item = cls()
            alive.add(item)
            loads.append(path)
            return item

        def requires_grad_(self, value):
            assert value is False
            return self

        def eval(self):
            return self

    class Tokenizer(Weight):
        @classmethod
        def from_pretrained(cls, path):
            return cls()

    class Predictor:
        def __init__(self, model, tokenizer, **kwargs):
            self.model, self.tokenizer = model, tokenizer

        def predict(self, **kwargs):
            return kwargs["df"].tail(kwargs["pred_len"]).reset_index(drop=True)

    monkeypatch.setitem(sys.modules, "model", SimpleNamespace(
        Kronos=Weight, KronosTokenizer=Tokenizer, KronosPredictor=Predictor,
    ))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False), manual_seed=lambda _: None,
        inference_mode=nullcontext,
    ))
    monkeypatch.setattr(sys, "path", sys.path.copy())
    payload = {
        "model": "kronos-small", "bars": bars(60).drop(columns="date").to_dict("records"),
        "history_dates": list(bars(60)["date"]), "future_dates": [date(2026, 8, 3)], "prediction_days": 1,
    }
    runtime = service.Runtime()
    runtime.run(service.PredictRequest(**payload))
    runtime.run(service.PredictRequest(**payload))
    assert len(loads) == len(alive) == 1
    runtime.run(service.PredictRequest(**{**payload, "model": "kronos-base"}))
    assert len(loads) == 2
    assert len(alive) == 1
    assert runtime.loaded_model == "kronos-base"
    class TimesFM:
        config = {"normalize_inputs": True}

        def __init__(self, *args):
            self.model = Weight.from_pretrained("timesfm")

        def predict(self, closes, horizon):
            return [closes[-1] + 0.1] * horizon

    monkeypatch.setitem(sys.modules, "timesfm_adapter", SimpleNamespace(TimesFMAdapter=TimesFM))
    result = runtime.run(service.PredictRequest(**{
        **payload, "model": "timesfm-2.5", "bars": [{"close": 10}] * 60,
    }))
    assert len(alive) == 1
    assert len(loads) == 3
    assert result["source_revision"] == TIMESFM_SOURCE_REVISION
    assert result["sampling"] is None
    assert result["tokenizer_revision"] is None
    assert result["output_fields"] == ["close"]
    assert result["predictions"] == [{"date": "2026-08-03", "close": 10.1}]
    assert runtime.loaded_model == "timesfm-2.5"
    runtime.last_used -= service.IDLE_SECONDS + 1
    runtime.expire()
    assert runtime.loaded_model is None
    assert not alive


@pytest.mark.parametrize("horizon,context", [(1, 60), (30, 512)])
def test_timesfm_request_supports_shared_horizon_and_context(horizon, context):
    request = ExperimentRequest(stock_code="600000", model="timesfm-2.5",
                                prediction_days=horizon, kline_days=context)
    assert request.model == "timesfm-2.5"


def test_timesfm_infer_sends_only_historical_closes(monkeypatch):
    history = bars(60)
    request = ExperimentRequest(stock_code="600000", model="timesfm-2.5", kline_days=60)
    dates = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]
    monkeypatch.setattr(exp, "future_dates", lambda *args: dates)
    client = Mock()
    client.predict.return_value = {"predictions": [{"date": day, "close": 11.0} for day in dates]}
    _, audit = exp.infer(client, None, request, history, 5, "job", lambda: None, lambda _: None)
    assert audit["input"]["bars"] == [{"close": 10.0}] * 60
    assert audit["input"]["history_dates"][-1] == str(history.iloc[-1]["date"])


def test_timesfm_forecast_does_not_invent_future_ohlcv(monkeypatch, sessions):
    request = ExperimentRequest(stock_code="600000", model="timesfm-2.5", kline_days=60)
    monkeypatch.setattr(exp, "SessionLocal", sessions)
    monkeypatch.setattr(exp, "KronosClient", Mock())
    monkeypatch.setattr(exp, "prepare_history", lambda *args: bars(60))
    result = {"forecast_target": "close", "predictions": [{"date": "2026-08-03", "close": 11.0}]}
    monkeypatch.setattr(exp, "infer", lambda *args: (result, {"input": {}, "output": result}))
    output = exp.forecast(request, "job", lambda: None, lambda _: None)
    assert "predicted_klines" not in output
    assert output["forecast_target"] == "close"
    assert output["predicted_prices"] == [11.0]
    assert output["kline_data"][0]["open"] == 10.0


def test_timesfm_remote_rejects_incorrect_input_scope(remote_service):
    payload = {
        "model": "timesfm-2.5", "bars": [{"close": 10}] * 60,
        "history_dates": list(bars(60)["date"]), "future_dates": [date(2026, 8, 3)], "prediction_days": 1,
    }
    assert len(remote_service.PredictRequest(**payload).bars) == 60
    with pytest.raises(ValueError, match="TimesFM accepts close only"):
        remote_service.PredictRequest(**{**payload, "bars": bars(60).drop(columns="date").to_dict("records")})
    with pytest.raises(ValueError):
        remote_service.PredictRequest(**{**payload, "model": "kronos-small"})


def test_kronos_only_server_keeps_working_and_marks_timesfm_unavailable(monkeypatch):
    from app.api import dl_prediction as api

    old_catalog = {
        "available": True, "source_revision": SOURCE_REVISION, "tokenizer_revision": TOKENIZER_REVISION,
        "models": [{"id": name, "revision": revision} for name, revision in MODEL_REVISIONS.items()
                   if name.startswith("kronos")],
    }
    monkeypatch.setattr(api.KronosClient, "status", lambda self: old_catalog)
    monkeypatch.setattr("app.config.settings.KRONOS_SERVICE_URL", "http://fixture")
    monkeypatch.setattr("app.config.settings.KRONOS_SERVICE_TOKEN", "private-fixture-token")
    catalog = api.models()
    available = {row["id"]: row["available"] for row in catalog["models"]}
    assert available == {"kronos-small": True, "kronos-base": True, "timesfm-2.5": False, "legacy": True}
