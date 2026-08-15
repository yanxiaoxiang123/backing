# Agent Harness P2 收尾 + P3 模拟盘 — 实施计划总览

> 日期：2026-08-15
> 规格基线：`docs/specs/2026-08-15-agent-harness-runtime-v2.md`（已批准）
> 上游：`AGENT_QUANT_UPGRADE_PLAN.md`；v1 计划 `docs/plans/2026-08-15-agent-harness/`（P0–P2 已完成）
> 执行模式：adaptive（主 agent 主导；委派仅用于聚焦独立切片，且先探测委派可用性）
> 提交策略：每个切片实现并验证通过后本地 commit（不推送）
> 交付终点：已验证的本地改动 + 模拟盘引擎后台连跑证据
> 实施前沿：P2 四个延期项 + P3 全实现；P4 保持附录

## 依赖图与波浪

```text
Wave A（无阻塞，可并行启动）
  01 研究数据层（新闻/公告/财报/指数 + SQLite 缓存）
  03 模拟盘持久化 + 撮合纯函数 + 重放
  06 TA 子图 + gateway vendor 深接线
  07 前端参数编辑 → 新 run
  08 artifact 工作区写入与查看
  11 DSH 运行时装配 E2E

Wave B
  02 研究专家升级 + 引用 ≥95% 评测      ← 01
  04 execution.paper.* 工具域           ← 03
  09 盘前计划/盘后归因                  ← 03

Wave C
  05 审批状态机 + 撮合调度 + soak 循环   ← 03, 04
  10 告警系统                           ← 03, 05

Wave D
  12 模拟盘 E2E + 后台连跑启动 + 恢复演练 + runbook ← 03, 04, 05, 09, 10

Wave E
  13 收尾验收门禁 + 交付               ← 全部
```

## 任务清单

| # | 任务 | 用户可见交付 | 阻塞 | 委派 |
|---|---|---|---|---|
| 01 | 研究数据层 | 新闻/公告/财报/基准指数确定性服务 + 缓存 + 网关工具 | None | eligible（独立新模块，接缝稳定） |
| 02 | 研究专家升级 | 真实引用研究专家；golden 引用覆盖率 ≥95% | 01 | ineligible（experts+evals+supervisor 耦合） |
| 03 | 模拟盘核心 | 账户/持仓/订单/成交/流水事件表；确定性撮合；重放 | None | ineligible（共享 models/migrations 耦合） |
| 04 | paper 工具域 | `execution.paper.*` 提议/撤单/持仓/账户查询 | 03 | ineligible（网关+权限耦合） |
| 05 | 审批+调度 | 审批卡状态机（一次性窗口）；每日撮合调度；soak 循环 | 03, 04 | ineligible（状态机+调度+API 耦合） |
| 06 | TA 深接线 | TradingAgents 子图全取数经 gateway vendor；claims/artifact 归一 | None | ineligible（runtime+gateway+TA 耦合） |
| 07 | 参数编辑 UI | 回测页签改参数 → 新 run_id；旧产物不可变 | None | eligible（纯前端，API 接缝已稳定） |
| 08 | artifact 工作区 | 节点写每 run 工作区文件；列表/下载；查看器接线 | None | ineligible（runtime 节点耦合） |
| 09 | 归因 | 盘前计划视图；对 sh.000300 的收益分解纯函数 + 面板 | 03 | ineligible（跨前后端+API 耦合） |
| 10 | 告警 | 阈值可配置；落库 + SSE + 工作台面板 | 03, 05 | ineligible（跨 SSE/前端/配置耦合） |
| 11 | DSH 装配 | 克隆内构建 runtime；quant.gateway 消费者；审批 E2E | None | eligible（隔离环境构建，低耦合） |
| 12 | 模拟盘集成验证 | E2E 黄金路径；后台连跑启动；恢复演练 100%；重放审计；runbook | 03, 04, 05, 09, 10 | ineligible（全局耦合） |
| 13 | 收尾验收门禁 | 全量回归 + 评测证据汇总 + 交付说明 | 全部 | ineligible（全局验收） |

## 执行约定

1. **每任务完成标准**：验收标准逐项有测试/命令证据；`ruff check` 与相关 pytest 全绿；涉及前端则 `npm run build` 全绿；仓库处于连贯状态。
2. **提交**：任务完成、验证通过后按 `feat:`/`refactor:` 惯例本地 commit；任务内不中途提交；不推送、不建 PR。
3. **TDD**：有稳定接缝的可执行行为先写失败测试（撮合规则、审批状态机、重放、引用覆盖率、gateway vendor 无直连、告警阈值）。
4. **委派**：先探测委派可用性（本轮首任务前发起一次探针）；可用则对 eligible 切片委派，主 agent 验收（跑验收命令 + 读关键 diff）再 commit；不可用则主 agent 全量执行并在执行备注记录。
5. **禁止**：推送、开 PR、部署、删除既有行为；改动 `deepseek-harness/` 源文件（构建产物除外）；Agent 获得生产 Shell/数据库写权限/任意代码执行。
6. **后台连跑**：切片 12 起在后台启动模拟盘 soak 引擎并持续运行，交付时报告累计运行时长与事件数。

## 执行备注（随进度追加）

- 2026-08-15：grilling 七项决策已确认（研究数据层/TA 接线/撮合规则/审批 TTL/P3-5 方式/DSH 构建位置）。
- 2026-08-15：**子 agent 委派仍不可用**（探针启动后无消息失败，与上一轮一致）。切片 01/07/11 原标记 eligible，全部改由主 agent 亲自执行；验收标准不变。
- 2026-08-15（切片 01–11 完成）：研究数据层（引用覆盖率 1.0）、paper 撮合/审批/soak、TA 子图 gateway vendor、artifact 工作区、参数编辑、归因、告警、DSH 运行时装配（exe 191MB + SDK + quant.gateway E2E）全部提交。
- 2026-08-15（切片 12）：E2E 黄金路径脚本（`backend/scripts/paper_e2e_demo.py`）、重放审计工具（`backend/scripts/paper_replay_audit.py`）、4–8 周验收 runbook（`docs/runbooks/paper-trading-4-8-week-validation.md`）交付；**修复两个真实缺陷**：① soak 与手动 match 并发 → 进程级撮合锁；② `autoflush=False` 会话下 `max(seq)` 看不到挂起事件 → seq 分配前显式 flush。恢复演练 100%（杀进程→重启→单次成交→重放 PASS）；模拟盘引擎后台连跑中。
