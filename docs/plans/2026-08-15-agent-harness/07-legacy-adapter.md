# 07 旧端点 adapter

- **用户可见交付**：`/api/v1/agent/*`（analyze/history 等）在过渡期行为不变，内部改经新运行时执行并落 run/step/tool_call 记录；旧 AI 分析页面与既有测试无感。
- **验收标准**：
  1. `POST /api/v1/agent/analyze` 返回结构不变；既有 `test_api_contracts`、`test_pipeline` 全绿。
  2. 每次旧端点调用产生一条 `agent_runs` + 阶段 step/tool_call 记录，事件可在新 SSE 端点重放（实现"旧入口、新底座"）。
  3. LLM 不可用时错误语义与旧版一致（清晰 503 而非 500）。
  4. 未增加任何第二套状态机；`ruff check` 全绿。
- **阻塞任务**：05, 06
- **委派**：ineligible（遗留 API 契约耦合，主 agent 执行）
