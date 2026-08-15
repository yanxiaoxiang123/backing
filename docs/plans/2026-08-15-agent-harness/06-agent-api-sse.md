# 06 agent_api HTTP + SSE

- **用户可见交付**：`backend/app/agent_api/` 提供 `POST /api/v1/agent-runs`（创建）、`GET /api/v1/agent-runs/{run_id}`（状态）、`GET /api/v1/agent-runs/{run_id}/events`（SSE，支持 `Last-Event-ID` 断线重放）、`POST /api/v1/agent-runs/{run_id}/resume`、`POST /api/v1/agent-runs/{run_id}/cancel`、`GET /api/v1/agent-runs/{run_id}/artifacts`。
- **验收标准**：
  1. httpx 异步测试：创建后 SSE 收到计划→节点→产物→完成事件；断开后带 `Last-Event-ID` 重连从断点继续且无重复。
  2. cancel/resume 端点行为与 05 的语义一致；未授权 401、超限 429 沿用既有认证/限流约定。
  3. 事件 JSON Schema 与前端契约一致（类型枚举：plan/step_start/tool_call/artifact/approval/complete/failed/cancelled + seq）。
  4. 预算参数在创建时校验（非法值 422）。
  5. `ruff check` + 全量 pytest 绿。
- **阻塞任务**：05
- **委派**：ineligible（认证/限流/错误约定与既有 API 层耦合，主 agent 执行）
