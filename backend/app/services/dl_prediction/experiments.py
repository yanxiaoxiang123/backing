"""Durable remote forecasts and causal rolling backtests using the shared engine."""

from dataclasses import asdict
from datetime import date, datetime, time as daytime, timedelta, timezone
import json
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.config import SessionLocal, settings
from app.models.models import JobDbRecord
from app.services.backtest_simulation import ExecutionCosts, daily_metrics, simulate_daily
from app.services.corporate_actions import execution_actions
from app.services.dl_prediction.contracts import BacktestExperimentRequest, ExperimentRequest
from app.services.dl_prediction.remote import KronosClient, MODEL_REVISIONS, source_revision
from app.services.job_store import job_store
from app.services.market_data import digest, load_bars, next_session, open_sessions
from app.services.market_data_sync import completed_end, sync_calendar, sync_history, sync_metadata
from app.services.market_research_prices import load_research_bars
from app.services.tasks import TaskCancelledError, register_runner


def check_job(job_id: str, started: float) -> None:
    record = job_store.get(job_id)
    if record is None or record.status in {"failed", "cancelled"}:
        raise TaskCancelledError("Experiment cancelled")
    if time.monotonic() - started > settings.KRONOS_JOB_TIMEOUT_S:
        raise TimeoutError("DL 任务超过最长执行时间")


def update_job(job_id: str, **values) -> None:
    # Cancellation is terminal, including when it races with final GPU output.
    with SessionLocal() as db:
        count = db.query(JobDbRecord).filter(
            JobDbRecord.id == job_id, JobDbRecord.status.in_(["pending", "running"]),
        ).update({**values, "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)},
                 synchronize_session=False)
        db.commit()
    if not count:
        raise TaskCancelledError("Experiment cancelled")


def validate_history(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    if len(frame) < count:
        raise ValueError(f"历史行情不足：需要 {count} 根，实际 {len(frame)} 根")
    history = frame.tail(count).copy().reset_index(drop=True)
    days = pd.to_datetime(history["date"])
    if days.duplicated().any() or not days.is_monotonic_increasing:
        raise ValueError("历史日期必须唯一且递增")
    values = history[["open", "high", "low", "close", "volume", "amount"]].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values[:, :4] <= 0).any()
            or (values[:, 4:] < 0).any()
            or (values[:, 2] > values[:, [0, 3]].min(axis=1)).any()
            or (values[:, 1] < values[:, [0, 3]].max(axis=1)).any()):
        raise ValueError("原始 OHLCV/成交额缺失或不合法；请补齐真实行情")
    return history


def prepare_history(db, code: str, start: date, end: date, count: int) -> pd.DataFrame:
    sync_calendar(db, start, end)
    frame, _ = load_bars(db, code, start, end)
    begin = frame.iloc[-count]["date"] if len(frame) >= count else start
    try:
        return load_research_bars(db, code, begin, end, source="raw")
    except ValueError:
        report = sync_history(db, [code], start, end, rate_limit_s=0.1)
        if not report["success"]:
            errors = "; ".join(row["error"] for row in report["errors"])
            raise ValueError("研究行情补齐失败：" + errors)
        return load_research_bars(db, code, start, end, source="raw")


def future_dates(db, code: str, after: date, count: int) -> list[str]:
    dates = []
    day = after
    for _ in range(count):
        try:
            day = next_session(db, code.split(".")[0], day)
        except ValueError:
            # Do not request a whole future year when only a few sessions are needed.
            sync_calendar(db, day, day + timedelta(days=14))
            day = next_session(db, code.split(".")[0], day)
        dates.append(day.isoformat())
    return dates


def forecast_cutoff(now: datetime | None = None) -> date:
    # BaoStock publishes daily bars at 17:30, after the exchange close.
    local = (now or datetime.now(ZoneInfo("Asia/Shanghai"))).astimezone(ZoneInfo("Asia/Shanghai"))
    if local.time() < daytime(17, 30):
        return local.date() - timedelta(days=1)
    return completed_end(local)


def infer(client, db, request: ExperimentRequest, history: pd.DataFrame,
          horizon: int, job_id: str, check, progress) -> tuple[dict, dict]:
    history = validate_history(history, request.kline_days)
    fields = ["close"] if request.model == "timesfm-2.5" else ["open", "high", "low", "close", "volume", "amount"]
    payload = {
        "model": request.model,
        "bars": history[fields].to_dict("records"),
        "history_dates": [str(day)[:10] for day in history["date"]],
        "future_dates": future_dates(db, request.stock_code, pd.Timestamp(history.iloc[-1]["date"]).date(), horizon),
        "prediction_days": horizon, "request_id": job_id,
    }
    result = client.predict(payload, check, progress)
    rows = result.get("predictions", [])
    if (len(rows) != horizon
            or [row.get("date") for row in rows] != payload["future_dates"]
            or any(not np.isfinite(row.get("close", np.nan)) or row["close"] <= 0 for row in rows)):
        raise ValueError("远端预测日期、数量或价格不合法")
    audit = {"input": payload, "input_sha256": digest(payload), "output": result}
    return result, audit


def forecast(request: ExperimentRequest, job_id: str, check, progress) -> dict:
    client = KronosClient()
    end = forecast_cutoff()
    with SessionLocal() as db:
        progress("准备行情")
        frame = prepare_history(db, request.stock_code, end - timedelta(days=request.kline_days * 3), end,
                                request.kline_days)
        check()
        history = validate_history(frame, request.kline_days)
        result, audit = infer(client, db, request, history, request.prediction_days, job_id, check, progress)
        return {
            "stock_code": request.stock_code, "model": request.model,
            "current_price": float(history.iloc[-1]["close"]),
            "last_date": str(history.iloc[-1]["date"])[:10],
            "prediction_dates": [row["date"] for row in result["predictions"]],
            "predicted_prices": [row["close"] for row in result["predictions"]],
            "kline_data": [{**row, "date": str(row["date"])[:10]} for row in
                           json.loads(history.to_json(orient="records", date_format="iso"))],
            **({"predicted_klines": result["predictions"]} if request.model != "timesfm-2.5" else {}),
            "forecast_target": result.get("forecast_target", "ohlcv_amount"), "model_metadata": {
                key: value for key, value in result.items() if key != "predictions"
            }, "data_provenance": frame.attrs.get("provenance"),
            "input_start": str(history.iloc[0]["date"])[:10], "audit": audit,
            "volume_unit": "shares", "amount_unit": "CNY",
            "data_cutoff_policy": "baostock_daily_1730_Asia_Shanghai",
        }


def rolling_backtest(request: BacktestExperimentRequest, job_id: str, check, progress) -> dict:
    if request.end_date > completed_end():
        raise ValueError("回测结束日期不能晚于已完成交易日")
    client = KronosClient()
    with SessionLocal() as db:
        progress("准备行情")
        # Load warmup independently of the requested execution interval.
        warm_start = request.start_date - timedelta(days=request.kline_days * 3)
        prepare_history(db, request.stock_code, warm_start, request.start_date, request.kline_days)
        sync_calendar(db, request.start_date, request.end_date)
        try:
            frame = load_research_bars(db, request.stock_code, warm_start, request.end_date, source="raw")
        except ValueError:
            report = sync_history(db, [request.stock_code], warm_start, request.end_date, rate_limit_s=0.1)
            if not report["success"]:
                raise ValueError("回测行情补齐失败：" + json.dumps(report["errors"], ensure_ascii=False))
            frame = load_research_bars(db, request.stock_code, warm_start, request.end_date, source="raw")
        try:
            actions, action_provenance = execution_actions(db, request.stock_code, request.start_date, request.end_date)
        except ValueError:
            sync_metadata(db, request.stock_code, request.start_date, request.end_date, rate_limit_s=0.1)
            actions, action_provenance = execution_actions(db, request.stock_code, request.start_date, request.end_date)
        check()
        execution = frame[frame["date"] >= request.start_date].copy()
        if execution.empty:
            raise ValueError("研究区间没有可用日线")
        sessions = open_sessions(db, request.stock_code.split(".")[0], request.start_date, request.end_date)
        execution["signal"] = 0
        anchors = [day for i, day in enumerate(sessions) if i % 5 == 0 and day in set(execution["date"])]
        audits = []
        saved = job_store.get(job_id)
        cached = (saved.result or {}).get("anchors", []) if saved else []
        for i, day in enumerate(anchors):
            check()
            history = validate_history(frame[frame["date"] <= day], request.kline_days)
            key = digest({"model": request.model, "revision": MODEL_REVISIONS[request.model],
                          "source_revision": source_revision(request.model),
                          "history": json.loads(history.to_json(orient="records", date_format="iso"))})
            previous = next((item for item in cached if item.get("cache_key") == key), None)
            if previous:
                audit = previous
                result = audit["output"]
            else:
                result, audit = infer(
                    client, db, request, history, 5, job_id, check,
                    lambda message: progress(f"回测 {i + 1}/{len(anchors)} · {message}"),
                )
                audit["cache_key"] = key
            price = float(history.iloc[-1]["close"])
            signal = 1 if result["predictions"][-1]["close"] > price else -1
            execution.loc[execution["date"] == day, "signal"] = signal
            audits.append({**audit, "anchor_date": day.isoformat(), "signal": signal})
            update_job(job_id, progress=0.1 + 0.8 * (i + 1) / max(1, len(anchors)),
                       message=f"回测完成 {i + 1}/{len(anchors)} 个锚点", result={"anchors": audits})
        check()
        costs = ExecutionCosts()
        income = []
        trades, final, curve = simulate_daily(
            execution, request.initial_capital, costs, session_dates=[day.isoformat() for day in sessions],
            corporate_actions=actions, action_ledger=income,
        )
        metrics = daily_metrics(trades, request.initial_capital, final, curve, corporate_income=income)
        closes = dict(zip(execution["date"], execution["close"], strict=True))
        last_close = float(execution.iloc[0]["close"])
        marks = []
        for point in curve:
            last_close = float(closes.get(point.date, last_close))
            marks.append(last_close)
        return {
            "stock_code": request.stock_code, "model": request.model,
            "model_revision": MODEL_REVISIONS[request.model],
            "total_return": metrics.total_return, "annualized_return": metrics.annual_return,
            "sharpe_ratio": metrics.sharpe_ratio, "max_drawdown": metrics.max_drawdown,
            "win_rate": metrics.win_rate, "total_trades": metrics.total_trades,
            "trades": [{**asdict(trade), "date": trade.date.isoformat(),
                        "action": trade.action.upper()} for trade in trades],
            "portfolio_values": [point.total_value for point in curve],
            "dates": [point.date.isoformat() for point in curve], "close_prices": marks,
            "initial_capital": request.initial_capital, "final_capital": final,
            "start_date": request.start_date.isoformat(), "end_date": request.end_date.isoformat(),
            "anchors": audits, "execution_metadata": {
                "engine_version": "daily-next-open-v3", "costs": asdict(costs),
                "corporate_actions": actions, "corporate_action_provenance": action_provenance,
                "corporate_income": income, "session_dates": [day.isoformat() for day in sessions],
                "signals": execution[["date", "signal"]].astype(str).to_dict("records"),
                "data_provenance": frame.attrs.get("provenance"),
                "signal_interval": 5, "prediction_horizon": 5,
                "limitations": ["retrospective_pretrained_evaluation", "pretraining_overlap_unknown",
                                "raw_unadjusted_forecast_context", *action_provenance["limitations"]],
            },
        }


def _execute_experiment(job_id: str, payload: dict, backtest: bool) -> None:
    started = time.monotonic()

    def check() -> None:
        check_job(job_id, started)

    def progress(message: str) -> None:
        check()
        update_job(job_id, message=message)
    check()
    if payload["model"] == "legacy":
        from app.services.dl_prediction.backtest import DLBacktester
        from app.services.dl_prediction.predictor import DLPredictor
        from app.services.baostock_service import BaostockService

        progress("现有预测器运行中")
        if backtest:
            data = DLBacktester().run_backtest(
                payload["stock_code"], payload["start_date"], payload["end_date"], payload["initial_capital"],
            )
        else:
            end = completed_end()
            frame = BaostockService().get_daily_kline(
                payload["stock_code"], (end - timedelta(days=730)).isoformat(), end.isoformat(),
            )
            if frame is None or frame.empty:
                raise ValueError("现有预测器未找到行情")
            data = DLPredictor().predict(payload["stock_code"], frame.tail(payload["kline_days"]).to_dict("records"))
        data["model"] = "legacy"
        data["limitations"] = ["legacy_predictor_may_use_technical_fallback"]
    else:
        request = (BacktestExperimentRequest if backtest else ExperimentRequest).model_validate(payload)
        data = rolling_backtest(request, job_id, check, progress) if backtest else forecast(
            request, job_id, check, progress,
        )
    check()
    data["experiment"] = payload
    data["execution_time_ms"] = round((time.monotonic() - started) * 1000, 2)
    update_job(job_id, status="completed", progress=1, message="实验完成",
               result={"success": True, "data": data}, error=None)


def run_experiment(job_id: str, payload: dict, backtest: bool) -> None:
    try:
        _execute_experiment(job_id, payload, backtest)
    except Exception:
        # A transport failure after cancellation must not requeue the cancelled job.
        check_job(job_id, time.monotonic())
        raise


@register_runner("dl_predict")
def run_predict(job_id: str, payload: dict) -> None:
    run_experiment(job_id, payload, False)


@register_runner("dl_backtest")
def run_backtest(job_id: str, payload: dict) -> None:
    run_experiment(job_id, payload, True)
