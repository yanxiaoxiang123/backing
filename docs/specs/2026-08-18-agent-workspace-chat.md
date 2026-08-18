# Agent 工作台聊天化改造规格

> 日期：2026-08-18
> 上游依据：`plan.md`（2026-08-18）、规格 v2 `docs/specs/2026-08-15-agent-harness-runtime-v2.md`（已批准，决策 13–15 认证、25–26 DSH 装配保持有效）、`dsh-quant-plugin/README.md`
> 状态：待用户批准
> 决策记录：grilling 已由用户确认 3 项根决策（D1 seam-first、D2 fake seam 逼真+真 run、D3 完全取代旧 objective-run）。

## 1. 问题陈述

现有 `AgentWorkspace` 中栏是 `AgentConversation`——目标式单次 run（输入研究目标 → `useAgentRun.start(objective)` → 渲染 run 事件流），并非真正的多轮聊天；左栏是两项静态导航（工作台/回测历史）；DeepSeek Harness 风格的会话上下文、推理展示、量化工具调用体验未接入。同时，真实 DeepSeek Harness Python SDK 与运行时**当前未安装**（`deepseek_harness` 不可导入，`backend/data/dsh_sessions/` 不存在，`DEEPSEEK_API_KEY`/`QUANT_API_KEY` 未配置），直接按真实 SDK 端到端构建会被环境与密钥供给阻塞。

目标：以 **seam-first** 方式在现有 React 工作台中原生实现 DeepSeek Harness 风格聊天界面——左会话列表 / 中多轮聊天 / 右栏自动跟随最近一次量化 run；后端以抽象接缝解耦真实 SDK，先以逼真 fake seam 验证全栈（含真实 run 创建与右栏联动），真实 `DeepSeekHarness` 接线延后为独立切片。不修改 `deepseek-harness/` 上游源码。

## 2. 用户可见的解决方案

1. **左栏会话列表（约 240px）**：新对话按钮、会话标题、最近更新时间、运行状态、点击切换；支持软归档。
2. **中栏多轮聊天**：用户消息右气泡，助手回复 Markdown（`react-markdown + remark-gfm`，不启用原始 HTML）；可折叠的思考过程与工具调用行；"Deep diving…"运行状态；滚动离开底部时显示"回到底部"按钮。
3. **底部输入区**：固定底部、自动增高；Enter 发送、Shift+Enter 换行；运行中发送的消息进入队列，发送按钮切换为停止按钮。
4. **右栏保留并跟随 run**：行情与结论、证据、回测、风险、产物面板保持现有功能，并自动 `attach` 当前会话最近一次量化 run（复用现有 run SSE）。
5. **可恢复**：URL 保存 `thread_id`；刷新后恢复聊天历史、SSE 游标（`Last-Event-ID`）与右栏最近 run。
6. **后端解耦**：新增 `agent_chat_threads/turns/events` 表与 `HarnessChatService` 单例；抽象 `HarnessChatSeam` 接口 + 逼真 fake 实现，fake seam 真实创建 `agent_runs` 并发布 `run.linked`，使 dev 内无 SDK/密钥即可演示聊天与右栏联动。

## 3. 用户故事 / 行为

- **US-C1 会话生命周期**：作为用户，我可以新建、切换、归档会话；新建会话分配 `thread_id`，首条用户消息前 36 个字符作为默认标题；归档后会话从默认列表移除但可恢复。
- **US-C2 多轮上下文**：作为用户，助手回复保留同一会话的历史上下文；同一 `thread_id` 的多轮消息按 FIFO 由单 worker 顺序执行，运行中继续发送的消息排队。
- **US-C3 流式事件**：作为用户，我看到助手按事件流渐进输出：reasoning（折叠）、assistant 文本块、tool call 与 tool result（折叠为工具行）；事件经 SSE 推送，断线后从 `Last-Event-ID` 续传，不丢不重。
- **US-C4 量化 run 联动**：作为用户，当助手调用 `quant_run_analysis` 时，后端真实创建 `agent_runs` 记录（写入 `thread_id`）与 run 事件，并发布 `run.linked`；前端立即 `attach(run_id)` 连接现有 run SSE，右栏行情/证据/回测/风险/产物随之更新。
- **US-C5 队列与停止**：作为用户，运行中我可以停止当前 turn（按钮切换为停止）；停止后当前 turn 标记 `cancelled`，队列中尚未开始的 turn 保留并可继续；新消息仍可入队。
- **US-C6 断线恢复**：作为用户，刷新或网络中断后，聊天历史、未完成 turn 状态与 SSE 游标按 `thread_id` + `Last-Event-ID` 恢复，右栏回到最近一次 run。
- **US-C7 重启恢复**：作为运维者，服务重启时未完成 turn 标记 `interrupted`（不自动重复提交），尚未开始的 queued turn 继续执行；`thread_id` ↔ `session_id` 映射可查可恢复。
- **US-C8 幂等提交**：作为用户/客户端，重复提交同一 `Idempotency-Key` 的 turn 不产生重复执行，返回原 turn 结果。
- **US-C9 归档**：作为用户，归档会话为软删除，不在默认列表显示但可恢复，其 run 与事件保留。
- **US-C10 取消语义**：作为用户，停止操作在 seam 层终止并重建本项目持有的 runtime 等价物（真实 SDK 单会话 cancel 暂不可用，留作开放问题）。

## 4. 实施决策与约束

### 接缝与解耦

1. **D1 Seam-first**：定义抽象 `HarnessChatSeam`（输入 `session_id`/用户消息，产出可重放的 reasoning/assistant/tool 事件流，并可发起 `quant_run_analysis` 工具调用）+ 逼真 `FakeHarnessChatSeam` 实现；真实 `DeepSeekHarness` 适配器（`from deepseek_harness import DeepSeekHarness`）作为后续切片实现，接口设计需前瞻兼容真实 SDK 的事件 schema 与单会话 cancel 限制。
2. **D2 Fake seam 逼真 + 真 run**：`FakeHarnessChatSeam` 模拟推理事件、助手 Markdown 回复、并模拟 `quant_run_analysis` 工具调用 → **真实**经 `agent_runtime` stores 创建 `agent_runs` 行（写入 `thread_id`）与 run 事件 → 发布 `run.linked`；dev 内无 SDK/密钥即可演示聊天 + 右栏联动；fake 行为须确定性以便测试。
3. **D3 完全取代旧 objective-run**：移除 `AgentConversation` 与 `useAgentRun.start(objective)` 入口；分析只经聊天 turn 驱动；右栏仍由 run 数据驱动（经 `attach`）。

### 数据模型

4. **D4 三新表 + 复用 run**：新增 `agent_chat_threads`（`thread_id` 唯一、Harness `session_id`、标题、状态、最近 `run_id`、归档标记、时间戳）、`agent_chat_turns`（用户输入、执行状态、最终回复、结束原因、错误、`Idempotency-Key` 唯一约束、`thread_id` 外键）、`agent_chat_events`（可重放原始事件：类型、序号、`turn_id` 外键、载荷 JSON、时间戳）+ Alembic 迁移；复用现有 `agent_runs.thread_id` 列（已存在，补索引以加速右栏"最近 run"查询）。
5. **D5 session 持久化**：`thread_id` 作为 Harness `session_id`，会话写入 `backend/data/dsh_sessions/`（`DSH_SESSION_ROOT` 可配置，默认 `backend/data/dsh_sessions`）。

### 服务与并发

6. **D6 HarnessChatService 单例**：在 FastAPI lifespan 中启动/关闭；单 worker 按 FIFO 执行 turn；运行中消息入队；同实例同时只执行一个 turn（SDK 生命周期、取消与 SQLite 写入安全）；重启将未完成 turn 标 `interrupted`，queued turn 继续。
7. **D7 队列不并入 arq**：本轮用进程内 FIFO（与现有 `job_store`/arq 任务体系并存，不并入），以隔离 SDK 生命周期与单 turn 串行约束；arq 仍服务其他后台任务。

### API

8. **D8 端点集**（认证 + CSRF 保护，挂 `/api/v1`）：
   - `POST /api/v1/agent-chats` 创建会话
   - `GET /api/v1/agent-chats` 分页未归档会话
   - `GET /api/v1/agent-chats/{thread_id}` 恢复 turn 与事件历史
   - `POST /api/v1/agent-chats/{thread_id}/turns` 提交消息（`Idempotency-Key`）
   - `GET /api/v1/agent-chats/{thread_id}/events` SSE（`Last-Event-ID` 重放）
   - `POST /api/v1/agent-chats/{thread_id}/cancel` 停止当前 turn
   - `POST /api/v1/agent-chats/{thread_id}/archive` 软归档

### 前端

9. **D9 useAgentChat + 聊天组件**：新增 `useAgentChat`（会话列表/切换/恢复 + 提交 turn + SSE 合并 + 队列/停止）与聊天组件；中栏采用 Harness 交互（用户右气泡、助手 Markdown、折叠思考与工具行、"Deep diving…"状态、回到底部）。
10. **D10 输入与发送**：输入框固定底部、自动增高；Enter 发送、Shift+Enter 换行；运行中入队、按钮切停止。
11. **D11 Markdown 与安全**：`react-markdown + remark-gfm`，**不启用原始 HTML**（防 XSS）。
12. **D12 路由与恢复**：URL 存 `thread_id`；刷新恢复聊天、SSE 游标与右栏最近 run。
13. **D13 右栏 attach**：`useAgentRun` 新增 `attach(run_id)`，用于观察已有 run（连接现有 `GET /agent-runs/{run_id}/events` SSE），不重复创建任务；`run.linked` 事件触发 attach。

### 认证与安全（沿用 v2 决策 13–15）

14. **D14 认证/CSRF/幂等**：新端点沿用现有 session cookie + 双提交 CSRF；`Idempotency-Key` 去重；Agent 不获得数据库写权限、生产 Shell 或任意代码执行；密钥经环境变量注入、不入库。

### 默认约束（沿用 plan.md）

15. **D15 约束**：仅优化桌面端，不新增移动端聊天布局；顶部全局导航与右侧研究面板保持现有功能；首条消息前 36 字符为默认标题；同实例同时只执行一个 turn。

## 5. 测试接缝与成功标准

| 层 | 接缝 | 验证方式 |
|---|---|---|
| Seam 抽象 | `HarnessChatSeam` + `FakeHarnessChatSeam` | pytest：多轮上下文、事件顺序与可重放、`quant_run_analysis` 真实创建 run + 事件、`run.linked` 发布 |
| 持久化 | 三新表 + `agent_runs.thread_id` | pytest：迁移可正反向、turn/event 重放重建状态、`Idempotency-Key` 去重、归档软删 |
| 服务并发 | `HarnessChatService` 单 worker FIFO | pytest：FIFO 顺序、运行中入队、取消标 cancelled 且队列保留、重启 interrupted 恢复、queued 继续 |
| SSE | `/api/v1/agent-chats/{thread_id}/events` + `Last-Event-ID` | pytest：断线重放不丢不重、游标推进 |
| run 联动 | `attach(run_id)` + 现有 run SSE | pytest + Vitest：`run.linked` 触发 attach、右栏数据更新 |
| 前端聊天 | `useAgentChat` + 聊天组件 | Vitest：会话切换、流式消息合并、工具行折叠、Enter/Shift+Enter、滚动跟随、断线恢复、右栏联动 |
| 构建/质量 | 全栈 | `pytest`、`ruff check .`、`npm run typecheck`、`npm run lint`、`npm run build`、`npm test` 全绿 |

## 6. 范围外

- 真实 DeepSeek Harness 在线集成（构建运行时 + `pip install -e` SDK + 密钥接线）——延后为独立切片。
- 移动端聊天布局。
- 修改 `deepseek-harness/` 上游源码。
- 顶部全局导航与右侧研究面板的功能改动。
- 并入 arq 任务体系（本轮隔离的进程内 FIFO）。

## 7. 风险与开放问题

- **R1 真实在线聊天待供给**：本轮仅以 fake seam 验证全栈；真实在线聊天需用户后续构建运行时、`pip install -e` SDK 并供给 `DEEPSEEK_API_KEY`/`QUANT_API_KEY`。
- **R2 fake/真实行为差异**：真实 `DeepSeekHarness` 的事件 schema、单会话 cancel 语义可能与 fake 不同；D1 接口设计须前瞻兼容，真实适配器切片可能需调整事件归一化。
- **R3 单会话 cancel 不可用**：SDK 暂无单会话 cancel，D7 停止语义为"终止并重建本项目持有的 runtime 等价物"；真实接线时需复核其安全性与资源回收。
- **R4 SQLite 写并发**：单 worker FIFO 保障串行写入；多实例部署需前置评估（本轮默认单实例）。
- **Q1 `quant_run_analysis` 工具签名**：plan 引用该工具但当前后端未见其实现（`grep` 无命中）；fake seam 须先定义其调用契约（入参/出参/证据 envelope），真实接线时对齐 dsh-quant-plugin gateway 消费者。
