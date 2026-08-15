# 11 DeepSeek Harness POC

- **用户可见交付**：`dsh-quant-plugin/`（profile + 插件）固定 DSH commit `47f9438`，经官方 Python SDK 启动 bundled runtime 作为独立 Web UI；对话中可调用 Tool Gateway 的只读量化工具并渲染结构化结果；工具审批卡可用；`session_id ↔ run_id` 映射由后端保存；默认移除 Bash/编辑器/宿主文件工具。
- **验收标准**：
  1. 一键启动脚本可在本地拉起独立 UI 并完成一次"查 K 线 → 发起分析 run"的对话闭环（人工演示 + 截图记录）。
  2. 插件只通过 FastAPI 网关调用（无直连数据库）；只读工具可用，策略/回测写入被权限拒绝并给出提示。
  3. 审批流程可演示：高风险工具调用出现审批卡，拒绝则终止。
  4. session↔run 映射在 `agent_runs` 表可查；run 事件可在后端 SSE 重放。
  5. POC 结论落档（可继续 fork UI 与否的评估依据）；不修改 `deepseek-harness/` 上游 clone 本体（以外部 profile 方式使用）。
- **阻塞任务**：06, 08
- **委派**：eligible（独立包，边界清晰；需在 prompt 中给出 SDK 用法与网关端点契约）
