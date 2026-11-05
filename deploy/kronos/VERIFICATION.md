# Live deployment verification - 2026-11-04

## Deployment

- Service: `backing-kronos`, enabled and running as `yanxx`.
- Endpoint: `172.22.226.86:8211`, device `cuda:1`, one uvicorn worker.
- Isolated Python 3.10.19, torch runtime `2.9.1+cu128`.
- Source, official model revisions and config/weight SHA256 values:
  `versions.json`. Installed runtime dependency closure: `requirements.lock`.
- Authentication required on both remote endpoints; unauthenticated status
  returned 401. A simultaneous inference request returned 429.
- Model switches unloaded the preceding model. Status always reported one
  loaded model. After ten idle minutes, live status reported `loaded_model=null`.
- SELinux remains enforcing. Runtime and permanent firewalld configuration allow
  TCP 8211 from `172.16.0.0/12`; the unrestricted port rule was removed.

## Real GPU measurements

256 raw daily bars for `sh.600000`, 2025-10-15 through 2026-11-03. Future dates
were taken from verified exchange sessions. Temperature 1, top-p 0.9, three
sampled paths averaged, seed 2026. No fine-tuning or substitute predictions.

| Model | Sessions | Cold request | Hot request | Peak allocated memory |
| --- | ---: | ---: | ---: | ---: |
| small | 5 | 8.751 s | 0.141 s | 145.33 MiB |
| base | 5 | 9.396 s | 0.137 s | 462.55 MiB |
| small | 30 | 7.194 s | 0.526 s | 148.02 MiB |
| base | 30 | 10.206 s | 0.976 s | 465.26 MiB |

"Cold" means weights were absent from this process before the request. Filesystem
and CUDA kernel caches were not flushed. The first deployment's small/5 request
took 16.819 seconds; subsequent model reloads were faster. These are observations
on a shared GPU, not latency guarantees. Memory is PyTorch peak allocated memory
for this service, including the resident model, rather than total device or
driver/context usage.

## Application and browser acceptance

- Actual authenticated backend jobs completed for prediction and historical
  backtesting. Jobs retained full input/output audits, data provenance, model
  revisions and sampling parameters in the existing database.
- The browser selected `sh.600000`, ran small/5 and base/30 predictions, and
  rendered the chart and full OHLCV/amount table.
- The base/30 forecast has 30 rows, 2026-11-04 through 2026-12-15.
- A real submitted job was cancelled through the page. It persisted as
  `failed` / `Cancelled` and the page displayed the cancellation.
- Refresh restored a completed job. Changing configuration labelled the old
  result with its original experiment. No JavaScript page errors were observed.
- Desktop, tablet and mobile widths (1440, 768, 390) were checked for horizontal
  overflow. Screenshots accompany this report.
- Before the 17:30 Asia/Shanghai data publication cutoff, the application used
  the preceding day's completed history and displayed its actual last session.
  Missing sessions inside the selected input interval still fail validation.

## Real historical execution

Small, 256-bar context, 2026-09-01 through 2026-10-30, initial capital CNY 100000.
Eight anchors generated fixed five-session forecasts. The first 256 context
bars preceded the execution interval and did not consume it. Four actual fills
were verified against raw next-session opening prices:

| Signal close | Execution date | Side | Raw open | Fill with slippage | Shares |
| --- | --- | --- | ---: | ---: | ---: |
| 2026-09-15 | 2026-09-16 | Buy | 9.17 | 9.1709 | 10900 |
| 2026-09-22 | 2026-09-23 | Sell | 9.02 | 9.0191 | 10900 |
| 2026-10-21 | 2026-10-22 | Buy | 9.66 | 9.6610 | 10100 |
| 2026-10-28 | 2026-10-29 | Sell | 9.85 | 9.8490 | 10100 |

The shared simulator applied fees, lot sizing, T+1 and participation limits.
Verified dividend and adjustment-factor batch identifiers are retained in the
result. This is a retrospective evaluation of a pretrained model with unknown
training overlap, not independent out-of-sample evidence.

## Automated verification

Commands cover backend Ruff/pytest; frontend typecheck, lint, formatting, build,
bundle budget and Vitest; the complete Playwright suite; and the nested
TradingAgents package. Exact final counts are recorded in `live-verification.json`.

Regression coverage includes request limits, holiday calendars, raw units,
version mismatches, transport errors, OOM/error mapping, model reuse/switching,
idle release, actual remote phases, cancellation races and restored jobs.
Changing future prices leaves an earlier anchor's model input and signal intact.

The full suite exposed a pre-existing 15:30-16:00 paper-test fixture gap. The
fixture now publishes its explicit synthetic evidence at the same 15:30 cutoff
used by that business rule, with a regression test. Production paper-trading
behavior was not changed.

## Reproduce and roll back

From `backend/`:

```powershell
python ../deploy/kronos/healthcheck.py
python ../deploy/kronos/verify_live.py --output ../deploy/kronos/live-verification.json
```

The opt-in verifier performs real GPU work and creates application jobs. It
checks remote authentication/serialization and asserts next-open fills against
raw bars. It never prints service credentials.

Rollback: select the existing predictor, then run
`systemctl disable --now backing-kronos` on the GPU server. Existing research
projects, original environments and saved business data are preserved.
