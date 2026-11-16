# Research Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 保留单股策略研究现场，并让仪表盘报告链接直接打开对应记录。

**Architecture:** 保留现有 React Router 和 sessionStorage。提取轻量、可校验的策略状态规则，用 URL 表示当前标的和报告详情，使用完整请求快照区别草稿与已保存结果。

**Tech Stack:** React 18、TypeScript、React Router、AntD、Vitest、Playwright。

**Spec:** `docs/superpowers/specs/2026-11-14-research-continuity-design.md`

## Global Constraints

- 当前 feature branch 上实现，保留所有已有未提交改动，不 commit/push/deploy。
- 不新增依赖、不改后端认证或回测计算、不调用真实模型或执行模拟订单。
- 非敏感草稿只保留在当前标签页 sessionStorage；长期记录仍由后端保存。
- 沿用现有界面组件与布局。

## Review Focus

- 无效/陈旧 sessionStorage 不应使页面崩溃；Task 1 验证保存记录校验。
- 页面入口带股票时用户改选和清空均应生效；Task 2 用 e2e 验证 URL 与提交。
- 目录后台刷新不应重置参数；Task 2 验证切换与刷新后的编辑值。
- 只变更分红/价格口径时也应标记旧结果；Task 1 比较完整请求，Task 2 验证恢复配置。
- 报告加载失败、非法 ID、快速切换与关闭不应展示错误记录；Task 3 验证 URL 驱动的详情状态。

---

### Task 1: Strategy state rules

**Files:**
- Create `frontend/src/utils/strategyWorkspace.ts`
- Create `frontend/src/utils/strategyWorkspace.test.ts`

**Interfaces:**
- `StrategyParameters = Record<string, number | string>`
- `SavedStrategyRun = { version: 1; request: StrategyBacktestRequest; result: StrategyBacktestResponse }`
- `mergeStrategyParameters(strategy: StrategyInfo | undefined, saved: unknown): StrategyParameters`
- `readSavedStrategyRun(value: unknown): SavedStrategyRun | null`
- `sameStrategyRequest(left: StrategyBacktestRequest, right: StrategyBacktestRequest): boolean`

- [x] Write failing tests: schema defaults plus known valid edits; wrong type/unknown parameter discard; malformed saved run rejected; correct run retained; stock/params/order-independent keys/price mode/dividend changes compared.
- [x] Run `npm test -- src/utils/strategyWorkspace.test.ts`; confirm failure before implementation.
- [x] Implement validation/merge/comparison using existing types. Validate arrays and nested result fields used by renderers, preserve optional metadata.
- [x] Re-run targeted tests and typecheck.

### Task 2: Preserve strategy work across navigation

**Files:**
- Modify `frontend/src/pages/Strategies.tsx`
- Modify `frontend/src/components/strategies/StrategyResults.tsx`
- Modify `frontend/src/components/strategies/StrategyResults.test.tsx` (controlled tab harness)
- Modify `frontend/src/components/strategies/StrategyConfig.tsx` and `frontend/src/components/StockSearch.tsx` (opt-in clear control)
- Create `frontend/e2e/research-continuity.spec.ts`

**Interfaces:**
- Consume Task 1 functions/types.
- Add `activeTab: string` and `onTabChange: (key: string) => void` to StrategyResults props.
- Use `strategies_parameterDrafts`, `strategies_savedRun`, and `strategies_resultTab` with existing `usePersistedState` prefix convention.

- [x] Add e2e using `mockResearchApi`: incoming stock can change/clear, submitted stock follows new selection.
- [x] Add e2e: custom parameter survives strategy switching, page navigation and reload.
- [x] Add e2e: successful backtest selects metrics, preserved result and tab survive navigation/reload without another POST; execution changes show adjusted-config notice; restoring run restores form and URL.
- [x] Run new e2e against baseline and confirm meaningful failures.
- [x] Replace stock overwrite loop with URL-derived stock + synchronized user changes. Preserve unrelated query keys.
- [x] Derive parameters from current strategy defaults plus per-strategy saved edits; remove reset-on-query-refresh effect.
- [x] Save a single versioned result/request pair and selected result tab. Preserve saved backtest when generating signals; choose market tab after signals and metrics after backtest.
- [x] Compare the full request for result mismatch and chart overlays. Key loaded chart data to stock/date/source to avoid mismatched candles while loading.
- [x] Add existing-component actions “恢复本次配置” and “查看历史”; recovery updates all request fields without executing anything.
- [x] Pass controlled tab state to StrategyResults, falling back to market when no backtest exists.
- [x] Re-run new e2e and targeted unit tests.

### Task 3: Direct report links

**Files:**
- Modify `frontend/src/pages/Dashboard.tsx`
- Modify `frontend/src/pages/AgentAnalysis.tsx`
- Create `frontend/e2e/report-navigation.spec.ts`

**Interfaces:**
- `/agent?report=<positive safe integer>` controls report modal.
- Existing `getAnalysisDetail(id)` query remains responsible for fetching content.

- [x] Add e2e for dashboard latest report and recent-report row ID, direct-link refresh, close preserving unrelated params, invalid ID ignored, failed detail retry and browser back.
- [x] Run tests before code change to observe missing direct navigation.
- [x] Update dashboard report actions to include corresponding record ID; “全部” stays plain list.
- [x] Derive report modal visibility and selected ID from search params. Opening updates URL; closing removes only report via replace. Validate integer safely. No second local modal state source.
- [x] Re-run report e2e and related existing tests.

### Task 4: Verification and review

- [x] Run `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`.
- [x] Run affected e2e plus existing research/history/dashboard suites; broaden to full e2e once targeted tests pass if runtime allows.
- [x] Prettier check all changed source and e2e files; report baseline-only failures separately.
- [x] Inspect current diff independently for correctness and request/config/source consistency; fix verified issues within scope and retest.
- [x] Use gstack with existing local fixtures to verify observable flow and view desktop/mobile rendering. Stop the temporary server and remove inspection-only setup afterward.
- [x] Update this plan's checkboxes and report shipped behavior, checks, and current-tag-only restoration boundary.

## Execution choice

在当前会话直接实施并集中验证。用户已同意优化方向，设计检查没有重要未决问题；常规工程选择由实现方承担，不重复请求授权。
