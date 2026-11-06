"""Opt-in real GPU and application acceptance for TimesFM 2.5."""

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
    forecast_cutoff, future_dates, prepare_history, validate_history,
)
from app.services.dl_prediction.remote import KronosClient  # noqa: E402
from app.services.market_data import load_bars, next_session  # noqa: E402
from verify_live import application_job  # noqa: E402


def verify_fills(backtest: dict) -> list[dict]:
    checked = []
    with SessionLocal() as db:
        frame, _ = load_bars(db, backtest["stock_code"], date.fromisoformat(backtest["start_date"]),
                             date.fromisoformat(backtest["end_date"]))
        for trade in backtest["trades"]:
            day = date.fromisoformat(trade["date"])
            anchor = next(item for item in backtest["anchors"] if next_session(
                db, backtest["stock_code"].split(".")[0], date.fromisoformat(item["anchor_date"]),
            ) == day)
            sign = 1 if trade["action"] == "BUY" else -1
            assert anchor["signal"] == sign
            opening = float(frame[frame["date"] == day].iloc[0]["open"])
            slip = backtest["execution_metadata"]["costs"]["slippage_rate"]
            assert trade["price"] == round(opening * (1 + sign * slip), 4)
            assert trade["quantity"] % 100 == 0
            checked.append({"signal_date": anchor["anchor_date"], "execution_date": trade["date"],
                            "action": trade["action"], "open": opening, "fill": trade["price"],
                            "quantity": trade["quantity"]})
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    client = KronosClient()
    end = forecast_cutoff()
    with SessionLocal() as db:
        history = validate_history(prepare_history(db, "sh.600000", end - timedelta(days=768), end, 256), 256)
        dates = future_dates(db, "sh.600000", history.iloc[-1]["date"], 30)
    request = {
        "model": "timesfm-2.5", "bars": history[["close"]].to_dict("records"),
        "history_dates": [str(day)[:10] for day in history["date"]],
    }
    report = {"model": "timesfm-2.5", "initial_status": client.status(), "benchmarks": [], "input": request}

    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for horizon in (5, 30):
        if horizon == 30 or client.status().get("loaded_model") == "timesfm-2.5":
            kronos = {
                **request, "model": "kronos-small", "prediction_days": 1, "future_dates": dates[:1],
                "bars": history[["open", "high", "low", "close", "volume", "amount"]].to_dict("records"),
            }
            report["kronos_switch_check"] = client.predict(kronos, lambda: None, lambda _: None)
        for run in ("cold", "hot"):
            payload = {**request, "prediction_days": horizon, "future_dates": dates[:horizon]}
            if horizon == 30 and run == "cold":
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(client.predict, payload, lambda: None, lambda _: None)
                    deadline = time.monotonic() + 30
                    while not client.status()["busy"] and time.monotonic() < deadline:
                        time.sleep(0.05)
                    report["concurrent_http_status"] = client._request("POST", "/v1/predict", json=payload).status_code
                    assert report["concurrent_http_status"] == 429
                    result = pending.result()
            else:
                result = client.predict(payload, lambda: None, lambda _: None)
            assert len(result["predictions"]) == horizon
            assert (result["load_ms"] > 0) == (run == "cold")
            assert all(set(row) == {"date", "close"} for row in result["predictions"])
            assert result["sampling"] is None and result["tokenizer_revision"] is None
            assert result["input_fields"] == result["output_fields"] == ["close"]
            assert client.status()["loaded_model"] == "timesfm-2.5"
            report["benchmarks"].append({"horizon": horizon, "run": run, **result})
            print(horizon, run, result["execution_time_ms"], "ms", result["peak_gpu_memory_mb"], "MiB", flush=True)
            save()
    report["one_session"] = client.predict(
        {**request, "prediction_days": 1, "future_dates": dates[:1]}, lambda: None, lambda _: None,
    )
    assert len(report["one_session"]["predictions"]) == 1
    with httpx.Client(base_url="http://127.0.0.1:8808", headers={"X-API-Key": settings.API_KEY},
                      timeout=30, trust_env=False) as app:
        catalog = app.get("/api/v1/dl/models").raise_for_status().json()
        assert next(row for row in catalog["models"] if row["id"] == "timesfm-2.5")["available"]
        experiment = {
            "stock_code": "sh.600000", "model": "timesfm-2.5", "kline_days": 256, "prediction_days": 30,
        }
        report["prediction_job"] = application_job(app, "predict", experiment)
        assert "predicted_klines" not in report["prediction_job"]["result"]
        report["backtest_job"] = application_job(app, "backtest", {
            **experiment, "start_date": "2026-09-01", "end_date": "2026-10-30", "initial_capital": 100000,
        })
    assert all(len(anchor["output"]["predictions"]) == 5
               for anchor in report["backtest_job"]["result"]["anchors"])
    report["verified_next_open_fills"] = verify_fills(report["backtest_job"]["result"])
    report["final_status"] = client.status()
    save()
    print("TimesFM live GPU, serialization, model switch and application acceptance complete", flush=True)


if __name__ == "__main__":
    main()
