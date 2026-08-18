# Agent 工作台聊天化改造 - 执行计划总览

> 日期：2026-08-18
> 规约：`docs/specs/2026-08-18-agent-workspace-chat.md`（已批准）
> 执行模式：Adaptive；提交策略：按批准切片提交；终点：验证过的本地改动
> 真源：规约 D1–D15；既有代码 `agent_runs.thread_id` 列、`/agent-runs/{run_id}/events` SSE、`useAgentRun`、`App.tsx` 顶导航

## 切片依赖图

```
T1 数据模型/迁移 ──> T2 Seam+Fake(真 run) ──> T3 HarnessChatService 单例/队列/重启恢复 ──> T4 后端 API+SSE+run.linked ──┐
                                                                                                                │
T5 useAgentRun.attach (独立) ───────────────────────────────────────────────┐                                   │
                                                                            │                                   │
T6 useAgentChat+API client (可先用 mock) <── T4 (API 契约) ──────────────────┼───────────────────────────────────┘
                                                                            │
T7 聊天组件 <── T6                                                          │
                                                                            │
T8 AgentWorkspace 集成+URL 路由+右栏联动 <── T7, T5                         │
                                                                            │
T9 端到端验证+文档 <── T8, T4                                              │
```

可并行起点：T1（后端 schema）与 T5（前端 hook）互不阻塞，可同批启动。T6 可先以 mock 契约推进，待 T4 落地再接真实 API。

## 切片清单

### T1 数据模型与 Alembic 迁移
- 用户可见交付：三张新表 `agent_chat_threads/turns/events` 可用；`agent_runs.thread_id` 补索引；迁移可正反向。
- 验收标准：`alembic upgrade head` 建表、`alembic downgrade -1` 干净回退；`agent_runs.thread_id` 带索引；模型可在 `app.config.Base` 注册并被导入；ruff 通过。
- 阻塞任务：None（前置因子）
- Delegation：eligible — 隔离的后端 schema 工作，契约清晰。

### T2 HarnessChatSeam 抽象接口 + FakeHarnessChatSeam（逼真 + 真 run）
- 用户可见交付：抽象 `HarnessChatSeam` 接口与确定性 `FakeHarnessChatSeam`；fake 产出 reasoning/assistant/tool 事件，并在 `quant_run_analysis` 工具调用时经 `agent_runtime` stores 真实创建 `agent_runs`（写 `thread_id`）与 run 事件、发布 `run.linked`。
- 验收标准：pytest 覆盖多轮上下文累积、事件类型与顺序可重放、`quant_run_analysis` 真实落 `agent_runs` 行 + 事件、`run.linked` 含正确 `run_id`/`thread_id`；fake 行为确定性（同输入同输出）。
- 阻塞任务：T1
- Delegation：eligible — 后端独立模块；但为核心契约，主代理须复核事件 schema 前瞻兼容真实 SDK。

### T3 HarnessChatService 单例 + FIFO 队列 + 重启恢复
- 用户可见交付：FastAPI lifespan 启停的单例服务；单 worker 按 FIFO 执行 turn；运行中消息入队；取消=终止并重建 runtime 等价物、当前 turn 标 cancelled、队列保留；重启将未完成 turn 标 interrupted、queued 继续。
- 验收标准：pytest 覆盖 FIFO 顺序、运行中入队、取消标 cancelled 且队列保留、重启 interrupted 恢复与 queued 继续、同实例单 turn 串行。
- 阻塞任务：T2
- Delegation：eligible — 后端独立服务，依赖 T2 接口。

### T4 后端 API 端点 + SSE + run.linked
- 用户可见交付：`/api/v1/agent-chats` 全套端点（创建/列表/恢复/turns/events SSE/cancel/archive）；`Idempotency-Key` 去重；复用现有 session cookie + 双提交 CSRF；`Last-Event-ID` 重放；turn 执行时由服务发布 `run.linked`。
- 验收标准：pytest 覆盖创建/列表/恢复/turn 提交幂等/SSE 断线重放不丢不重/cancel/archive；CSRF 与认证拒绝未授权；端点可被 curl 验证。
- 阻塞任务：T3
- Delegation：eligible — 后端路由层，依赖 T3 服务与 T1 表。

### T5 前端 useAgentRun.attach(run_id)
- 用户可见交付：`useAgentRun` 新增 `attach(run_id)`，连接现有 `GET /agent-runs/{run_id}/events` SSE 观察已有 run，不创建任务；右栏可由 `attach` 驱动。
- 验收标准：Vitest 覆盖 attach 后接收 run 事件、不触发 createRun；`npm run build` 绿。
- 阻塞任务：None（复用现有 run SSE）
- Delegation：eligible — 小而隔离的前端 hook 改动；与后端切片可并行。

### T6 前端 useAgentChat hook + API client
- 用户可见交付：`useAgentChat` 管理会话列表/切换/恢复、提交 turn、SSE 事件合并为消息、队列与停止；API client 封装 `/api/v1/agent-chats` 端点与 `Last-Event-ID` 游标。
- 验收标准：Vitest 覆盖会话切换恢复、流式 chunk 合并、停止切停止态、断线 Last-Event-ID 续传；可先用 mock 契约开发，T4 落地后接真实。
- 阻塞任务：T4（API 契约；可先 mock 并行）
- Delegation：eligible — 前端独立 hook。

### T7 前端聊天组件
- 用户可见交付：左会话列表（~240px，新建/标题/更新时间/状态/切换/归档）；中聊天（用户右气泡、助手 Markdown via `react-markdown+remark-gfm` 无 raw HTML、折叠思考与工具行、"Deep diving…"态、回到底部）；底部输入（固定、自动增高、Enter 发送/Shift+Enter 换行、运行中按钮切停止）。
- 验收标准：Vitest 覆盖流式合并、工具行折叠、Enter/Shift+Enter、滚动跟随、停止态切换；`npm run build` 绿；新增依赖锁定。
- 阻塞任务：T6
- Delegation：eligible — 前端组件独立。

### T8 AgentWorkspace 页面集成 + URL 路由 + 右栏联动
- 用户可见交付：`AgentWorkspace` 中栏由 `AgentConversation` 替换为聊天组件；左栏换为会话列表；URL 存 `thread_id` 并刷新恢复；右栏经 `run.linked` 触发 `useAgentRun.attach(run_id)` 跟随最近 run；移除旧 `start(objective)` 入口。
- 验收标准：dev 内（fake seam）可端到端演示：新建会话->发消息->流式回复->工具行折叠->右栏 attach 最近 run 更新；刷新恢复；`npm run build` 绿。
- 阻塞任务：T7, T5
- Delegation：eligible — 但耦合左/中/右+路由，主代理复核集成。

### T9 端到端验证 + 文档
- 用户可见交付：全栈质量门全绿；`.env.example` 记 `DSH_SESSION_ROOT`；AGENTS.md 与 Harness 安装说明记录 Cordis 路径与 editable SDK/runtime 安装命令。
- 验收标准：`pytest`、`ruff check .`、`npm run typecheck`、`npm run lint`、`npm run build`、`npm test` 全绿；文档增量更新且不含密钥。
- 阻塞任务：T8, T4
- Delegation：ineligible — 最终集成与验证门，主代理拥有。

## Delegation 策略（adaptive）
- 起点可同批委派：T1（后端 schema）与 T5（前端 hook）互不阻塞。
- 核心 contract 切片 T2/T3/T4 虽 eligible，但事件 schema 与 cancel 语义前瞻兼容要求高，委派后主代理须复核。
- 前端 T6/T7/T8 串行阻塞链，建议按序在主代理或单委派链推进。
- T9 由主代理统一收口验证。

## 验证门（每切片）
- 后端切片：`cd backend && ruff check . && pytest <相关>`
- 前端切片：`cd frontend && npm run typecheck && npm run lint && npm run build && npm test <相关>`
- 收口（T9）：全栈全绿。
