# Agent Harness 统一运行时规格

> 日期：2026-08-15
> 上游依据：`AGENT_QUANT_UPGRADE_PLAN.md`（2026-08-14）
> 状态：待用户批准
> 决策记录：见「实施决策与约束」；grilling 结论已由用户确认。

## 1. 问题陈述

项目现有两套重复的 Agent 实现：`backend/app/agent/` 是手写线性编排（quick/standard/full/strategy 四种模式），状态停留在单次进程与自由文本中，无 checkpoint、无恢复、无预算控制、结论无证据溯源；`TradingAgents-astock/`（v0.2.4）已基于 LangGraph，含 7 类分析师、质量门控、多空/风险辩论与 A 股规则，但未成为主系统的统一运行时。前端 Agent 能力是"提交后轮询"，无事件流、无结构化证据/回测/风险视图、无审批卡。DeepSeek Harness（DSH）未接入，缺少对话外壳与工具审批能力。

目标：把 Agent 能力收敛为**一个可审计的投研与策略实验平台**——LangGraph 是唯一量化流程编排器，DSH 是对话外壳，所有工具经类型化网关访问，LLM 只提假设与解释，行情计算/回测/风控由确定性代码执行。

## 2. 用户可见的解决方案

1. **统一 run 模型**：一切 Agent 活动（分析、研究、策略实验）都是持久化 `run`，有 `run_id`、计划、预算、checkpoint、事件流；页面刷新、断线、进程重启后按 `run_id` 恢复，不丢进度。
2. **事件流工作台**：新增三栏桌面工作台（左侧导航 / 中间对话与运行计划 / 右侧研究区），右侧以「行情与结论、证据、回测、风险」四页签展示结构化结果；每个工具调用是可折叠 timeline 事件；高风险操作（模拟盘下单）出现审批卡。
3. **类型化工具**：Agent 只能通过 Tool Gateway 调用 `market.*`、`fundamental.*`、`event.*`、`factor.*`、`strategy.*`、`backtest.*`、`portfolio.*`、`execution.paper.*` 八域工具，权限分级（只读默认开放 / 写策略与高成本回测需策略权限 / 模拟下单需人工审批 / 实盘禁用），返回统一 JSON Schema。
4. **证据可追溯**：每条结论附 `source_id`、`as_of`、vendor、数据版本与 tool call 引用；无证据只能标为假设。
5. **DSH 对话入口（独立 POC）**：固定 commit 的 DSH bundled runtime 通过官方 Python SDK 启动，提供独立 Web UI 与工具审批；`session_id` 与 `run_id` 由后端映射，可分别恢复。
6. **兼容过渡**：现有 `/api/v1/agent/*` 端点与 AI 分析页面在过渡期继续可用，由 adapter 桥接到新运行时，能力对齐后退役。

## 3. 用户故事 / 行为

### Phase 0：可信基础
- **US-0.1** 作为研究者，我希望系统有六大核心结构化契约（`RunPlan`、`ResearchClaim`、`StrategySpec`、`BacktestVerdict`、`PortfolioProposal`、`DataQualityReport`），Agent 输出必须通过 Pydantic 校验，禁止从自由文本正则猜测信号。
- **US-0.2** 作为审计者，我希望每条结论/证据强制携带 `source_id`、`as_of`（数据当时可获得时间）、vendor 与 schema version，缺证据的表述必须标记为假设。
- **US-0.3** 作为维护者，我希望有固定评测集（10 个 golden cases 覆盖牛/熊/震荡/停牌/涨跌停/财报/解禁/数据缺失）与确定性评分器；LLM 响应走缓存，评测不依赖外网，可一键回归。
- **US-0.4** 作为维护者，我希望后端 166 个既有测试与前端 build 保持全绿（基线已确认通过，作为回归底线）。

### Phase 1：统一 Runtime
- **US-1.1** 作为用户，我提交目标后获得 `run_id`，通过 SSE 收到计划、节点进度、工具调用、产物与完成/失败事件；刷新或断线后可按事件序号从 checkpoint 重放。
- **US-1.2** 作为用户，我可以取消运行中的 run；取消在最近的安全边界（节点间）生效并记录取消原因。
- **US-1.3** 作为运维者，我可以配置 run 预算（最大轮次、工具调用数、token、耗时、并发）；超预算自动终止并给出明确失败原因。
- **US-1.4** 作为审计者，每个 run 的 step、tool call、artifact 落库（`agent_runs`/`agent_steps`/`tool_calls`/`artifacts`），可查到"这条结论来自哪次工具调用、什么参数、什么时间"。
- **US-1.5** 作为用户，进程重启后正在执行的 run 能从最近成功 checkpoint 恢复，外部调用使用幂等键。
- **US-1.6** 作为用户，旧的 AI 分析入口在过渡期行为不变（adapter 桥接），直到工作台能力对齐后退役。

### Phase 2：Quant Harness
- **US-2.1** 作为用户，我可以自然语言描述目标（股票池 + 研究目标），Supervisor 生成 `RunPlan` 并动态路由到 Research/Data QA/Strategy Engineer/Backtest Critic/Portfolio Risk 专家，而不是固定跑一条流水线。
- **US-2.2** 作为用户，我可以在工作台看到策略与基准净值、年化、最大回撤、样本外 Sharpe、交易成本与审计结论，参数修改产生新的 `run_id`，旧回测永不覆盖。
- **US-2.3** 作为用户，我可以在 DSH 对话中调用量化工具（如查询 K 线、发起回测），工具审批卡展示参数与风险，Chat Node 渲染结构化结果。
- **US-2.4** 作为审计者，所有结论可通过 `run_id → step → tool_call → artifact → source_id` 全链路追溯。
- **US-2.5** 作为开发者，TradingAgents-astock 作为 workspace package 接入统一运行时（复用其 A 股图与辩论能力），不新增第二套状态机。

### Phase 3（仅规划，不实现）
- **US-3.x** 模拟盘闭环：paper broker、人工审批卡、盘前计划/盘后归因、告警。本规格只产出规划切片与验收标准。

### Phase 4（仅设计附录，不实现）
- **US-4.x** 受控实盘：券商接口、报备、限频、熔断、审计与应急预案评审清单。

## 4. 实施决策与约束

### 架构
1. **单一 LangGraph 运行时**：新增 `backend/app/agent_runtime/`（graph 定义、checkpoint、预算、审批、事件），是唯一的量化流程编排器。
2. **DSH 只做外壳**：新增 `dsh-quant-plugin/`，固定 commit `47f9438`（仓库内已有克隆），用官方 Python SDK 启动 bundled runtime 作为独立 POC；插件只调 FastAPI Tool Gateway，不直连数据库；默认移除 Bash/编辑器/宿主文件工具。session↔run 映射存于后端 `agent_runs.session_id`。
3. **类型化 Tool Gateway**：新增 `backend/app/tools/`，包装既有确定性服务（`baostock_service`、`indicator_service`、`backtest_executor`、`strategy/registry` 等），八个域按权限分级，输出统一 JSON Schema。
4. **旧编排过渡退役**：`backend/app/api/agent.py` 的端点改经 adapter 调新运行时（adapter 复用 `AgentOrchestrator` 直至工作台对齐）；禁止在新运行时中新增状态机。
5. **新模块边界**：`backend/app/domain/`（纯 Pydantic schema，无数据库依赖）、`backend/app/agent_runtime/`（LangGraph 层）、`backend/app/agent_api/`（FastAPI 路由：run/stream/resume/cancel/artifact/evaluation）、`backend/app/tools/`（网关与权限）、`evals/`（数据集与评分器）。`TradingAgents-astock/` 保持独立包，被 backend 以 workspace/editable 方式导入。

### 持久化
6. **SQLite-first**：LangGraph 用 `langgraph-checkpoint-sqlite`（单库 `agent_checkpoints.db`）；业务表 `agent_runs`、`agent_steps`、`tool_calls`、`artifacts`、`approvals` 加入现有 SQLAlchemy 库（`stock_backtest.db`）并出 Alembic 迁移。
7. **repository 接口**：所有 run/step/tool/artifact/approval 读写走 repository 协议（`app/agent_runtime/stores/`），后续 PostgreSQL 仅新增实现类 + 配置切换，不触碰调用方。
8. **事件序号**：每个 run 的事件单调递增 `seq`，SSE 支持 `Last-Event-ID` 断线重放；事件同时落库（可重放）。

### 依赖与版本
9. **主后端补齐 LangGraph 栈**：在 `backend/requirements.txt`（及 lock）中加入与 `langchain-core==1.5.4` 兼容的 `langgraph`、`langgraph-checkpoint-sqlite`、`langchain-openai` 固定版本；DeepSeek 通过 `langchain-openai` 的 base_url 接入，继续用现有 `DEEPSEEK_API_KEY`。
10. **TradingAgents 兼容性**：其声明 `langchain-core>=0.3.81`、`langgraph>=0.4.8`，代码针对 0.3.x API 编写。首个实现切片先做兼容性 smoke（导入 + 构建其 graph + checkpoint resume 测试通过）；若与 1.5.4 存在不可调和 API 冲突，则隔离为独立进程/环境、经 HTTP 适配调用，并把该结论带回评审。

### 前端
11. **传输**：新增 SSE 流端点 `GET /api/v1/agent-runs/{run_id}/events`；现有 WebSocket 继续服务实时行情，不与 Agent 事件流混用。
12. **工作台**：新增路由 `/workspace` 与组件（`pages/AgentWorkspace.tsx`、`components/agent/AgentConversation.tsx`、`RunTimeline.tsx`、`EvidencePanel.tsx`、`BacktestPanel.tsx`、`RiskPanel.tsx`、`ApprovalCard.tsx`、`ArtifactViewer.tsx`），复用 antd/ECharts；三栏布局，研究区四页签；对话中点击"查看证据/回测/风险"只切页签不跳页；加载/部分失败/数据为空/等待审批/已取消/恢复中均有独立状态。

### 安全与权限
13. 工具权限三级：只读（market/fundamental/event/factor）默认开放；策略写与高成本回测（strategy/backtest）需策略权限；模拟下单（execution.paper）需人工审批；实盘工具不存在于本规格。
14. Agent 不得获得数据库写权限、生产 Shell 或任意代码执行；`strategy.*` 仅接受声明式 `StrategySpec`，禁止执行宿主代码。
15. 新增端点沿用既有认证（session cookie/API key）、速率限制与 CSRF 约定；敏感 trace 内容默认脱敏。

### 评测
16. `evals/datasets/` 版本化 10 个 golden cases；LLM 响应缓存（record/replay），CI 不依赖外网与 API key；确定性评分器覆盖 schema 校验、引用覆盖率、无前视、A 股成交规则；live 跑批单独开关。

## 5. 测试接缝与成功标准

| 层 | 接缝 | 验证方式 |
|---|---|---|
| 契约 | `app/domain/` 六大 schema + `as_of/source_id` | pytest：schema 正反例、缺证据标记为假设 |
| Runtime | graph 节点、checkpoint、预算、取消 | pytest + langgraph 内存/临时 SQLite saver：中断恢复、超预算终止、取消在节点边界生效 |
| 事件流 | `agent_runs` seq + SSE 端点 | httpx 异步测试：断线重放、`Last-Event-ID` 语义 |
| 工具网关 | `app/tools/` 注册表 + 权限策略 | pytest：allowlist、参数校验、权限拒绝、mock 化的 provider |
| 前端 | `AgentWorkspace` 与子组件 | Vitest：SSE 消费、四页签切换、审批卡、状态机渲染；`npm run build` 全绿 |
| 评测 | `evals/` 数据集 + 评分器 | pytest：缓存回放确定性打分；live 开关跑批为可选标记 |
| 兼容 | `/api/v1/agent/*` 旧端点 | 既有 test_api_contracts / test_pipeline 保持通过 |
| 集成 | TradingAgents 图适配 | smoke：构建图 + checkpoint resume 通过 |

**阶段完成标准（验收门槛）**
- **P0**：schema/契约/评测骨架可一键回归；既有 166 测试与前端 build 保持全绿；golden cases 缓存回放全通过。
- **P1**：任意节点中断后可恢复（测试证明）；刷新/断线不丢进度；每条结论可追到工具调用；超预算与取消行为有测试；旧端点兼容。
- **P2**：自然语言目标 → `RunPlan` → 专家执行 → 确定性回测 → 审计结论（通过/拒绝及原因）全链路可演示；DSH POC 可启动并与网关对话、审批工具调用；工作台四视图可用；不自动进入任何交易。

## 6. 范围外

- 实盘连接、自动下单、券商接口（Phase 4 仅附录）。
- 模拟盘 broker 实现（Phase 3 仅规划，其验收需 4–8 周连续运行，不在本轮完成）。
- PostgreSQL/Redis 基础设施切换（接口预留，不做迁移）。
- fork DSH Web UI 或把 Chat Node 协议接入现有 React（POC 验证后再评估）。
- 向量数据库、把 LLM 自由文本当事实记忆。
- TradingAgents v0.3.1 的深度回迁（决策日志、前视过滤等列为后续独立切片，且需先写差异测试）。
- 让 Agent 写任意生产代码或获得生产 Shell/数据库写权限。

## 7. 风险与开放问题

1. **DSH Developer Preview 破坏性变更**：固定 commit `47f9438` + 独立 POC 隔离；升级须走差异验证。
2. **langchain 版本对齐**：主后端 1.5.4 vs TradingAgents 0.3.x 系代码。缓解：兼容性 smoke 为第一切片；失败则隔离进程/环境，方案需带回评审（见决策 10）。
3. **真实 LLM 评测稳定性与成本**：golden cases 缓存响应；live 跑批单独开关；成本与 P95 延迟记录为评测指标。
4. **行情 provider 网络脆弱性**（akshare/mootdx）：全部测试走 mock/stub；运行时失败计入 run 错误事件与 DataQualityReport。
5. **前端体积**：当前 bundle 2.4MB，新增工作台需按路由懒加载与 manualChunks 拆分，避免恶化。
6. **开放问题**：DSH 与 LangGraph 的预算控制分界（DSH 管对话轮次、LangGraph 管量化预算）需在 POC 中验证；`execution.paper.*` 的审批有效期与重试语义留待 P3 规划时定稿。
