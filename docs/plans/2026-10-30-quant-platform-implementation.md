# Quant platform implementation

Ordered delivery plan. A checkbox means implemented and verified, not merely designed.
Existing user changes must be preserved. Backend commands use the backing Conda environment.

## A. Trustworthy research foundation

- [x] A1: Shared next-session-open execution for backtests and optimizers; fees,
  slippage, participation limits, T+1, blocked bars, daily-equity metrics and tests.
- [ ] A2: Data coverage/quality API and repeatable scheduled synchronization CLI.
- [x] A3: Immutable input snapshots and execution assumptions in saved results.
- [ ] A4: Exchange calendar, security status history, corporate actions, raw prices
  and versioned adjustment factors; migrate existing unlabelled candles explicitly.
- [ ] A5: Replace demonstration risk approvals with evidence-based proposals.

## B. Portfolio research

- [x] Multi-symbol shared-cash execution, rebalance schedules, benchmarks and costs.
- [ ] Walk-forward evaluation, parameter stability and market-regime stress tests.
- [ ] Factor IC/RankIC, quantiles, neutralization, decay and correlation reports.
- [ ] Strategy versions, experiment registry and reproducible experiment exports.

## C. Product and trading lifecycle

- [ ] Multi-account simulation, position accounting, partial fills and reconciliation.
- [ ] Portfolio exposures, concentration, liquidity, stress limits and kill switch.
- [ ] Scheduled research, report exports, run comparisons and notification delivery.
- [ ] Model provenance, training/validation separation, fallback visibility and drift.
- [ ] Real user ownership, roles, approval separation, audit and credential scopes.

## D. Operations

- [ ] Static hosting/reverse proxy, least-privilege deployment and release rollback.
- [ ] Durable metrics, tracing, dependency readiness and external alert delivery.
- [ ] Production DB validation, encrypted/offsite backups and restoration exercises.
- [ ] Continuous paper validation against quantitative promotion requirements.

Broker sandbox credentials, production host/TLS configuration, notification channel
credentials and historical PIT datasets are external dependencies. Implement adapters
and local tests first; do not report real integrations verified without credentials.

## Audit corrections

- Parameter snapshots already derive defaults from the configured strategy instance;
  the earlier claim that supplied parameters were discarded was incorrect.
- Native LLM chat is already implemented. Do not restore the historical DSH design.
- Calendar-day CAGR is a valid convention; this delivery standardizes on observed
  daily sessions and discloses that convention alongside the execution model.

## Delivery record: foundation batch 1

- A2 partially delivered: authenticated coverage/quality endpoint, explicit failure
  on missing history in synchronization CLI, watchlist/all-market modes and Linux
  timer templates. Scheduler installation and full-market ingestion are pending.
- A5 partially delivered: removed hardcoded 10%/100-share buy approvals; missing
  execution evidence now yields an explicit rejected risk proposal. Full account-
  based risk and order sizing are pending.
- Fixed stale quote eviction: fresh-only misses retain last-good data for fallback.
- Fixed synchronization duplicate handling so earlier successful rows survive.
- Migration `20261030_02` applied after an online SQLite backup in `backend/data/backups/`.
- Backend restarted in backing Conda. Live authenticated coverage query, real
  backtest and snapshot replay returned 200; replay reproduced result #1.
- Full backend regression after cache fix: 646 passed, 1 skipped; subsequent
  snapshot/auth tests verified separately. Changed-file Ruff check passes.
- Actual database at verification: 5,573 securities, 3,304 candles, 2 covered
  securities. This is not full-market historical coverage.
- Explicit remaining execution limits: historical fee schedules, exact exchange
  price limits, PIT adjustment factors, real exchange calendar and partial fills.

Next ordered work: A2 full ingest/scheduler and A4 versioned market-data governance,
then evidence-based A5 risk. B/C/D have not been implemented by this batch.

## Delivery record: foundation batch 2 (goal remains active)

- Migration `20261030_03` applied after online SQLite backup; schema-drift and
  upgrade/downgrade tests pass. Five new market-governance tables are present.
- Legacy 3,304 candles archived in two `legacy_unknown` batches without rewriting
  the original history. New raw-price batches are separate and checksum-addressed.
- Live security-master refresh stored 5,564 observations, including delisted names;
  the security master now contains 5,913 symbols. Earlier PIT universes remain
  unavailable unless a historical observation/import supplies that evidence.
- Verified daily calendars and raw-price ingestion work against Baostock. The first
  ten-day sample completed without gaps. Full two-year ingestion is running in
  exec session `99678`; progress is `backend/data/sync/full-market-report.json`.
  Revalidate that handle before waiting or deciding it has stopped. Do not restart
  an active process merely because a tool observation timed out.
- Windows task `Backing-MarketDataSync` registered successfully, daily at 17:00,
  current-user interactive principal, repeat instances ignored. Uses backing Python.
- Current missing-session examples: sh.600053 on 2026-04-29; sh.600058 from
  2025-12-30 through 2026-01-14. A direct provider probe returned no candle for the
  first gap. These must not be marked complete without verified suspension/status
  observations. Add explicit per-security session-status storage and reconcile
  failures after the initial live ingestion, rather than fabricating candles.
- Stock-management UI shows coverage and per-page raw ingestion. Desktop/tablet/
  phone checks at 1440/768/390: no page errors or horizontal overflow. Screenshots
  are in `.taste-skill/data-quality-{width}.png` (ignored working files).
- Backend full regression before the last startup-recovery changes: 658 passed,
  1 skipped. Focused governance/recovery/task tests pass. Frontend build and five
  quality/stock-list tests pass; ESLint has zero errors and one existing Screener
  hook-dependency warning. Changed backend files pass Ruff.
- Backend now runs hidden from backing Python (PID 36248 at this record), with
  runtime output in `backend/data/runtime/`. Frontend remains on port 5174.
- Latest verified ingestion snapshot: 230/5,913 processed, 165 complete, 34 with
  unresolved gaps; other processed symbols fall outside the requested listing
  interval. Raw batches cover 200 symbols. Counts continue changing in the report.
- Frontend unit/component suite completed successfully. Repository-wide
  `format:check` still reports 78 pre-existing files; newly changed frontend files
  were formatted. This CI gate remains open and must be fixed before final delivery.

Remaining A2/A4: explicit suspension evidence, factor/corporate-action integration
in historical execution, raw-data selection throughout charts/backtests, complete
ingestion audit and multi-host scheduling/locking. A5 and B/C/D remain required.

## Delivery record: foundation batch 3 (goal remains active)

- Migrations `20261030_04` and `20261030_05` applied after online SQLite backups.
  Added append-only security-session evidence and complete metadata-response
  snapshots (including verified empty results). Schema/roundtrip tests pass.
- Explicit Baostock `query_all_stock` evidence confirms sh.600053 suspended on
  2026-04-29. Stored 49 suspended securities for that session; the confirmed gap
  is now excused without creating candles. Observation cutoffs, reversals and
  conflicting status reports are covered by tests.
- Charts, indicators, signals, optimizers and core backtests share raw-first
  selection. Once a security has versioned raw history, incomplete intervals fail
  instead of silently mixing legacy candles. API compatibility can explicitly
  select legacy; the research UI defaults to raw and verified corporate actions.
- Daily-next-open-v2 includes verified suspended sessions in equity observations
  and expires their pending signals. V3 adds record-date entitlements, dividend
  receivables/payment, bonus-share listing availability and configurable flat
  dividend-tax assumptions. Fractional allocations and unsupported ex-date events
  fail closed. Adjusted charts disclose their retrospective factor semantics.
- Execution snapshots now hash the complete saved metadata, including signals,
  costs, session dates and actions. Replay reproduces the verified v3 live result
  #2; subsequent browser QA generated further real saved results. Raw and adjusted
  2025 sh.600000 history each returned 243 observed sessions.
- `data_sync_cli.py --metadata-only` can update action metadata independently of
  long-running price ingestion. Live sh.600000 metadata sample succeeded. Metadata
  commits occur before the next network call to avoid holding SQLite write locks.
- New Baostock price-governance calls use a persistent isolated process with a
  45-second request deadline. A blocked connection is terminated and can recover
  on the next call. Real calendar query and process-timeout/recovery tests pass.
  The already-running original full-market process still uses its original code;
  let it finish, then reconcile failures with the upgraded status-aware loader.
- SQLite ingestion keeps its OS-held lock; PostgreSQL uses a dedicated
  session-level advisory lock across commits. Actual PostgreSQL deployment and
  concurrency validation remain part of D, not yet verified.
- Restored the pre-existing research_data module after a filename collision,
  preserving the earlier connection-cache changes captured in the session. The
  new price policy is `market_research_prices.py`. Research, paper attribution and
  evaluation regressions pass; do not replace the original research-data tools.
- Backend full regression after market-data integration: 681 passed, 1 skipped.
  Focused ingestion/corporate/RPC regression after metadata extraction: 26 passed.
  Frontend full suite: 155 passed. Build passes. Strategy UI browser QA at
  1440/768/390: actual backtest succeeds, no page errors or horizontal overflow;
  narrowed metrics fixed to one column. Screenshots `.taste-skill/strategies-*.png`.

## Delivery record: evidence-based risk (in progress)

- Explicit targets and stop assumptions now drive deterministic order sizing,
  using server-collected account/position/fill/order facts and versioned raw prices.
  Checks include market/calendar/status coverage, T+1 availability, cash reserved
  for pending orders, cash buffers, concentration, stop-loss and liquidity capacity.
  Sector limits require classification evidence when enabled; they are disclosed
  as disabled by default. No demonstration buy or invented target is generated.
- New authenticated run-risk endpoint, optional create-run `risk_request`, and
  graph integration save checksum-addressed intent and evidence artifacts. Current
  accounts cannot be backdated; concurrent ledger changes reject assessment.
  Evaluation does not create orders/approvals. The workspace risk panel supports
  explicit inputs and displays calculated quantities and their evidence outcome.
- Fixed artifact writing on Windows so new checksum values match actual UTF-8
  bytes rather than pre-translation LF text. Old artifacts remain readable.
- Risk/service/API/graph tests: 43 passed; artifact workspace tests: 6 passed.
  The full risk regression and latest frontend checks are running; record final
  totals after completion. API process still needs restarting for the risk routes.
- A5 is not marked complete: mandatory risk binding and revalidation on order
  proposal/approval/fill, plus account-policy ownership, remain required. Existing
  manual paper-order paths still require separate hardening in C.

Remaining full scope: complete ingestion/reconciliation, raw consumers still using
legacy data in paper matching/attribution/older analysis paths, unsupported corporate
events/PIT history, mandatory order risk evidence, all B/C/D requirements and the
pre-existing repository-wide frontend formatting failures. Do not mark the goal
complete from this foundation delivery.

## Latest verification and runtime handoff (2026-10-30 afternoon)

- Backend full suite with risk integration: **700 passed, 1 skipped**. Subsequent
  market-calendar/RPC/circuit-breaker changes: **21 focused tests passed**.
  Frontend entire suite with risk form: **157 passed**. Latest production build
  and bundle-budget check pass; ESLint has zero errors and the existing Screener
  dependency warning. All changed backend files pass Ruff.
- New risk panel browser rendering checked at 1440/768/390 without page errors or
  document overflow. These screenshots use an explicitly labelled **UI fixture**
  (`.taste-skill/risk-*.png`), not a claimed live successful trading decision.
- Live authenticated risk evaluation run
  `validation-risk-8a043d0364f8444f` returned 200 with a rejected proposal and zero
  suggested orders because latest completed-session price evidence was missing
  for sh.600000 and sz.000001. Evidence artifact #6 is stored; paper-order count
  did not change. The run is explicitly labelled as functional validation.
- API restarted with all current code using backing Python, PID **35472** at this
  record. Output: `backend/data/runtime/backend-current.out` and `.err`.
  Frontend still runs on 5174. Migrations remain at `20261030_05`.
- The original price-ingestion process was deliberately replaced to load the
  status fixes and bounded network calls; it was **not** assumed dead from an
  observation timeout. Its exec session **99678 is terminal**. Final preserved
  report: `backend/data/sync/full-market-report-before-status-20261030-162631.json`
  (**1,836 attempted / 5,913**, 1,466 complete, 252 unresolved, 118 skipped).
  Previously committed raw batches are preserved and reused by the new pass.
- Replacement session 66351 terminated on a real 45-second Baostock login timeout
  while requesting calendar data. Calendar coverage now reuses complete verified
  stored ranges, and CLI startup failure always writes an explicit fresh report.
- An RPC progress-message upgrade initially broke an already-running parent
  process. Fixed with an opt-in worker protocol: old parents still receive only
  final boolean responses; new parents can request stage messages. Two protocol
  regression cases pass. Do not change live worker/parent wire compatibility
  without preserving old callers. The intermediate session 21800 was replaced;
  its report is preserved with a `full-market-report-protocol-*` name.
- Current upgraded ingestion: exec session **75237**, Python PID **52528** at this
  record, writing `backend/data/sync/full-market-report.json`. The source TCP port
  is reachable but login calls time out; latest observed pass was 6 attempted,
  2 network failures, 4 outside-listing skips. **Revalidate the session**: after
  three consecutive provider failures the run now terminates with
  `aborted=provider_unavailable`, preserving the unprocessed count. It must not be
  reported complete or silently retried in a rapid loop. The existing 17:00 daily
  Windows task can retry after service recovery; price metadata are not fabricated.
- Next ordered implementation: require a risk-evidence reference and fresh
  validation on paper-order proposal, approval and fill. Current risk assessment
  itself is implemented and reviewable, but existing manual paper-order tools do
  not yet require that evidence. Then proceed with B portfolio execution/research,
  C lifecycle/access control and D operations. Full-market reconciliation, metadata
  coverage beyond the sampled stock, and legacy paper/analysis consumers remain
  open alongside that work. Keep the overall goal active.

Terminal confirmation: session **75237 has now exited** after the third actual
login timeout (2026-10-30T08:37:48 UTC). Its structured report states 7 attempted,
3 failed, 4 outside-listing skips, **5,906 unprocessed**, `success=false`, and
`aborted=provider_unavailable`. No full-market ingestion process should be assumed
running now. Preserve the earlier successful raw batches: live quality endpoint
still returns 200 with **1,719 raw-covered securities / 819,507 versioned bars**.
Frontend also returns 200. Continue independent implementation while the provider
is unavailable; resume/reconcile ingestion on confirmed recovery, with the existing
daily task as a later retry opportunity.
## Delivery record: portfolio research (2026-10-31 morning)

- Revalidated the previous mandatory paper-order risk work: proposal, approval,
  fill and migration regressions pass. Full A5 remains open for ownership/policy
  separation; do not infer RBAC or multiple accounts from the order gate.
- B1 implemented: explicit long-only weights (up to 20 securities) share one cash
  pool; daily/weekly/monthly schedules size at the previous completed close,
  execute sells before buys at the next session open, and proportionally reduce
  buys when cash is scarce. Liquidity capacity uses previous completed-session
  volume; lots, fees, slippage, non-executable sessions and expiring residuals are
  covered. This is allocation research, not a multi-strategy optimizer.
- The service requires versioned raw prices and verified exchange calendars.
  Missing bars need explicit suspension evidence. Corporate actions use the
  entitlement/receivable/bonus-share ledger; verified metadata are the default.
  Explicit price-only research is labelled. Universes and observations are
  retrospective; no historical PIT universe or exact auction model is claimed.
- Optional benchmark: same initial cash, costs and actions, next-open buy-and-hold
  of a user-selected security. Reports excess return, tracking error and IR;
  this is not the published return of an index. Daily equity, gross turnover,
  fees, slippage and unfilled reasons are retained.
- New authenticated `/api/v1/portfolio-research` create/list/detail/replay/export
  routes persist complete input and result snapshots with independent hashes.
  Results are scoped to the existing authenticated actor. Full user IDs, roles,
  scoped API credentials and approval separation remain C work.
- Migration `20261031_01` applied after online SQLite backup
  `backend/data/backups/before-portfolio-20261031-082033.db`. Fresh migrations,
  full upgrade/downgrade roundtrip and model/schema drift checks pass.
- Frontend `/portfolio` is linked from the strategy navigation. It supports
  explicit allocations/costs, net equity comparison, positions, fills, unfilled
  orders, daily ledger, saved experiments, replay and actual JSON download.
  Restored results show their saved allocation/period independently of the form.
  The most recent saved experiment loads on reopening the page.
- Tests caught and fixed hidden cost controls being omitted until a collapsed
  form was opened. StockSearch now forwards its form ID for accessible labels.
  The global 422 handler now returns type/path/message only: ValueError context,
  nonfinite raw input and credentials cannot break or leak through error JSON.
- Discovered an existing AI-settings fixture starting the real app lifespan and
  rotating the development account to its test API key. Isolated that fixture
  with its own database/app and no production workers. Restored the exact pre-test
  password hash from the backup above. The subsequent full regression explicitly
  verified the hash stayed unchanged and configured password login remained valid.
- Backend full regression after isolation: **732 passed, 1 skipped**; repository
  Ruff passes. Nested TradingAgents: **107 passed, 1 skipped, 44 subtests passed**;
  the optional Google adapter is not installed. Installed the already-declared
  missing CLI dependency questionary 2.1.1 in backing to run that suite.
- Frontend full regression: **160 passed**. Later saved-state/layout changes pass
  focused portfolio/Screener tests; latest build and independent bundle budgets
  pass. Fixed 70 pre-existing formatting violations with the repo formatter and
  the unstable Screener history dependency. ESLint and format checks now pass.
- Live verified 2025 sh.600000/sh.600004 portfolio with default costs and corporate
  actions: 18 fills, experiment `61af1f35e694427db2b82c3315674673`, immutable replay
  reproduced, export downloaded in a real browser. Desktop/tablet/phone QA at
  1440/768/390 has no page errors or horizontal document overflow. Screenshots and
  working review artifacts are in ignored `.taste-skill/portfolio*` paths.
- Visuals reuse the Backing shell/palette/type with editorial-greeting style,
  seed 242594597, no redraw. The question is how a specified allocation behaved
  under shared cash; the signature is its saved allocation beside the cash/equity
  evidence. No synthetic market observations or rendered fixture results were used.
- Data provider recovered for a real sh.600004 metadata synchronization. Its report
  is `backend/data/sync/portfolio-metadata-report.json`. Resumed full-market prices
  in exec session **93248**, Python PID **36984** at launch; use the live PID/handle
  and `backend/data/sync/full-market-report.json` to establish current state. Prior
  report copied to `full-market-report-before-portfolio-20261031-082243.json`.
  An individual source timeout remains a failure; never count unprocessed or
  unresolved symbols as complete. Daily task Backing-MarketDataSync is still Ready.
- Runtime: backend backing Python in exec session **77741**, PID **35096**, port
  **8808**; current frontend Vite PID **4724**, port **5180**. Port 5173 belongs to
  another project. Revalidate these handles before future restarts.

Next ordered work: finish ingestion/reconcile genuine gaps, then B2 walk-forward,
parameter stability and regime stress; B3 factor research and B4 strategy versions
remain open. All uncompleted A/C/D items above remain in scope. B1 delivery does
not mean the full quantitative-platform implementation is complete.

Visual audit addendum: final real-browser inspector returned **0 FAIL, 1 WARN**.
The retained warning is the existing Chinese platform font stack (PingFang SC is
unavailable on Windows and falls back to the installed local font); brand type was
explicitly retained. Reviewed desktop/mobile rendered images after fixing table
header size/tracking and showing the latest actual saved experiment on reopen.
The complete working critique is `.taste-skill/portfolio/critique.md`.

## Delivery record: automatic portfolio history (2026-10-31)

User-requested follow-up: selecting securities in portfolio research now prepares
research history directly, using the same `/data/history/sync` task endpoint and
metadata-aware loader as stock management. Stock/benchmark/date changes trigger
bounded debouncing; selecting another security only requests missing selections.
The page displays progress and exposes refresh/retry. Submitting a backtest waits
for the same preparation promise instead of racing it or submitting it twice.
Failed/incomplete synchronization never enables execution with incomplete inputs.

The hook scopes results to the current selection and period, cancels stale polling
and reuses persisted job IDs (including delayed submission responses). Removing a
security from a pending multi-security job cannot make the remaining selection
inherit an unrelated failure. Completed data for the same interval are reused.

Replaced the entire-universe ingestion mutex with per-security locks and bounded
waiting, retaining per-security metadata locks. A live full-market pass no longer
blocks an interactive request for a different stock. Same-stock followers wait,
then inspect already committed batches before making a duplicate price request.
Two actual SQLite concurrency regressions verify these properties.

The old API and bulk worker were deliberately restarted to load the locking change;
committed data were preserved. Previous report:
`backend/data/sync/full-market-report-before-interactive-20261031-085721.json`.
Current API: PID 19076 / exec session 33990; current all-market worker: PID 55036 /
exec session 41887. Revalidate these before later restarts; the bulk report still
uses `backend/data/sync/full-market-report.json`. No schema migration is required.

Live browser verification selected sz.000001 and sh.600000 for the default
2025-10-31 through 2026-10-30 interval. Two automatic jobs completed successfully;
the previously missing Ping An raw history was committed. The next portfolio run
completed with 23 fills, experiment d4949dd74c89485cb8412a3ac0b2897b, without another
download submission. Browser widths 1440/768/390 show no page errors or overflow;
actual screenshots are `.taste-skill/portfolio-auto-{width}.png`.

Backend full regression: 734 passed, 1 skipped. Frontend full initial regression:
168 passed; final selection-scope and retry checks pass (7 hook + 5 page tests).
Latest build, bundle budgets, Ruff, ESLint and repository format checks pass.
Source style lint: 0 FAIL/0 WARN. Browser inspector: 0 FAIL/1 existing platform-font
warning, with the same retained Chinese font-stack justification as above.
Final frontend full regression after the selection-scope fix: **169 passed**
(34 files). Configured account login still succeeds. Live versioned-history
quality checks confirm zero missing sessions for both sz.000001 and sh.600000 in
the tested default interval; frontend and API remain available.
