# Agent 工作台 Harness 聊天化改造

## 总体方案

在现有 React 工作台中原生实现 DeepSeek Harness 风格界面，不直接嵌入其 Web 页面：

- 左栏改为会话列表，支持新建、切换和归档对话。
- 中栏改为真正的多轮聊天，DeepSeek Harness 负责上下文、推理和量化工具调用。
- 右栏保留行情、证据、回测、风险和产物面板，并自动跟随当前会话最近一次量化 run。
- 不修改被忽略的 `deepseek-harness/` 上游源码；复用现有 Python SDK、量化 Cordis 配置和 `dsh-quant-plugin`。

## 后端与数据流

- 新增 `agent_chat_threads`、`agent_chat_turns`、`agent_chat_events` 表及 Alembic 迁移：
  - thread 保存 Harness `session_id`、标题、状态和最近 `run_id`。
  - turn 保存用户输入、执行状态、最终回复、结束原因和错误。
  - event 保存可重放的 reasoning、assistant chunk、tool call/result 等原始事件。
- 新增单例 `HarnessChatService`，在 FastAPI lifespan 中启动/关闭：
  - 使用 `thread_id` 作为 Harness `session_id`，会话写入 `backend/data/dsh_sessions/`。
  - 单 worker 按 FIFO 执行，运行中继续发送的消息进入队列。
  - 服务重启时将未完成 turn 标记为 `interrupted`，不自动重复提交；尚未开始的 queued turn 继续执行。
- 修改 `quant_run_analysis`，从工具执行上下文读取 `exec.agent.session.header.id`，创建 run 时传入 `thread_id`。
- 后台发现当前 thread 新建 run 后发布 `run.linked`，前端立即连接现有 run SSE，驱动右栏更新。
- SDK 暂无单会话 cancel，因此停止操作会终止并重建本项目持有的 Harness runtime；当前 turn 标记 cancelled，队列保留。



## API 与前端改造

新增认证和 CSRF 保护下的接口：

- `POST /api/v1/agent-chats`：创建会话。
- `GET /api/v1/agent-chats`：分页获取未归档会话。
- `GET /api/v1/agent-chats/{thread_id}`：恢复 turn 和事件历史。
- `POST /api/v1/agent-chats/{thread_id}/turns`：提交消息，支持 `Idempotency-Key`。
- `GET /api/v1/agent-chats/{thread_id}/events`：支持 `Last-Event-ID` 的 SSE。
- `POST /api/v1/agent-chats/{thread_id}/cancel`：停止当前 turn。
- `POST /api/v1/agent-chats/{thread_id}/archive`：软归档会话。

前端新增 `useAgentChat` 和聊天组件：

- 左栏约 240px：新对话按钮、标题、更新时间、运行状态和会话选择。
- 中栏采用 Harness 交互：用户右侧气泡、助手 Markdown、折叠思考与工具行、“Deep diving…”状态、回到底部按钮。
- 输入框固定底部并自动增高；Enter 发送、Shift+Enter 换行；运行中消息进入队列，按钮切换为停止。
- 使用 `react-markdown + remark-gfm`，不启用原始 HTML。
- URL 保存 `thread_id`；刷新后恢复聊天、SSE 游标和右栏最近 run。
- `useAgentRun` 增加 `attach(run_id)`，用于观察已有 run，不重复创建任务。



## 验证与文档

- 后端使用 fake Harness seam 测试多轮上下文、事件顺序、SSE 重放、幂等提交、队列、取消、重启恢复和 session-to-run 映射。
- 前端测试会话切换、流式消息合并、工具折叠、键盘发送、滚动跟随、断线恢复及右栏 run 联动。
- 运行 `pytest`、`ruff check .`、`npm run typecheck`、`npm run lint`、`npm run build` 和 `npm test`。
- 更新 `.env.example`、AGENTS.md 和 Harness 安装说明，记录 `DSH_SESSION_ROOT`、Cordis 路径及 editable SDK/runtime 安装命令。
- 保留当前工作区已有修改，实施时只在相关文件上增量编辑，不覆盖未提交内容。



## 默认约束

- 仅优化桌面端，不新增移动端聊天布局。
- 顶部全局导航和右侧研究面板保持现有功能。
- 首条消息前 36 个字符作为默认会话标题。
- 同一后端实例同时只执行一个 Harness turn，以保证 SDK 生命周期、取消和 SQLite 写入安全。
