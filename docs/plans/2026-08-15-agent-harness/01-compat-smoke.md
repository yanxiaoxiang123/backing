# 01 依赖兼容性 smoke

- **用户可见交付**：主后端 requirements 锁定 LangGraph 栈（`langgraph`、`langgraph-checkpoint-sqlite`、`langchain-openai`，与 `langchain-core==1.5.4` 兼容的固定版本），`TradingAgents-astock` 以 editable 方式可导入；兼容性结论书面记录（对齐 or 隔离）。
- **验收标准**：
  1. `pip install -r requirements.txt` 在 conda `backing` 环境可完整复现新依赖集；`requirements.lock` 重新生成并提交。
  2. smoke 脚本能构建 `TradingAgents-astock` 的 graph（SQLite saver）并跑通其 `test_checkpoint_resume.py`。
  3. 结论落档：`docs/plans/2026-08-15-agent-harness/compat-decision.md`——若 API 兼容，记录最终版本矩阵；若不可调和，给出隔离方案（独立进程/环境 + HTTP 适配接缝），并同步修订任务 05/07/09 接缝说明。
  4. 既有后端 166 测试全绿（新增依赖不得破坏现网）。
- **阻塞任务**：None
- **委派**：eligible（独立的依赖实验，输入输出边界清晰）
