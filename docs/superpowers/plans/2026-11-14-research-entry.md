# Research Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 交接副驾驶会话与股票，告警链接直达并可恢复失败状态。

**Architecture:** 复用当前聊天 hook 和 React Router，为 hook 增加可选路由同步接口；工作台面板由 URL 驱动；告警面板共享 shell 的 TanStack Query 缓存。

**Tech Stack:** React 18、TypeScript、React Router 6、AntD、TanStack Query、Vitest、Playwright。

**Spec:** `docs/superpowers/specs/2026-11-14-research-entry-design.md`

## Global Constraints

- 当前功能分支原地实现，保留首轮与用户其他改动，不提交、推送、部署。
- 不新增依赖，不改后端契约，不调用真实模型、供应商或模拟订单。
- 沿用现有视觉体系和现有 PageContext 字段；仅传合法股票、会话 ID 和允许的面板名。
- URL 改动保留其他参数与浏览器历史状态；无自动发送、创建会话或标记已读。

## Review Focus

- 当前工作台仍挂载时换会话或前进后退，晚返回数据不得覆盖新目标。Task 1 hook 回归与 Task 2 浏览器用例覆盖。
- 聊天选择/创建与面板切换共用 URL，不得丢 thread_id 或 stock。Task 2 浏览器用例覆盖。
- 手机抽屉与桌面折叠偏好不能遮住显式告警入口，也不能阻止用户再次关闭。Task 2 浏览器用例覆盖。
- 告警刷新/标记失败保留已知数据，不能变成空列表或虚假已读。Task 2 浏览器用例覆盖。
- 无效面板、无效/不在列表告警、缺失股票应安全回退，不执行写操作。Task 1 规则与 Task 2 浏览器用例覆盖。

### Task 1: 交接规则与会话 URL 同步

**Files:** Create `frontend/src/utils/researchNavigation.ts` and `.test.ts`; modify `frontend/src/hooks/useAgentChat.ts` and `.test.ts`, `frontend/src/components/research/ResearchCopilot.tsx`, `frontend/src/App.tsx`.

**Interfaces:** `workspaceHref({threadId?, stockCode?, panel?, alertId?}): string`; `readResearchPanel(value: string|null): ResearchPanelKey|null`; `readAlertId(value: string|null): number|null`. Hook adds optional `threadId?: string|null` and `onThreadChange?: (id: string|null)=>void`; default callers remain compatible.

- [x] Add literal link/validation tests and controlled thread change/back-to-empty hook tests; run to observe missing behavior.
- [x] Implement rule helpers, opt-in route synchronization and native-history state preservation. Separate controlled restoration from legacy initial URL restoration; retain stale-response guards.
- [x] Pass current thread and normalized stock explicitly from副驾驶; App context supports current stock query as well as stock route.
- [x] Verify targeted unit tests and typecheck.

### Task 2: 面板路由与告警恢复

**Files:** Modify `frontend/src/pages/AgentWorkspace.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/App.tsx`, `frontend/src/components/agent/AlertsPanel.tsx`; create `frontend/e2e/research-entry.spec.ts` and `frontend/e2e/fixtures/researchEntry.ts`.

**Interfaces:** Workspace `panel`/`alert` query parameters; `AlertsPanel({selectedAlertId?: number|null})`; shared query key `['system','alerts']`.

- [x] Add browser regressions: query stock/context and active conversation handoff without POST; workspace same-route conversation change and URL panel preservation; dashboard/side alert entry on collapsed desktop/mobile; refresh/back; invalid panel/alert; failed reads/mutations and recovery/counter update.
- [x] Run new tests against current implementation and inspect expected failures.
- [x] Integrate controlled chat URL synchronization. Derive panel from URL and reveal explicit destinations once; preserve ability to close/collapse.
- [x] Update dashboard record/all-alert and sidebar alert links. Keep task counter unchanged.
- [x] Share query data; implement honest loading/error/empty/refresh/read feedback, selected record focus and absent-record notice. No optimistic read before successful API response.
- [x] Run new and existing workspace/dashboard/navigation/continuity browser tests.

### Task 3: 验证与独立审查

- [x] Run full unit suite, typecheck, lint, format:check, build/chunk budgets, frontend diff check.
- [x] One independent read-only review of this round's diff; fix important issues with failing regressions.
- [x] gstack desktop/mobile fixture inspection; stop temporary preview and remove temporary setup after inspection.
- [x] Record behavior, evidence, limits and any failures in `docs/reviews/2026-11-14-research-entry-verification.md`.

## Execution choice

沿用当前会话内执行与末尾一次独立审查，继续用户已交由实现方取舍的第二轮。规格 builder check 无重要未决项；该检查不是用户批准。所有工程取舍及验证证据写入本轮独立 ledger，保留未提交实现记录。
