# TimesFM 2.5 integration

The existing `backing-kronos` service now also supports `timesfm-2.5`.
It uses the official Apache-2.0 TimesFM 2.5 200M PyTorch weights. TimesFM 3.0
weights are not used. Kronos-small/base and the legacy predictor remain selectable.

## Fixed artifacts

- Weights: `google/timesfm-2.5-200m-pytorch`.
- Weight revision: `1d952420fba87f3c6dee4f240de0f1a0fbc790e3`.
- Weight SHA256: `2f776efe6245e42b24bc4153ffdf61810140210e4bd3b01fb21f7aa779ab6ce8`.
- Official source commit: `2011cfb9a483296b893571df050b5d25a26ef9cc`.
- Source distribution version: 2.0.2 (the exported model class is
  `TimesFM_2p5_200M_torch`, i.e. the 2.5 model).
- Remote source: `/home/yanxx/kronos-service/vendor/TimesFM`.
- Remote weights: `/home/yanxx/kronos-service/models/TimesFM-2.5-200M`.
- The original Apache license and official model card are preserved.

The source is imported from that pinned vendor directory, using the service's
existing torch/numpy/huggingface-hub/safetensors dependencies. No dependency
upgrade is required in the research environment, service environment or local
backend. The backend needs no torch or TimesFM installation.

## Behavior

TimesFM experiments use 60-512 completed daily closing prices (default 256) to
predict 1-30 future exchange sessions (default 5). They send only historical
`close` values and date arrays to the remote service. Future prices are never
inputs. Historical OHLCV/amount and its provenance remain available in local
results and the history chart.

Future rows contain only `date` and `close`. Results declare
`forecast_target=close`, `input_fields=["close"]`, `output_fields=["close"]`,
with pinned model/source revisions. No OHLCV/amount values, sample-path means or
confidence intervals are invented. The page retains the existing chart,
sliders/manual controls, progress, cancellation, session recovery and export,
and explains the close-only output.

The adapter disables `torch.compile`, normalizes inputs, enables flip invariance
and positive-input handling, and uses a single batch. The internal forecast
context is capped at 512 and the internal output patch is 128; only the requested
1-30 sessions are returned. Its exact configuration is recorded in every result.

Upstream defaults to `cuda:0` and the number of visible GPUs. The adapter sets the
module's device to the configured `cuda:1` and its device count to one **before**
loading weights. All three remote models share one inference lock and one
resident predictor. Switching models unloads the old one; ten idle minutes
release it. Existing GPU workloads are untouched.

Backtests reuse the same causal five-session anchor forecasts, shared next-open
execution, costs, lot sizes, T+1, participation limits and verified corporate
actions as Kronos. They record complete audits and fail explicitly on model
errors. These are retrospective pretrained evaluations with unknown training
overlap.

## Provision and verify

Copy `timesfm_adapter.py` and `provision_timesfm.py` alongside `service.py`.
The bootstrap now invokes the provisioner. It fetches only pinned official
artifacts, verifies the weight SHA256, records config/model checksums and extracts
the pinned source with path traversal checks.

When the GPU host cannot access the Internet, run the provisioner on a connected
machine with `KRONOS_ROOT` set to an absolute temporary directory. Transfer its
`models/TimesFM-2.5-200M`, `vendor/TimesFM` and `TIMESFM_REVISION.txt` to the service
root. The provisioner can then verify/reuse these files offline.

Retain `yanxx` ownership, apply the existing SELinux labels with `restorecon`,
and restart `backing-kronos` after any active inference has finished. The service
validates every model's config/weight checksums and source marker at startup.
No firewall change or new service token is needed.

The local backend continues using the existing backend-only
`KRONOS_SERVICE_URL` / `KRONOS_SERVICE_TOKEN`. Restart it to expose the expanded
catalog. During rollout an older Kronos-only remote remains usable; TimesFM is
reported unavailable until its pinned catalog entry appears.

From `backend/`:

```powershell
python ../deploy/kronos/healthcheck.py
python ../deploy/kronos/verify_timesfm.py --output ../deploy/kronos/timesfm-live-verification.json
pytest -q tests/test_kronos.py tests/test_dl_prediction.py
```

The opt-in verifier performs real GPU inference for 1, 5 and 30 sessions, cold/hot
measurements, model switching, concurrent-request rejection and authenticated
application prediction/backtest jobs. Its report contains public market inputs,
outputs, revisions and timings, never service credentials.

For this rollout, the previous remote entry point is retained as
`service.py.pre-timesfm-20261106`. To roll back, stop active new submissions,
restore that file to `service.py`, apply its ownership/SELinux context and restart
the service. The updated local backend will continue offering Kronos and mark
TimesFM unavailable. Selecting Kronos in the page also preserves its original
behavior without removing any saved results.

## Deployment verification (2026-11-06)

The running service on `172.22.226.86:8211` exposes all three pinned remote
models. It uses physical GPU 1, RTX 3090, UUID
`GPU-094a275d-4751-c559-fc17-b59d64a78039`. The service remained active with
zero automatic restarts after this deployment.

Real forecasts used 256 completed daily closes of `sh.600000`, ending
2026-11-05. Execution times include model loading on cold requests:

| Sessions | Cold execution | Hot execution | Peak allocated CUDA memory |
| --- | --- | --- | --- |
| 5 | 14,126.90 ms | 160.74 ms | 897.43 MiB |
| 30 | 4,723.71 ms | 356.86 ms | 906.55 MiB |

These are observed single-request measurements, not throughput guarantees.
The allocated-memory metric excludes CUDA context and other processes. One-day
forecasts, Kronos/TimesFM model switching and concurrent-request rejection
(HTTP 429) also passed.

An authenticated application prediction completed with 30 close-only rows.
The September 1 through October 30 retrospective backtest completed eight
five-session forecast anchors. All five fills were checked against the next
exchange session's raw open, configured slippage, signal direction and lot size.
The live browser submitted a prediction, rendered the results and restored them
after reload. No JavaScript errors or horizontal overflow were observed at
1440, 768 and 390 pixels.

Validation completed: backend Ruff, 819 passed/1 skipped backend tests,
frontend typecheck/lint/format/build, 212 frontend tests and six DL Playwright
tests. The machine-readable inputs, forecasts, timings, job results, fill checks
and browser evidence are in `timesfm-live-verification.json`. Screenshots are
`timesfm-page-1440.png`, `timesfm-page-768.png` and `timesfm-page-390.png`.
