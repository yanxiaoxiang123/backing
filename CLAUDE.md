# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Superpowers 工作流规则 (必须严格遵守)

**所有任务必须使用 superpowers skill 流程，不得跳过。**

收到任何任务后，按以下顺序执行：

1. **立即调用 `Skill` 工具**检查适用的 superpowers skill（哪怕只有 1% 可能性）
2. **Announce**：明确宣布"Using [skill] to [purpose]"
3. **遵循 skill 流程**：严格按照 skill 内容执行，不得自行简化或跳过步骤

### 必须使用的核心 skills

| 场景 | Skill |
|------|-------|
| 任何 bug/问题排查 | `superpowers:systematic-debugging` |
| 任何新功能/特性开发 | `superpowers:brainstorming` (先行) + `superpowers:test-driven-development` |
| 完成实现后、提交前 | `superpowers:verification-before-completion` |
| 代码审查 | `superpowers:requesting-code-review` |
| 收到代码审查反馈 | `superpowers:receiving-code-review` |
| 复杂多步骤任务 | `superpowers:subagent-driven-development` |

### Red Flags (禁止的思维模式)

以下想法意味着 **STOP**，必须先调用 skill 检查：
- "这只是个小问题" — 问题即任务，必须检查
- "我需要先了解上下文" — skill 检查在澄清问题之前
- "先探索代码库" — skills 指导如何探索
- "这不需要 formal skill" — 如果 skill 存在，就必须使用
- "我知道这意味着什么" — 知道概念 ≠ 使用 skill
- "我先做完这个" — 先检查，再行动
- "感觉很有成效" — 无纪律的行动浪费时间

### 规则优先级

1. 用户的明确指令 (CLAUDE.md, GEMINI.md, AGENTS.md, 直接请求) — **最高优先级**
2. Superpowers skills — 覆盖默认行为
3. 默认 system prompt — **最低优先级**

## Project Overview

Backing is an A-share (Chinese equity) research, backtesting, AI-analysis and paper-trading platform. The repository root is the application root:

- `backend/` — FastAPI + SQLAlchemy + Pydantic v2 API, task workers, agent runtimes, migrations, tests (`pytest`).
- `frontend/` — React 18 + TypeScript + Vite + Ant Design + ECharts SPA (`vitest`, Playwright).
- `TradingAgents-astock/` — separate Python package (v0.2.4) used for optional multi-analyst deep research; installed editable, not run as a service.
- `docs/` — specs (`docs/specs`), implementation plans (`docs/plans`), and runbooks; the agent runtime specs are authoritative for that subsystem.
- `deploy/` — Redis docker-compose and systemd units for backend/frontend/maintenance.
- `dsh-quant-plugin/` and `deepseek-harness/` — historical design references only. Backend runtime must not import, copy, or start code from them.

This is a research/demo system. There is no live broker integration; "trading" means paper trading only.

## Commands

### Backend (`backend/`)

Requires Python 3.11+ (verified on 3.12). Local dev can use a venv (below) or the existing `stockbacking` conda env used by the systemd units.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # installs patched mootdx from ./vendor/mootdx
pip install -e ../TradingAgents-astock   # TA bridge and its tests
cp .env.example .env               # Windows cmd: copy .env.example .env
alembic upgrade head               # mandatory; server refuses to start without schema
python main.py                     # http://localhost:8808
```

`requirements.lock` pins the full transitive environment. Never add the PyPI `mootdx` package; the vendored copy relaxes an `httpx` constraint and must stay in place. Optional production task backend: `pip install -r requirements-arq.txt`.

```bash
# Tests
pytest
pytest -q
pytest tests/test_backtest_executor.py -v
pytest tests/test_backtest_executor.py::test_name

# Lint (ruff.toml in backend/)
ruff check app/ main.py task_worker.py maintenance_cli.py migrations/ tests/
ruff check --fix .

# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Arq worker (production multi-instance; TASK_BACKEND=arq + REDIS_URL)
python task_worker.py

# Data lifecycle
python maintenance_cli.py jobs --days 30
python maintenance_cli.py analysis --days 180
python maintenance_cli.py backtests --days 365
python maintenance_cli.py alerts --days 90
python maintenance_cli.py archive-klines --before 2015-01-01
python maintenance_cli.py backup --out /backup/backing.db
python maintenance_cli.py all

# Agent evaluation (deterministic replay by default; no API key/network)
python -m evals.run_eval
python -m evals.run_eval --output report.json
EVAL_LIVE=1 python -m evals.run_eval --live   # real LLM calls
```

### Frontend (`frontend/`)

```bash
cd frontend
npm ci                 # or npm install for first-time dev
npm run dev            # http://localhost:5174; Vite proxies /api -> :8808
npm run typecheck      # tsc --noEmit
npm run lint           # ESLint
npm run format:check   # Prettier
npm run build          # tsc + vite build + bundle-budget check
npm test               # Vitest run
npm run test:watch
npm run test:e2e       # Playwright; starts Vite itself (install browsers first)
```

### Nested TradingAgents package

```bash
cd TradingAgents-astock
pip install -e .
pytest
```

### CI

`.github/workflows/ci.yml` runs on push/PR: backend `ruff` + `pytest`, the nested TradingAgents suite, and frontend `typecheck` → `lint` → `format:check` → `build` → `test`. Run the same commands locally before pushing.

## Architecture

### API composition and auth

`backend/main.py` is the composition root. It imports `app.services.strategy` for its registration side effect, registers unified error handlers, request-logging middleware, CORS, session middleware and CSRF middleware, then mounts every router. **All API endpoints are under `/api/v1`** (including `/api/v1/strategies/*`, `/api/v1/watchlist/*`, `/api/v1/auth/*`); the realtime WebSocket is `/api/v1/ws/realtime/{code}`.

Authentication supports two paths (`app/auth.py`): a signed HttpOnly session cookie issued by `POST /api/v1/auth/session` (the browser exchanges `API_KEY` once at login; 8-hour default, SameSite=Lax), or the `X-API-Key` header for external clients. Cookie-authenticated mutations must carry the `csrf_token` cookie's value in `X-CSRF-Token` (`app/middleware.py`); the login endpoint is exempt and rate-limited to 10/minute. In production (`APP_ENV=production`) startup fails unless `SESSION_SECRET` is set and `SESSION_HTTPS_ONLY=true`.

Responses and errors are structured: failures return `{"error": {"code", "message", ...}}` via `app/error_handlers.py`. Raise `AppError` subclasses (`app/exceptions.py`); external provider failures should use `ExternalServiceError` so the client gets a stable status/code and the task executor can decide retryability.

### Data layer and caching

- `app/services/baostock_service.py` — stock list and daily K-line sync. `STOCK_LIST_PROVIDER` and `KLINE_PROVIDER` select `akshare`/`baostock`, with fallback; baostock's C client is guarded by a process-wide lock.
- `app/services/realtime_service.py` — mootdx quotes/bars/indices with server discovery, failover, health counters and L1/L2 caching. Provider reachable but empty → HTTP 200 with `data: []`; provider unreachable → 503 `provider_unavailable`. Health snapshot at `GET /api/v1/realtime/health`.
- `app/services/indicator_service.py` — technical indicators with a cache keyed by DB engine so test databases cannot share stale values.
- `app/services/research_data.py` — deterministic evidence layer for news/announcements/financials/index K-lines. Every item carries `source_id`, `as_of`, `vendor`, `data_version`; results cache in the isolated SQLite file `backend/data/research_cache.db` (not Alembic-managed). Eval fixtures are injectable here.
- `app/services/cache.py` — bounded process-local L1 cache plus optional Redis L2 (`REDIS_URL`). Entries have fresh and stale deadlines; Redis failure degrades to memory and never breaks a market request.

### Strategy and backtest engine

Strategies inherit `Strategy` (`app/services/strategy/base.py`) and register with `@register_strategy("name")`. Built-ins are split across `trend.py`, `reversal.py`, and `breakout.py` (13 strategies); `factors.py` holds `TechnicalFactors`, `optimizer.py` the grid-search optimizer, `signals.py` shared signal helpers. The package `__init__` imports all strategy modules, and `main.py` imports the package for registration — new strategy modules must be added to that import path. Parameters expose `min/max/step/options` metadata consumed directly by the frontend.

`app/services/backtest_executor.py` is the single backtest engine used by both the legacy `POST /api/v1/backtest` and the strategy endpoint `POST /api/v1/strategies/backtest`. It loads K-lines from the DB, simulates trades, computes metrics/portfolio curve, and persists `backtest_results` + `backtest_trades`. Parameter optimization (`POST /api/v1/strategies/optimize[/submit]`) runs through the shared task executor.

### Background jobs

Job state lives in the `jobs` table (`app/services/job_store.py`), so status survives restarts. Execution location is selected by `TASK_BACKEND` (`threads` default; `arq` for Redis-backed multi-instance workers), but both use the same lifecycle in `app/services/tasks/runner.py`: idempotency keys, lease/heartbeat, retry with backoff for transient provider errors, cooperative cancellation, and metrics. Submit endpoints return a `job_id`; clients poll `GET /api/v1/jobs/{job_id}` (there is also `/jobs/metrics` and `/jobs/{id}/cancel`). Register new job types with `@register_runner("name")` and import the defining module from `task_worker.py` if the Arq worker must see it.

### Agent systems (three distinct layers)

Do not conflate these; they share infrastructure but serve different APIs.

1. **Legacy staged analysis** — `app/agent/` (`orchestrator.py`, `pipeline.py`, agents). Modes `quick`, `standard`, `full`, `strategy`; exposed at `/api/v1/agent/analyze`, `/market/analyze`, and history endpoints. LLM via `llm_adapter.py` (DeepSeek, optional Tavily).
2. **Durable Agent Run engine** — `app/agent_runtime/` plus API `app/agent_api/`. Implements runs that survive refresh/restart: `agent_runs`, `agent_steps`, `tool_calls`, `artifacts`, `approvals`. `runtime.py` executes a sequential `RuntimeNode` pipeline with budget checks, node-boundary cancellation/cancel tokens, resume from the last successful step, and tool-call idempotency by parameter hash. `graphs/supervisor.py` builds a `RunPlan` and selects expert nodes (`data_qa`, `research`, `strategy_engineer`, `backtest_critic`, `portfolio_risk`, optional `ta_research`); `app/domain/` holds the guarded Pydantic output schemas. Routes: `/api/v1/agent-runs[/...]` with SSE events (Last-Event-ID replay), resume, cancel, artifacts.
3. **Agent Chat workspace** — `app/agent_chat/` plus `/api/v1/agent-chats/*`. `NativeAgentChatRuntime` is a DeepSeek ReAct loop over typed tools (no dependency on the external DeepSeek Harness checkout); `policy.py` deterministically decides which tool scope a turn may use; `service.py` runs a worker pool with strict per-thread FIFO, idempotency keys, cancel, restart recovery, and ordered events in `agent_chat_threads/turns/events`. `AGENT_CHAT_BACKEND=native` (default) or `fake` (tests/demo). A chat turn can emit `run.linked` to attach an `agent_run`.

### Typed tool gateway

`app/tools/` is the only permitted way for agents/tests to reach market or portfolio data. `DEFAULT_REGISTRY` contains allowlisted tools across market, fundamental, factor, strategy, backtest, portfolio, execution.paper and event domains. `ToolRegistry.invoke` enforces permission, validates the Pydantic input schema, caps output size, returns a uniform envelope (`ok`, `data`, `source_id`, `as_of`, `vendor`), and records audit rows in `tool_calls` when stores are supplied. External callers use `POST /api/v1/tools/invoke`. The TradingAgents bridge (`app/agent_runtime/ta_bridge/`) routes supported TA data methods through this gateway too; unsupported methods fail explicitly rather than bypassing it.

### Paper trading, alerts, evaluation

`app/agent_runtime/paper/` implements the default paper account, approval state machine, deterministic matching rules (no approval → no fill, T+1, cash/position checks, fees/price limits), replay/attribution, and a soak loop started by `main.py`. API routes under `/api/v1/paper/*` and approval routes under `/api/v1/agent-runs/{run_id}/approvals`. Alerts are persisted and exposed under `/api/v1/paper/alerts`.

`backend/evals/` is the evaluation harness: golden cases, response cache for deterministic replay, and scorers for schema validity, citation coverage, lookahead bias and A-share trading rules. `EVAL_LIVE=1`/`--live` switches to real LLM calls.

### Persistence and migrations

Default DB is SQLite (`backend/stock_backtest.db`, relative to the backend working directory); MySQL is supported through `DATABASE_URL` (optional `DB_BOOTSTRAP_URL` for database creation). SQLite connections enable foreign keys, WAL and a busy timeout. **Alembic is the only schema authority**: `main.py` no longer calls `create_all` and refuses to start if the `strategies` table is missing. Add migrations with autogenerate, inspect them, and run `alembic upgrade head`. Money/price/return columns are `Numeric`; DB timestamps are naive UTC (new non-model code may use timezone-aware UTC). `backend/data/` (research cache, artifacts, TA outputs) is runtime data and gitignored.

### Frontend

`src/App.tsx` owns routing (lazy-loaded pages, auth gate, responsive navigation, global stock search, Research Copilot). Key pages: Dashboard, StockList, StockChart (`/stocks/:code`), Watchlist, Screener, Strategies (main strategy research UI), DLPrediction, BacktestHistory, AgentAnalysis (`/agent`), AgentWorkspace (`/workspace`), Login. `/backtest` redirects to `/strategies`.

`src/services/api.ts` is the axios base (`/api/v1`) and handles session bootstrap/login/logout plus the CSRF request interceptor. Feature modules (`stocks.ts`, `strategies.ts`, `agentRuns.ts`, `agentChats.ts`, `jobs.ts`, `market.ts`) wrap API calls. TanStack Query is configured in `main.tsx`; hooks in `src/hooks/` encapsulate polling, SSE (`AgentRunStream` with Last-Event-ID reconnect), chat state and realtime WebSocket K-line updates (with HTTP fallback). Components are grouped by area under `src/components/`; global styling lives in `src/index.css`.

Vite splits vendor chunks (antd, echarts, react, etc.) and the production build runs `scripts/check-bundle.mjs`. Unit/component tests are colocated as `*.test.ts(x)` (Vitest + Testing Library, jsdom); Playwright specs live in `frontend/e2e/`.

## Working conventions and gotchas

- `backend/ruff.toml` intentionally ignores UP006/UP007/UP009/UP035/UP045 (legacy typing style), B008 (FastAPI defaults), BLE001 (deliberate provider isolation), and naive-datetime rules. Do not "modernize" those conventions wholesale. `vendor/` is excluded from lint and must remain upstream-identical except its metadata patch.
- Use four-space Python, type hints on public interfaces, `snake_case` modules/functions, `PascalCase` classes. Keep handlers thin; domain behavior belongs in services. TypeScript follows the existing two-space, semicolon-free style.
- Provider semantics matter: `FetchResult.status` distinguishes `ok` / `empty` / `unavailable`; preserve the 200-with-empty vs 503 contract and the `stale`/`cache_age_ms` fields.
- Never add `VITE_*` secrets — they are inlined into the browser bundle. The browser authenticates only via the login page and session cookie.
- Agent facts must come from tool-gateway envelopes; do not let an LLM invent provider data, and do not bypass the gateway to call vendors directly.
- The backend must not import `dsh-quant-plugin/` or `deepseek-harness/`; they are historical references.
- Commit messages use Conventional Commit-style subjects (e.g. `feat: ...`, `fix: ...`), imperative and focused.

## gstack

Use gstack's `/browse` skill for web browsing. All available gstack skills (including `/qa`, `/review`, `/investigate`) are listed in the skills panel and discoverable at runtime.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
