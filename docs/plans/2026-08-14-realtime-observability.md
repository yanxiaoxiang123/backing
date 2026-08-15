# Realtime Observability and Frontend Partial-Degrade (Issue 7)

Source: existing task "7. 实时行情已恢复，但仍缺少可观测性和前端局部降级"

Goal: distinguish "legitimately empty data" from "provider failure", expose node
health and short-term caching on the backend, and let the Dashboard render
indices, watchlist, and the trend chart independently with their own retry
controls.

The plan follows the current architecture: the realtime service stays a thin
failover wrapper around `mootdx.Quotes`, but it now records metrics, exposes
a health endpoint, caches recent results, and signals provider failures
through a structured 503. The Dashboard page moves from `Promise.all` to
`Promise.allSettled` and renders each block from its own state slot.

## Vertical slices

### Slice 1 — RealtimeService: failure distinction + caching + metrics
File: `backend/app/services/realtime_service.py`

Backward compatibility: the existing public helpers
`normalise_bars`, `get_realtime_quotes`, `get_index_realtime` keep
returning `list[dict[str, Any]]` (they are imported by screener,
WebSocket handler, and HTTP layer). The new envelope lives on
additional methods:

- `FetchResult` dataclass with `status` (`"ok" | "empty" | "unavailable"`),
  `data`, `provider`, `reason`, `served_at`, `cache_age_ms`,
  `selected_server`. Frozen, JSON-serializable.
- New methods: `fetch_bars(symbol, period) -> FetchResult`,
  `fetch_quotes(symbols) -> FetchResult`, `fetch_indices() -> FetchResult`.
- The existing list methods delegate to the new methods and strip the
  envelope (so screener, WS, and the graceful-degrade path still work).
- Add a 2-second cache per (symbol, period) for bars and per index
  code for snapshots so a noisy client doesn't pound the provider.
- Track state: selected_server, total servers, healthy count, last
  failure reason per endpoint, request count, failover count, cache
  hit count, unavailable count.
- Increment counters via the existing `task_metrics` helper
  (`realtime.request`, `realtime.failover`, `realtime.cache_hit`,
  `realtime.provider_unavailable`).
- Add `get_provider_health() -> dict` returning node pool snapshot plus
  counters, ready for the new endpoint.

Acceptance:
- `bars()` still returns `DataFrame`; `normalise_bars()` /
  `get_realtime_quotes` / `get_index_realtime` still return list[dict].
- `fetch_bars()` returns `status="ok"` with non-empty data when
  provider succeeds; `status="empty"` when probe succeeds but no bars;
  `status="unavailable"` when no server is reachable.
- Cache hit on `fetch_bars` is observable via `cache_age_ms > 0` and
  increments `realtime.cache_hit`.
- `get_provider_health()` returns counters and node snapshot.

### Slice 2 — HTTP layer: structured 503, health endpoint, cached metadata
File: `backend/app/api/realtime.py`

- `/realtime/{code}`, `/realtime/quotes`, `/realtime/indices` keep the
  graceful-degrade contract (`200 {success:true, data:[]}`) when the
  provider is healthy but markets are closed or no data is returned.
- When the realtime service reports `status="unavailable"`, return
  `503` with the structured error body (`code="provider_unavailable"`,
  `provider="mootdx"`, `retryable=true`, `extra={reason,...}`) by
  raising `ProviderUnavailableError`.
- Add `GET /realtime/health` (auth required) returning the snapshot from
  `get_provider_health()` (selected server, healthy count, last failure
  reason, recent metrics counters).

Acceptance:
- `/realtime/{code}` returns 503 + structured body when no server can
  serve a probe; otherwise 200 with `data` (empty when legit).
- `/realtime/health` is reachable without invoking mootdx.

### Slice 3 — Regression tests
Files:
- `backend/tests/test_realtime_service.py` (extend)
- `backend/tests/test_api_contracts.py` (extend)

Add focused tests:

1. Failure distinction:
   - Provider probe fails for every server → envelope `status=unavailable`.
   - Provider probe succeeds but no bars → envelope `status=empty`.
2. Caching:
   - First call to `normalise_bars` invokes `bars` once; second call
     within TTL returns from cache with positive `cache_age_ms`.
3. Metrics:
   - Successful, failover, and unavailable paths each bump the right
     counter; `get_provider_health()` exposes the snapshot.
5. HTTP contract:
   - `/realtime/{code}` returns 503 + `{code: provider_unavailable,
     provider: mootdx, retryable: true}` when service reports unavailable.
   - `/realtime/{code}` still returns 200 with empty data when the
     service returns `status=empty`.
   - `/realtime/health` returns 200 with `selected_server`,
     `healthy_count`, and counter fields.

Acceptance: `pytest tests/test_realtime_service.py tests/test_api_contracts.py`
runs the new cases green.

### Slice 4 — Dashboard: per-block degrade + retry
File: `frontend/src/pages/Dashboard.tsx`

- Replace the single `Promise.all([quotes, indices])` with
  `Promise.allSettled`. The page now tracks three independent state
  slots: `indices` (`{status: 'loading'|'ok'|'error', data?, error?}`),
  `watchlist` (same shape), `trend` (same shape).
- Render each block separately: on error show an inline alert with a
  retry button that re-runs only that block. The empty-watchlist case
  is unchanged.
- Suppress the page-level "数据加载失败" toast; rely on the per-block
  alert. The trend block keeps its retry via the existing stock
  selector but also surfaces an explicit button on error.
- New behaviour: a watchlist with empty quotes (provider empty) and
  valid indices still renders the indices cards.

Acceptance:
- `Promise.allSettled` is the only aggregator left in the page.
- Each block renders a `Retry` button on error and an `Alert` with the
  backend message when present.

### Slice 5 — Dashboard test coverage
File: `frontend/src/pages/__tests__/Dashboard.test.tsx` (new)

Use `@testing-library/react` + a mocked `api` module (matching the
existing pattern in `api.test.ts`) to assert:

- All three blocks load independently: when `getRealtimeQuotes` rejects
  but `getRealtimeIndices` resolves, the indices cards still render.
- Each block exposes a `Retry` button on error that re-invokes the
  matching service.
- A 503 from the backend (`{ error: { code: 'provider_unavailable',
  retryable: true } }`) is rendered as a retriable alert.

Acceptance: `npm test -- Dashboard` runs the new file green.

### Slice 6 — Verification
- Run `pytest` from `backend/` (whole suite).
- Run `ruff check backend/`.
- Run `npm run typecheck`, `npm run lint`, `npm run test`,
  `npm run build` from `frontend/`.
- Optionally smoke the live `/realtime/health` endpoint.

## Risks / decisions

- Cache TTL (slice 1) stays 2–5 seconds because market data is volatile
  but the realtime page polls every 10s anyway. The cache avoids
  unnecessary provider calls when several endpoints load concurrently.
- The new 503 contract is a breaking change for any caller that
  expected 200 with empty data on provider outage. The realtime client
  is the only caller (`api.ts` → `getRealtimeQuotes` etc.) and the
  fallback strategy is to render the new per-block error UI.
- `task_metrics` was originally task-scoped; using it for realtime
  counters reuses the existing `snapshot()` shape and keeps a single
  metrics endpoint.