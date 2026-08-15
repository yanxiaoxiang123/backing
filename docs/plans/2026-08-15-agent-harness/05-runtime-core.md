# 05 LangGraph Runtime 核心

- **用户可见交付**：`backend/app/agent_runtime/` 提供 run 生命周期——创建 run（目标 + 预算）、执行 graph、节点间 checkpoint（SQLite saver）、事件按 `seq` 单调落库、取消在节点边界生效、中断后恢复、外部调用幂等键。
- **验收标准**：
  1. pytest 证明：注入失败后从最近 checkpoint 恢复，已执行节点不重复执行（幂等键去重）。
  2. 预算（最大轮次/工具调用/token/耗时）超限自动终止，run 状态与原因落库。
  3. 取消请求后 run 在下一节点边界停止并记录取消原因；`asyncio` 语义测试覆盖。
  4. 每个节点产生结构化事件（计划/节点开始/工具调用/产物/完成/失败），`seq` 单调且可整段重放。
  5. TradingAgents 的图可经统一 facade 注入同一 checkpointer 与事件发射器（按任务 01 结论实现接缝）。
  6. `ruff check` + 全量 pytest 绿；无 LLM 真实调用（测试用 fake model）。
- **阻塞任务**：01, 04
- **委派**：ineligible（核心耦合，主 agent 执行）
