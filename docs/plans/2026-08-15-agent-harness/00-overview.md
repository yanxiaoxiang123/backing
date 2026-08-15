# Agent Harness 统一运行时 — 实施计划总览

> 日期：2026-08-15
> 规格基线：`docs/specs/2026-08-15-agent-harness-runtime.md`（已批准）
> 执行模式：adaptive（主 agent 主导，聚焦子 agent 用于独立任务）
> 提交策略：每个切片实现并验证通过后本地 commit（不推送）
> 交付终点：已验证的本地改动
> 实施前沿：P0–P2 核心实现；P3 仅规划；P4 仅设计附录

## 依赖图与波浪（Frontier）

```text
Wave A（无阻塞，可并行启动）
  01 依赖兼容性 smoke
  02 领域契约 schema（backend/app/domain/）
  03 评测骨架（evals/，10 golden cases，缓存回放）
  13 P3 规划切片 + P4 设计附录（纯文档，spec 派生）

Wave B
  04 run 持久化（5 张表 + 迁移 + repository 接口）     ← 无阻塞
  08 类型化 Tool Gateway（tools/ + 权限分级）          ← 02

Wave C
  05 LangGraph Runtime 核心（预算/checkpoint/取消/恢复/事件） ← 01, 04

Wave D
  06 agent_api HTTP + SSE（run/stream/resume/cancel/artifact） ← 05
  09 Supervisor 动态路由图（专家节点 + 结构化输出）      ← 05, 08, 02

Wave E
  07 旧端点 adapter（/api/v1/agent/* 桥接新运行时）     ← 05, 06
  10 前端三栏工作台（AgentWorkspace + SSE + 审批卡）    ← 06
  11 DSH POC（dsh-quant-plugin，独立 UI，session↔run）  ← 06, 08

Wave F
  12 端到端评测门禁（golden cases 走新运行时 + 验收演示） ← 03, 07, 09
```

## 任务清单

| # | 任务 | 交付 | 阻塞 | 委派 |
|---|---|---|---|---|
| 01 | 依赖兼容性 smoke | 主后端锁定 LangGraph 栈；TradingAgents 兼容结论 | None | eligible |
| 02 | 领域契约 schema | 六大 Pydantic schema + as_of/source_id 契约 + 测试 | None | eligible |
| 03 | 评测骨架 | evals/ 数据集、缓存回放、确定性评分器 | None | eligible |
| 04 | run 持久化 | 5 表 + Alembic 迁移 + repository 接口 | None | ineligible（共享 models/migrations 耦合） |
| 05 | Runtime 核心 | 预算、checkpoint、取消、恢复、事件序号 | 01, 04 | ineligible（核心耦合） |
| 06 | agent_api + SSE | run/stream/resume/cancel/artifact 端点 | 05 | ineligible（认证/限流约定耦合） |
| 07 | 旧端点 adapter | /api/v1/agent/* 桥接且既有测试全绿 | 05, 06 | ineligible（遗留耦合） |
| 08 | Tool Gateway | 八域类型化工具 + 权限分级 + allowlist | 02 | eligible |
| 09 | Supervisor 图 | 动态路由 + 专家节点 + 结构化输出 | 05, 08, 02 | ineligible（runtime+tools+LLM 耦合） |
| 10 | 前端工作台 | AgentWorkspace 三栏 + 四视图 + SSE + 审批卡 | 06 | eligible |
| 11 | DSH POC | dsh-quant-plugin + 独立 UI + session↔run 映射 | 06, 08 | eligible |
| 12 | 端到端评测门禁 | golden cases 走新运行时 + P2 验收演示 | 03, 07, 09 | ineligible（全局耦合） |
| 13 | P3 规划 + P4 附录 | 模拟盘切片规划与实盘设计附录 | None | ineligible（文档连续性） |

## 执行约定

1. **每任务完成标准**：验收标准逐项有测试/命令证据；`ruff check` 与相关 pytest 全绿；涉及前端则 `npm run build` 全绿；仓库处于连贯状态。
2. **提交**：任务完成、验证通过后按 `feat:`/`refactor:` 惯例本地 commit；任务内不中途提交。
3. **TDD**：有稳定接缝的可执行行为先写失败测试（schema 校验、事件序号、预算、取消、SSE 重放、工具权限、A 股成交规则评分）。
4. **委派任务**：子 agent 交付后主 agent 验收（跑验收命令 + 读关键 diff）再 commit；不合格退回修正。
5. **冲突处理**：任务 01 若得出"TradingAgents 必须隔离进程/环境"的结论，05/07/09 的接缝需按隔离方案调整并回报用户；任务 11 若 Python SDK 与当前环境不可调和，降级为 HTTP 直连 + 文档记录，并回报用户。
6. **禁止**：推送、开 PR、部署、删除既有行为（adapter 退役须待 10/12 完成后另行评估）。
