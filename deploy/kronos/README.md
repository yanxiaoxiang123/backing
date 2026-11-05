# Remote Kronos inference

The DL page submits durable jobs to the application backend. The backend prepares
versioned raw OHLCV/amount data and sends only that window and verified future
session dates to the private GPU service. The GPU service never connects to the
application database. No OpenAI/DeepSeek API is needed.

## Runtime and weights

- Host: `172.22.226.86`, service root: `/home/yanxx/kronos-service`.
- Runtime user: `yanxx`; systemd unit: `backing-kronos`; address: port `8211`.
- Default device: `cuda:1`; one process, one concurrent inference, one loaded
  model. A model switch unloads the previous model. Idle weights expire after
  600 seconds. Existing GPU workloads are never stopped.
- Source revision: `67b630e67f6a18c9e9be918d9b4337c960db1e9a`.
- Small: `901c26c1332695a2a8f243eb2f37243a37bea320`.
- Base: `2b554741eca47781b64468546e77fef3e85130e6`.
- Tokenizer: `0e0117387f39004a9016484a186a908917e22426`.
- Official MIT license is preserved in `vendor/Kronos/LICENSE`.

`bootstrap.sh` copies the verified small/base/tokenizer files from the existing
research installation, exports pinned upstream source, and creates a separate
CUDA environment. It does not install into the existing research environment.
Runtime startup verifies the weights/config checksums against the copied revision
manifests. Weights are loaded locally with Hugging Face offline mode.
`requirements.lock` records the installed runtime dependency closure. The PyPI
torch package metadata is `2.9.1`; its verified runtime identifies as
`2.9.1+cu128`, which is checked at service startup. Research packages are not
included in the runtime lock and the service imports only pinned official Kronos.

Provision `service.py`, `requirements.txt`, `lock_runtime.py`, `bootstrap.sh` and the unit file into
the service directory, then run `bash bootstrap.sh` as root. A fresh host without
the existing research installation must first download the three official model
repositories at the revisions above and create their SHA256 manifests. Do not use
an arbitrary PyPI package named `kronos`.

Create `service.env` (owner `yanxx`, mode `0600`):

```dotenv
KRONOS_ROOT=/home/yanxx/kronos-service
KRONOS_DEVICE=cuda:1
KRONOS_IDLE_SECONDS=600
KRONOS_SERVICE_TOKEN=<unique random service token>
```

Install the unit into `/etc/systemd/system/`, reload systemd, and enable/start
`backing-kronos`. Permit TCP 8211 only from the trusted internal network. All
service endpoints require `Authorization: Bearer <service token>`. This deployment
uses internal HTTP as selected by the owner; a future network exposure change
requires TLS termination or an SSH tunnel.

On this Rocky Linux host, SELinux remains enforcing. Label this service directory
for systemd, including its restricted environment file:

```bash
semanage fcontext -a -t usr_t '/home/yanxx/kronos-service(/.*)?'
semanage fcontext -a -t bin_t '/home/yanxx/kronos-service/.venv/bin(/.*)?'
semanage fcontext -a -t etc_t /home/yanxx/kronos-service/service.env
restorecon -R /home/yanxx/kronos-service
```

The deployed firewalld rule allows IPv4 `172.16.0.0/12` to TCP 8211, with the
former unrestricted `8211/tcp` rule removed in both runtime and permanent
configuration. Inspect with `firewall-cmd --list-rich-rules`. Other ports and GPU
workloads are unchanged.

Configure the same token in the application backend's ignored `.env`:

```dotenv
KRONOS_SERVICE_URL=http://172.22.226.86:8211
KRONOS_SERVICE_TOKEN=<same service token>
KRONOS_REQUEST_TIMEOUT_S=180
KRONOS_JOB_TIMEOUT_S=3600
```

Restart the backend and any Arq worker after changing settings. Never put this
token in `VITE_*`, frontend storage, command history, repository files or logs.
The source backend does not need GPU/PyTorch/Hugging Face dependency changes.

## Interfaces and lifecycle

- Remote `GET /v1/status`: model revisions, device, loaded model, busy/phase.
- Remote `POST /v1/predict`: allowlisted `model`, 60–512 `bars` aligned to
  `history_dates`, 1–30 `future_dates`, `prediction_days`, optional `request_id`.
  OHLC prices must be finite and positive; volume is shares, amount is CNY.
  Sampling is fixed: temperature 1, top-p 0.9, three paths averaged, seed 2026.
  Raw decoded invalid OHLC bars are retained with `ohlc_valid=false`; nonfinite
  output or nonpositive prices fail the request.
- Backend `GET /api/v1/dl/models`: authenticated catalog and remote status.
- Backend `POST /api/v1/dl/{predict|backtest}/submit`: HTTP 202 with `job_id`.
  Body: `model`, `stock_code`, `kline_days`, `prediction_days`, plus backtest
  `start_date`, `end_date`, `initial_capital`. `Idempotency-Key` deduplicates a
  submission; conflicting payloads return 409.
- Existing `/api/v1/jobs/{job_id}` and its `/cancel` endpoint provide lifecycle.
  Prediction/backtest results, model metadata, input/output audits and rolling
  checkpoints are persisted in the existing jobs table. No migration is added.
- Legacy synchronous `/dl/predict` and `/dl/backtest` remain available. The
  historical fake +1% fallback is removed. Legacy forecasts expose technical
  fallback explicitly in new asynchronous results.

The page stores the current job ID (or in-flight idempotency key) in session
storage and resumes polling after refresh. Cancelling a task prevents the current
GPU result from being committed and stops subsequent anchors; an already-running
remote kernel finishes normally. It does not interrupt another user's GPU job.
Transient remote connection/timeouts use the existing bounded job retries.
Busy GPUs return 429 and are retried within the per-request timeout. OOM, model
failure, version mismatch and invalid output fail explicitly without substitution.

## Data and historical experiments

Only completed daily bars are used. New forecasts wait for the BaoStock 17:30
Asia/Shanghai daily publication batch before including today's bar. Before that
cutoff they use the preceding calendar day's completed history, with the actual
last exchange session shown in the result. Missing bars inside that interval
still fail validation after synchronization. The backend checks versioned raw history,
fills missing data via the existing provider, and validates every selected input.
Future dates come from the stored exchange calendar; calendar gaps are fetched
in bounded increments. Missing calendars never fall back to weekdays.
The asynchronous experiments currently accept Shanghai/Shenzhen securities,
matching the project's verified exchange-calendar coverage.

Kronos backtests load the warmup before the requested period. Every fifth exchange
session (if a real bar exists) forecasts five future sessions using only the
history through that anchor close. Forecast fifth close above current close
produces buy, otherwise sell; intervening sessions have no new order. Orders run
once at the next open using the shared daily engine, fees, slippage, lot sizing,
participation constraints, T+1 and verified corporate action accounting.

Saved audits contain each input/output, versions and settings; completed anchors
are reused after retry only when their model revision and historical input match.
The input context is unadjusted raw data, so corporate-action price jumps may
affect model forecasts. Corporate actions are accounted for in execution. These
are retrospective evaluations of pretrained models with unknown training overlap;
they are not evidence of independent out-of-sample trading performance.

## Verification and operations

From the repository root, with backend environment activated and `.env` resolved
from `backend/`, run:

```powershell
cd backend
python ../deploy/kronos/healthcheck.py
pytest -q tests/test_kronos.py tests/test_dl_prediction.py
```

On the server:

```bash
systemctl status backing-kronos --no-pager
journalctl -u backing-kronos -n 50 --no-pager
nvidia-smi
```

The health script reads credentials from settings and prints only nonsecret
status. Unit tests use isolated databases and fake remote calls; no model download
or GPU is required in CI. Live verification must separately cover both models,
256-bar inputs and 5-/30-session forecasts, cold/hot timing and peak allocated
GPU memory, plus an authenticated page prediction and a short historical backtest.

Rollback: select the existing predictor, then stop/disable `backing-kronos`.
Saved job results and existing research projects are preserved.

See `VERIFICATION.md` for the completed live acceptance, `live-verification.json`
for machine-readable results and model samples, and `versions.json` for the
weight/config SHA256 manifest. During an active inference the backend polls the
authenticated remote phase to distinguish model loading from inference.
