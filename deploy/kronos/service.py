"""Private, single-GPU inference service for pinned official Kronos weights."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import secrets
import sys
import threading
import time
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator

REVISION = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"
MODEL_REVISIONS = {
    "kronos-small": "901c26c1332695a2a8f243eb2f37243a37bea320",
    "kronos-base": "2b554741eca47781b64468546e77fef3e85130e6",
}
TOKENIZER_REVISION = "0e0117387f39004a9016484a186a908917e22426"
FIELDS = ["open", "high", "low", "close", "volume", "amount"]
ROOT = Path(os.environ.get("KRONOS_ROOT", Path(__file__).resolve().parent))
DEVICE = os.environ.get("KRONOS_DEVICE", "cuda:1")
IDLE_SECONDS = int(os.environ.get("KRONOS_IDLE_SECONDS", "600"))
bearer = HTTPBearer(auto_error=False)


def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    expected = os.environ.get("KRONOS_SERVICE_TOKEN", "")
    if not expected or not credentials or not secrets.compare_digest(credentials.credentials, expected):
        raise HTTPException(401, detail={"code": "unauthorized", "message": "Service authentication failed"})


class Bar(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    amount: float = Field(ge=0)

    @model_validator(mode="after")
    def consistent_ohlc(self):
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("Inconsistent OHLC range")
        return self


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: Literal["kronos-small", "kronos-base"]
    bars: list[Bar] = Field(min_length=60, max_length=512)
    history_dates: list[date] = Field(min_length=60, max_length=512)
    future_dates: list[date] = Field(min_length=1, max_length=30)
    prediction_days: int = Field(default=5, ge=1, le=30)
    request_id: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def aligned_dates(self):
        if len(self.history_dates) != len(self.bars) or len(self.future_dates) != self.prediction_days:
            raise ValueError("Dates must align with history and prediction length")
        all_dates = self.history_dates + self.future_dates
        if all_dates != sorted(set(all_dates)):
            raise ValueError("Dates must be unique, increasing, and future must follow history")
        return self


class Runtime:
    def __init__(self):
        self.lock = threading.Lock()
        self.predictor = None
        self.loaded_model = None
        self.phase = "idle"
        self.last_used = 0.0
        self.error = None
        self.identities: dict = {}

    def verify(self):
        import torch

        if torch.__version__ != "2.9.1+cu128" or not torch.cuda.is_available():
            raise RuntimeError("The verified torch 2.9.1+cu128 CUDA runtime is required")
        torch.cuda.get_device_properties(DEVICE)
        for name, revision in {
            "Kronos-small": MODEL_REVISIONS["kronos-small"],
            "Kronos-base": MODEL_REVISIONS["kronos-base"],
            "Kronos-Tokenizer-base": TOKENIZER_REVISION,
        }.items():
            directory = ROOT / "models" / name
            manifest = json.loads((directory / "revision.json").read_text())
            if manifest["revision"] != revision:
                raise ValueError(f"Unexpected model revision: {name}")
            for filename in ("config.json", "model.safetensors"):
                checksum = hashlib.sha256()
                with (directory / filename).open("rb") as stream:
                    for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                        checksum.update(block)
                if checksum.hexdigest() != manifest["files"][filename]:
                    raise ValueError(f"Weight checksum mismatch: {name}/{filename}")
            self.identities[name] = manifest
        if (ROOT / "UPSTREAM_REVISION.txt").read_text().strip() != REVISION:
            raise ValueError("Unexpected upstream source revision")

    def unload(self):
        self.predictor = None
        self.loaded_model = None
        gc.collect()
        import torch

        if torch.cuda.is_available():
            with torch.cuda.device(DEVICE):
                torch.cuda.empty_cache()

    def expire(self):
        if self.predictor is None or time.monotonic() - self.last_used < IDLE_SECONDS:
            return
        if self.lock.acquire(blocking=False):
            try:
                if self.predictor is not None and time.monotonic() - self.last_used >= IDLE_SECONDS:
                    self.unload()
            finally:
                self.lock.release()

    def run(self, request: PredictRequest) -> dict:
        if not self.lock.acquire(blocking=False):
            raise HTTPException(429, detail={"code": "gpu_busy", "message": "GPU is processing another request"},
                                headers={"Retry-After": "2"})
        started = time.monotonic()
        loaded_ms = 0.0
        try:
            import numpy as np
            import pandas as pd
            import torch

            self.error = None
            if self.loaded_model != request.model:
                self.phase = "loading_model"
                self.unload()
                if torch.cuda.is_available():
                    torch.cuda.reset_peak_memory_stats(DEVICE)
                load_started = time.monotonic()
                sys.path.insert(0, str(ROOT / "vendor" / "Kronos"))
                from model import Kronos, KronosPredictor, KronosTokenizer

                tokenizer = KronosTokenizer.from_pretrained(str(ROOT / "models" / "Kronos-Tokenizer-base"))
                model = Kronos.from_pretrained(str(ROOT / "models" / request.model.replace("kronos", "Kronos")))
                tokenizer.requires_grad_(False).eval()
                model.requires_grad_(False).eval()
                self.predictor = KronosPredictor(model, tokenizer, device=DEVICE, max_context=512)
                self.loaded_model = request.model
                loaded_ms = (time.monotonic() - load_started) * 1000
            elif torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats(DEVICE)
            self.phase = "inference"
            random.seed(2026)
            np.random.seed(2026)
            torch.manual_seed(2026)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(2026)
            with torch.inference_mode():
                frame = self.predictor.predict(
                    df=pd.DataFrame([bar.model_dump() for bar in request.bars], columns=FIELDS),
                    x_timestamp=pd.Series(pd.to_datetime(request.history_dates)),
                    y_timestamp=pd.Series(pd.to_datetime(request.future_dates)),
                    pred_len=request.prediction_days, T=1.0, top_p=0.9, sample_count=3, verbose=False,
                )
            rows = []
            for day, values in zip(request.future_dates, frame[FIELDS].to_numpy().tolist(), strict=True):
                if not all(math.isfinite(float(value)) for value in values) or min(values[:4]) <= 0:
                    raise ValueError("Model generated nonfinite or nonpositive prices")
                row = dict(zip(FIELDS, map(float, values), strict=True))
                row.update(date=day.isoformat(), ohlc_valid=(
                    row["low"] <= min(row["open"], row["close"])
                    and row["high"] >= max(row["open"], row["close"])
                    and row["volume"] >= 0 and row["amount"] >= 0
                ))
                rows.append(row)
            return {
                "predictions": rows, "model": request.model,
                "model_revision": MODEL_REVISIONS[request.model],
                "tokenizer_revision": TOKENIZER_REVISION, "source_revision": REVISION,
                "sampling": {"temperature": 1.0, "top_p": 0.9, "sample_count": 3, "seed": 2026},
                "device": DEVICE, "load_ms": round(loaded_ms, 2),
                "execution_time_ms": round((time.monotonic() - started) * 1000, 2),
                "peak_gpu_memory_mb": round(torch.cuda.max_memory_allocated(DEVICE) / 1024 ** 2, 2)
                if torch.cuda.is_available() else 0,
                "request_id": request.request_id,
            }
        except HTTPException:
            raise
        except Exception as exc:
            import torch

            if isinstance(exc, torch.cuda.OutOfMemoryError):
                self.unload()
                code, message = "gpu_oom", "GPU memory is insufficient; release capacity and retry"
            elif isinstance(exc, (FileNotFoundError, ImportError, OSError)):
                self.unload()
                code, message = "model_unavailable", "Pinned model files or runtime are unavailable"
            else:
                code, message = "inference_failed", "Kronos inference failed; no substitute prediction was generated"
            self.error = code
            raise HTTPException(503 if code != "inference_failed" else 502,
                                detail={"code": code, "message": message}) from exc
        finally:
            self.last_used = time.monotonic()
            self.phase = "idle"
            self.lock.release()


runtime = Runtime()


@asynccontextmanager
async def lifespan(_app):
    if not os.environ.get("KRONOS_SERVICE_TOKEN"):
        raise RuntimeError("KRONOS_SERVICE_TOKEN is required")
    runtime.verify()

    async def idle_release():
        while True:
            await asyncio.sleep(30)
            await asyncio.to_thread(runtime.expire)

    task = asyncio.create_task(idle_release())
    yield
    task.cancel()


app = FastAPI(title="Backing Kronos", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/v1/status", dependencies=[Depends(authorize)])
def status():
    return {
        "available": True, "device": DEVICE, "loaded_model": runtime.loaded_model,
        "busy": runtime.lock.locked(), "phase": runtime.phase, "error": runtime.error,
        "source_revision": REVISION, "tokenizer_revision": TOKENIZER_REVISION,
        "models": [{"id": name, "revision": revision, "max_context": 512}
                   for name, revision in MODEL_REVISIONS.items()],
    }


@app.post("/v1/predict", dependencies=[Depends(authorize)])
def predict(request: PredictRequest):
    return runtime.run(request)
