# Architecture Notes

## Goals

- Keep one authoritative backtest execution model
- Separate synchronous read APIs from long-running write/compute jobs
- Make local development work without external infrastructure

## Core Decisions

### 1. Shared backtest executor

`backend/app/services/backtest_executor.py` is the single execution path for:

- legacy `/api/backtest`
- strategy `/api/strategies/backtest`
- future optimizers

It normalizes:

- trade records
- capital curve metrics
- strategy lookup
- persistence into `backtest_results` and `backtest_trades`

### 2. Job submission pattern

Long-running operations now follow:

1. submit a job
2. get `job_id`
3. poll `/api/jobs/{job_id}`
4. consume `result` or `error`

Current in-memory job types:

- `sync_stocks`
- `sync_kline`
- `strategy_optimize`
- `agent_analysis`

### 3. Environment-first configuration

All secrets and deployment-sensitive values must come from `.env`.
The codebase keeps only safe defaults for local development.

### 4. Migration baseline

Alembic is added as the schema source of truth for future database changes.
`Base.metadata.create_all()` is still present for development bootstrap, but schema evolution should move through Alembic revisions.
