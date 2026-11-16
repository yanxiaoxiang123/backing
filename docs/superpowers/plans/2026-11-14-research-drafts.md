# Research Draft Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 研究文字跨关闭、切页、刷新和工作台交接保留，发送失败可直接重试。

**Architecture:** ChatInput 增加受控输入与异步提交反馈；ResearchChatInput 对接 sessionStorage 草稿及 useAgentChat 的提交确认结果。按会话或股票隔离，源草稿按版本条件清空/迁移。

**Tech Stack:** React 18、TypeScript、AntD、Vitest/Testing Library、Playwright。

**Spec:** `docs/superpowers/specs/2026-11-14-research-drafts-design.md`

## Global Constraints

- 在当前功能分支实施，保留前两轮及用户其他工作，不提交、推送或部署。
- 只改前端，不新增依赖、后端契约、模型/行情/订单调用。
- 草稿只存当前标签页 sessionStorage；存储不可用时内存降级，不保证刷新恢复。
- 不将未发送文字加入 URL，不因关闭、交接、刷新或恢复而自动提交。
- 沿用既有样式、欢迎问题和研究导航。

## Review Focus

- 首次发送创建会话后提交失败：原文在新会话可恢复，不能遗落于新研究身份。Task 2 浏览器用例。
- 旧提交完成时已切到另一个会话：不能清掉其他草稿或源草稿的后续修改。Task 1 条件清空与 Task 2 浏览器回归。
- 会话恢复/股票预填晚到：不能覆盖已输入或主动清空的内容。Task 1 受控组件及 Task 2 浏览器回归。
- sessionStorage 损坏/拒绝读写：编辑和发送仍可用，不影响其他存储。Task 1 存储单测。
- 连点/Enter/中文输入法：只提交一次，失败后可再次发送。Task 1 真实输入组件单测及 Task 2 POST 计数。

### Task 1: 草稿与提交确认基础

**Files:** Create `frontend/src/utils/chatDrafts.ts`, `.test.ts`; create `frontend/src/components/chat/ChatInput.test.tsx`; modify `frontend/src/components/chat/ChatInput.tsx`, `frontend/src/hooks/useAgentChat.ts`, `.test.ts`.

**Interfaces:** `ChatSendResult = {accepted: boolean; threadId: string|null}`; hook `send(content, context?, onThreadCreated?): Promise<ChatSendResult>`, with synchronous creation callback before identity publication. Draft storage provides stable versioned snapshots, subscribe, read/write, conditional clear/move, page-local submission locks, and a scope builder preferring thread over normalized stock. ChatInput optional `value`/`onChange`/`submitting`, async `onSend` returns boolean or void.

- [x] Write failing tests for scope isolation, explicit empty value, corrupt/blocked storage, version-conditional clear/migration.
- [x] Run `npm --prefix E:/stock/frontend test -- src/utils/chatDrafts.test.ts`; expected missing-module failure, then implement minimal store and rerun to pass.
- [x] Write component tests proving text remains until acceptance, rejection retains text, rapid submit is suppressed, IME/Shift+Enter behavior, controlled input is not overwritten by initialValue updates. Run before implementation and observe missing behavior.
- [x] Implement async input lock/loading and optional controlled editing. Host owns controlled clearing; original uncontrolled usage stays compatible.
- [x] Add hook receipt tests: accepted turn, rejected turn after thread creation, creation failure/unavailable. Run before implementation then return accurate receipts while retaining existing stale-response guards and error UI.
- [x] Run all Task 1 tests and typecheck; expected all pass.

### Task 2: 副驾驶与工作台接入

**Files:** Create `frontend/src/components/chat/ResearchChatInput.tsx`; modify `frontend/src/components/research/ResearchCopilot.tsx`, `frontend/src/pages/AgentWorkspace.tsx`; create `frontend/e2e/research-drafts.spec.ts` using existing `fixtures/researchEntry.ts` via route overrides.

**Interfaces:** ResearchChatInput consumes Task 1 draft storage/receipts, current/restoring thread identity, stock and initialValue/welcome draft. Both hosts use the same scope rules. Clear/move only the unchanged submitted snapshot; never overwrite an existing destination draft.

- [x] Add browser regressions for close/reopen, reload, unsent handoff with no POST or URL text, per-thread drafts, explicit clear surviving presets, existing-thread rejection/retry and first-create-then-reject recovery.
- [x] Run new browser tests before integration; expected draft loss/early clear failures.
- [x] Implement wrapper and replace both host ChatInput usages. Restore by route target during thread fetch; ignore late preset changes after edits.
- [x] Add delayed acceptance with thread switch regression; assert both correct target request and retained other draft.
- [x] Run new plus existing research-entry/workspace browser tests; expected pass.

### Task 3: 完整验证与审查

- [x] Full frontend unit suite, typecheck/lint/format/build/chunk budgets and frontend diff check.
- [x] One independent read-only review against this round's before snapshots; fix Important/Critical issues with failing regressions.
- [x] Full serial Playwright run with local fixture responses; desktop/mobile inspection of affected input and pending/failure states. Earlier full run 111/112 exposed a shared dropdown motion bug. User requested the remaining failures be fixed; the minimal transition-property priority repair and two new regressions now pass the full suite 114/114 (4.1m), with 277/277 unit tests and checks/build passing. Historical failures remain in the verification report.
- [x] Stop temporary preview/remove task-owned startup setup; retain uncommitted execution snapshots/logs.
- [x] Write `docs/reviews/2026-11-14-research-drafts-verification.md` with measured results, scope choices and limits.

## Execution choice

沿用当前会话内实现与末尾一次独立审查。以上任务共享输入、确认结果与适配组件，属于同一变更，顺序执行。用户已委托持续优化，不重复询问例行实现选择。实现方取舍写入本轮 ledger；设计检查和代码审查不是用户批准。
