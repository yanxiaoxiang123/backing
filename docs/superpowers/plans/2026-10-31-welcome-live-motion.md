# Welcome Live Market and Motion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn approved editorial A into a cinematic product page with real public market data and a scroll-driven read-only research demonstration.

**Architecture:** Keep static HTML/CSS/JS. Add narrowly scoped unauthenticated read-only market endpoints backed by existing quote/index services and a bounded cached intraday adapter. Progressive-enhancement frontend loads quotes and one selected series, pauses when hidden/offscreen and never fabricates quotes. Separate market, SVG chart and motion modules retain the existing welcome navigation and filters.

**Tech Stack:** FastAPI/Pydantic, existing realtime services, HTML/CSS/ES modules, SVG, Playwright, pytest.

**Spec:** Approved conversation: warm white/orange editorial A; live index quotes for Shanghai, Shenzhen, ChiNext; public selectable 贵州茅台 600519, 宁德时代 300750, 招商银行 600036; dramatic entrance and desktop sticky three-stage story; mobile natural flow; read-only strategy example, actual operations only after login.

## Global Constraints

- No private watchlists, account data, secrets, arbitrary public symbol proxy, automatic backtests or LLM calls.
- Public gateway returns explicit ok/empty/unavailable with per-section provider, market_at, fetched_at, stale/cache-age metadata. Partial failures must not erase other sections.
- Use actual intraday provider points, never daily bars labeled intraday. Missing data is missing, no invented line or animated random quotes.
- Visible quote time and source; distinguish fetch time from market time. Weekend/overnight/quote-date age and stale state must not imply live trading. Do not infer exchange holidays from weekdays alone.
- Poll at 30 seconds while relevant section is visible and document visible, use backoff on failures, no overlapping requests; abort/ignore obsolete stock selection responses.
- Price single series SVG and separate volume panel, labels + keyboard/touch tooltip + table. Text remains text-colored; price direction has +/- text and A-share red-up/green-down cues.
- Motion 2-second staged intro; sticky story progresses by scroll, not scroll hijacking; animate transforms/opacity, viewport pause, reduced-motion final readable state; no script leaves static content readable.
- Maintain safe login next forwarding, FAQ, strategy filtering, focus trap, legal styling. At most one existing screenshot in final page.
- User authorized implementation; work in active feature checkout to update localhost; no commits/pushes or integration changes.

## Review Focus

- Offline/partial/stale/empty quotes and series: honest labels and retry, no crash or fabricated fallback.
- Out-of-order symbol switch responses never update wrong ticker; timing source remains distinct.
- Backend public parameters fixed allowlist, response rows bounded, cached failures prevent provider storms.
- Screen reader chart text/table and reduced motion expose final content without empty sticky void.
- Mobile overflow, no JS, hidden tab/offscreen polling suspension and keyboard focus.

### Task 1: Public market gateway
**Files:** New backend API/service/tests, register router in main.py only as needed.
**Interfaces:** GET `/api/v1/public/market` returns `{indices: envelope, quotes: envelope}` where each envelope has status/data/provider/market_at/fetched_at/served_at/cache_age_ms/stale/reason; symbol strings canonicalized to sh.000001 etc. GET `/api/v1/public/market/intraday?code=sh.600519` accepts only three canonical allowed stocks and returns envelope with data `[{time: ISO+08:00,price:number,volume:number|null}]`, `volume_unit: "lots"`, `volume_kind:"interval"`, code, trade_date; no model-internal/server metadata.
- [x] Add tests and observe RED for fixed public access, disallowed symbols, partial outage, stale metadata and bounded series/cache behavior.
- [x] Implement fixed cached/rate-limited public gateway, actual Tencent minute-series adapter, conservative metadata.
- [x] Run targeted pytest and ruff; report live endpoint smoke evidence.

### Task 2: Real chart and market board
**Files:** welcome index.html/landing.css, new market.js/charts.js and browser tests.
**Interfaces:** Consumes Task 1 endpoints; graceful skeleton/error/retry, tables. Chart renderer validates rows and exposes tooltip, keyboard scrub.
- [x] Add deterministic Playwright fixtures covering quotes, empty/partial/outage, series switching and errors; observe RED.
- [x] Replace hero screenshot with index strip, selectable stock board, live quote/price/volume graphs, timestamp/state, table/retry.
- [x] Check accessible readout, no fabricated data, and snapshot mock-free live behavior.

### Task 3: Cinematic story and motion
**Files:** welcome index.html/landing.css, new motion.js, existing landing.js where necessary.
**Interfaces:** Hero and sections data-motion hooks; sticky story has three stages, one read-only example and explicit example label, no POST.
- [x] Build DOM strategy/search/result demonstration replacing repeated screenshots; keep only trust screenshot. States progressive without JS.
- [x] Add one-shot line/word/module entrances, section-local stagger, sticky scene with IntersectionObserver progress anchors, data-driven quote emphasis. Reduced-motion/mobile unpinned.
- [x] Test all stages appear, no POST/LLM calls, reduced motion, menu and filters remain functional.

### Task 4: Verify
- [x] Run frontend unit suite, lint/format, landing browser suite, production build and relevant backend tests.
- [x] Inspect screenshots at 1440/768/390, scroll-stage states and failure/reduced-motion states; fix material issues.
- [x] One scoped independent review; fix verified findings and report remaining limits faithfully.
