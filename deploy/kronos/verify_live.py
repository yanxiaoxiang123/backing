"""Opt-in GPU and application acceptance checks; run from backend with its env."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import time

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import SessionLocal, settings  # noqa: E402
from app.services.dl_prediction.experiments import (  # noqa: E402
    forecast_cutoff,
    future_dates,
    prepare_history,
    validate_history,
)
from app.services.dl_prediction.remote import KronosClient  # noqa: E402
from app.services.market_data import load_bars, next_session  # noqa: E402


def application_job(client, kind, payload):
    response = client.post(f"/api/v1/dl/{kind}/submit", json=payload)
    response.raise_for_status()
    job_id = response.json()["job_id"]
    deadline = time.monotonic() + settings.KRONOS_JOB_TIMEOUT_S
    while time.monotonic() < deadline:
        state = client.get(f"/api/v1/jobs/{job_id}").raise_for_status().json()
        if state["status"] == "completed":
            assert state["result"]["success"], state.get("error")
            return {"job_id": job_id, "result": state["result"]["data"]}
        if state["status"] == "failed":
            raise RuntimeError(f"Application job failed: {state.get('error')}")
        time.sleep(1)
    raise TimeoutError("Application acceptance job timed out")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--application-url", default="http://127.0.0.1:8808")
    parser.add_argument("--stock", default="sh.600000")
    args = parser.parse_args()
    client = KronosClient()
    end = forecast_cutoff()
    with SessionLocal() as db:
        frame = prepare_history(db, args.stock, end - timedelta(days=768), end, 256)
        history = validate_history(frame, 256)
        dates = future_dates(db, args.stock, history.iloc[-1]["date"], 30)
    base = {
        "bars": history[["open", "high", "low", "close", "volume", "amount"]].to_dict("records"),
        "history_dates": [str(day)[:10] for day in history["date"]],
    }
    report = {
        "stock": args.stock,
        "history_start": base["history_dates"][0],
        "history_end": base["history_dates"][-1],
        "initial_status": client.status(),
        "benchmarks": [],
    }
    # Switching sizes makes each first call cold with respect to resident weights.
    for horizon in (5, 30):
        for model in ("kronos-small", "kronos-base"):
            for run in ("cold", "hot"):
                payload = {**base, "model": model, "prediction_days": horizon, "future_dates": dates[:horizon]}
                result = client.predict(payload, lambda: None, lambda _: None)
                assert len(result["predictions"]) == horizon
                assert client.status()["loaded_model"] == model
                report["benchmarks"].append({"horizon": horizon, "run": run, **result})
                print(model, horizon, run, result["execution_time_ms"], "ms", flush=True)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # A second HTTP call must be rejected while the first owns the inference lock.
    payload = {**base, "model": "kronos-base", "prediction_days": 30, "future_dates": dates}
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(client._request, "POST", "/v1/predict", json=payload)
        deadline = time.monotonic() + 20
        while not client.status()["busy"] and time.monotonic() < deadline:
            time.sleep(0.02)
        report["concurrent_http_status"] = client._request("POST", "/v1/predict", json=payload).status_code
        assert report["concurrent_http_status"] == 429
        running.result().raise_for_status()
    report["unauthenticated_http_status"] = httpx.get(
        client.base_url + "/v1/status", trust_env=False, timeout=5,
    ).status_code
    assert report["unauthenticated_http_status"] == 401
    with httpx.Client(base_url=args.application_url, headers={"X-API-Key": settings.API_KEY},
                      timeout=30, trust_env=False) as local:
        request = {"stock_code": args.stock, "model": "kronos-small", "kline_days": 256, "prediction_days": 5}
        report["prediction_job"] = application_job(local, "predict", request)
        report["backtest_job"] = application_job(local, "backtest", {
            **request, "start_date": "2026-09-01", "end_date": "2026-10-30", "initial_capital": 100000,
        })
    backtest = report["backtest_job"]["result"]
    fills = []
    with SessionLocal() as db:
        bars, _ = load_bars(db, args.stock, date(2026, 9, 1), date(2026, 10, 30))
        for trade in backtest["trades"]:
            execution_date = date.fromisoformat(trade["date"])
            matching = [anchor for anchor in backtest["anchors"] if
                        next_session(db, args.stock.split(".")[0], date.fromisoformat(anchor["anchor_date"]))
                        == execution_date]
            assert matching and matching[0]["signal"] == (1 if trade["action"] == "BUY" else -1)
            opening = float(bars[bars["date"] == execution_date].iloc[0]["open"])
            slip = backtest["execution_metadata"]["costs"]["slippage_rate"]
            expected = round(opening * (1 + slip if trade["action"] == "BUY" else 1 - slip), 4)
            assert trade["price"] == expected
            assert trade["quantity"] % 100 == 0
            fills.append({"signal_date": matching[0]["anchor_date"], "execution_date": trade["date"],
                          "open": opening, "fill": trade["price"], "quantity": trade["quantity"]})
    report["verified_next_open_fills"] = fills
    report["final_status"] = client.status()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Live acceptance complete", flush=True)


if __name__ == "__main__":
    main()
