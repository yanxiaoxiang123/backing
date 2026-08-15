# 13 收尾验收门禁 + 交付

**交付**：全量回归证据汇总、规格→计划→实现一致性核查、交付说明。

**范围**：
- 后端：全量 pytest（含新增）、`ruff check`；迁移 upgrade↔downgrade 往返；TradingAgents 包测试。
- 前端：`npm run typecheck` + lint + format:check + build + 全量 Vitest。
- 评测：golden cases 缓存回放；引用覆盖率 ≥95%、无前视 100%、schema 校验全过证据。
- 汇总：对照规格 v2 验收门槛逐项列证据；工作树状态与 commit 链；后台连跑状态；交付说明（未完成项/风险/如何运行）。

**验收**：所有命令绿色输出；门槛逐项证据表；最终本地 commit（不推送）。

**阻塞**：全部
**委派**：ineligible（全局验收）
