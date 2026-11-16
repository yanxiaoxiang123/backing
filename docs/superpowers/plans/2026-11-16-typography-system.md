# Typography System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Load Noto Sans SC for Chinese and Inter for Latin/digits, and make every application screen use four text sizes: 28 (key figures), 20 (titles), 14 (body), 12 (metadata/chart labels).

**Architecture:** Self-hosted variable fonts imported once at the app entry. One semantic token set in `tokens.css`; Ant Design and ECharts receive the same family string from `typography.ts`. Existing page CSS is migrated by role, not by a global flattening selector. Canvas charts re-render after font loading without resetting user state.

**Tech Stack:** React 18, TypeScript, Vite 5, Ant Design 5, ECharts 5, Playwright, Vitest.

**Spec:** `C:/Users/13566/.claude/plans/skill-4-noto-sans-glittery-quiche.md`

## Global Constraints

- Four text sizes only: `28px` metric, `20px` title, `14px` body, `12px` auxiliary. Icons and non-text glyphs are not text tiers.
- Chinese: `Noto Sans SC` / Source Han Sans CN fallback. Latin and digits: `Inter`.
- Preserve routes, data, form behavior, 250px sidebar, A-share red-up/green-down semantics, and `tabular-nums`.
- No Google Fonts runtime dependency. Do not preload every CJK subset.
- No component library or framework migration.

## Review Focus

- Text inside Ant Design portals (modal, select, tooltip, drawer) must inherit the family and the four sizes.
- ECharts canvas text does not inherit CSS and may measure fallback fonts before the webfont loads.
- Long Chinese stock names and large financial values must not clip at 320px or 200% zoom.
- Static `public/welcome` and exported HTML reports do not pass through the React style entry.
- Font failure/offline must remain readable through system fallbacks.

---

### Task 1: Baseline and failing typography test

**Files:**
- Create: `frontend/e2e/typography.spec.ts`
- Test: same

**Interfaces:**
- Produces: route-level assertions consumed by all later tasks.

- [ ] Write a Playwright test that mocks research APIs, visits `/stocks`, `/stocks/sz.000532`, `/strategies?stock=sz.000532`, `/workspace`, `/agent`, `/dl-prediction` at 1440 and checks visible text computed sizes against `{12,14,20,28}` and font family containing `Inter Variable` and `Noto Sans SC Variable`.
- [ ] Run it and confirm it fails on current fonts/sizes.
- [ ] Commit the test.

### Task 2: Semantic tokens and self-hosted fonts

**Files:**
- Create: `frontend/src/styles/typography.ts`
- Modify: `frontend/src/styles/tokens.css`, `frontend/src/main.tsx`, `frontend/package.json`, `frontend/index.html`
- Test: `frontend/src/styles/typography.test.ts`

**Interfaces:**
- Produces: `FONT_FAMILY`, `FONT_SIZE = { metric: 28, title: 20, body: 14, meta: 12 }`, `CHART_FONT`.
- CSS: `--fs-metric`, `--fs-title`, `--fs-body`, `--fs-meta`.

- [ ] Write failing unit test for constants and four unique sizes.
- [ ] Import `@fontsource-variable/inter` and `@fontsource-variable/noto-sans-sc` at the entry, define tokens, update AntD theme, remove stale Google Fonts links.
- [ ] Run unit test and confirm pass; confirm computed font in browser.

### Task 3: Migrate app CSS and components

**Files:**
- Modify: shared style layers (`base.css`, `layout.css`, `components.css`, `pages.css`, `shell.css`, `research-theme.css`, `surfaces.css`, `research-refinement.css`, `stock-list.css`, `dashboard.css`) and page styles as needed.
- Modify: `frontend/src/styles/agent.css`, `login.css`, `researchTheme.ts`, page-level ConfigProviders.
- Modify: chart typography in `frontend/src/components/charts/dlChartOptions.ts`, `frontend/src/utils/chart.ts`, `frontend/src/pages/StockChart.tsx`, `Dashboard.tsx`, `AgentAnalysis.tsx`.
- Test: `frontend/e2e/typography.spec.ts`.

**Interfaces:**
- Consumes Task 2 constants/tokens.
- Produces: four-size rendered screens and shared chart font.

- [ ] Replace effective font sizes with the four tokens; map page titles to 20, key numeric values to 28, body/table/nav/buttons to 14, and labels/axes/timestamps to 12.
- [ ] Apply `FONT_FAMILY` to AntD and every ECharts option; add post-font-load chart refresh preserving zoom/legend state.
- [ ] Run typography E2E and existing surface tests; fix outliers.

### Task 4: Verification and review

**Files:** none new beyond fixes.

- [ ] Run `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm run build`, `npm test`.
- [ ] Run Playwright surface, navigation, dashboard-fit, stock-list-fit, agent-workspace, dl-prediction specs.
- [ ] Inspect screenshots at 1440/768/390 and font network sizes; record exceptions.
- [ ] Dispatch the final whole-branch reviewer.
