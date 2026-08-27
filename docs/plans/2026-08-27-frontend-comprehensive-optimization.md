# 全前端研究终端优化计划

## 总结

在 `codex/frontend-research-terminal` 分支完成一次性全面改造：修复数据与安全缺陷，统一 API、类型、Query、股票身份、任务轮询和视觉组件，重构所有旧式页面，并补齐桌面端测试、可访问性和性能门禁。保留现有 URL、Ant Design、暖色研究终端风格及当前未提交修改；不考虑移动端和完整深色模式。

## 核心实施

### 1. P0 缺陷与工程底座

- 新增共享股票 identity 模块，统一规范化、别名匹配和行情 Map，供仪表盘、自选股、列表、筛选和个股页复用。
- 修复股票管理搜索分页总数；过滤、分页、市场和排序写入 URL 查询参数，返回列表时恢复滚动位置。
- 将股票搜索改为 250ms 防抖的服务端查询；保留最近选择，补齐失败、重试、空结果和缓存恢复。
- 修复 AI 报告 HTML 注入：转义动态内容、限制新闻 URL 协议，抽离安全打印视图，禁止未经处理的模型文本进入 `document.write`。
- 按领域拆分 API 与类型，保留 `services/api.ts` 作为兼容 re-export；建立 Query Key factory、查询 hooks、mutation hooks、统一错误转换和失效策略。
- Strategies、Screener、History、Agent 报告和 DL 迁入 TanStack Query；所有后台任务复用 `useJobPolling`。

### 2. 设计系统与共享组件

- 扩充语义 token，严格分离 A 股红涨绿跌、买卖动作、成功失败、风险等级和图表颜色；提高三级文字对比度，移除 Google Font 网络依赖。
- 新增统一的 `PageHeader`、`ResearchPanel`、`AsyncBoundary`、`MetricCard`、`InstrumentTable`、`PriceChange`、`DataFreshness`、`JobProgressPanel`、`ResearchResultCard`、`EmptyState` 和 `RowActionMenu`。
- 清理 `any`、大面积行内样式、硬编码颜色和非必要 `!important`；替换 Ant Design 过时 API。
- 为可点击表格行增加链接语义和键盘操作；加载区域增加 `aria-busy`/`aria-live`，图表提供文本摘要，路由动态更新页面标题。
- 保持仪表盘、个股页和 Agent 工作台为视觉基准，仅做桌面端 1280px 和 1440px 适配。

### 3. 页面重构

- 仪表盘改为紧凑无空位的指数布局，压缩纵向空间，保留模块级降级和刷新。
- 股票管理与自选股统一使用研究型标的表格，提供市场筛选、数据时间、自选状态、个股研究、Agent 研究、策略验证和动作菜单。
- 股票筛选移除手写轮询，结果改为摘要、关键因子、风险和动作分层的研究结果组件。
- 策略研究拆为策略目录、实验配置、运行状态和结果工作区，保留信号、回测、优化、比较和历史能力。
- DL 预测重构为全宽模型实验台，分离预测和回测任务，展示模型说明、数据准备、最近运行、结果和风险提示。
- 回测历史增加过滤、排序、摘要统计及个股/策略跳转；列表使用 Query，详情使用独立抽屉并延迟加载图表。
- `/workspace` 作为唯一的新分析入口；`/agent` 改为历史报告中心，保留旧 URL、详情和安全导出。“新建研究”跳转工作台并预填股票与提示词，不自动发送。
- 应用壳增加路由元数据、路由级错误边界和 React Router future flags；保留 9 个一级 URL，导航中的“AI 分析”调整为“分析报告”。

## 接口与兼容性

- 不新增后端 HTTP 接口、数据库迁移或环境变量；复用现有股票搜索、行情、自选、策略、回测、筛选、Agent 和 DL 接口。
- 新增内部严格类型：`StockIdentity`、`StockAliasSet`、`InstrumentRow`、`AsyncState`、领域 Query Key 和安全报告视图模型。
- `StockSearch` 保持现有 value/onChange 使用方式；内部改为服务端搜索。
- `/agent`、`/workspace` 及其他现有路由保持兼容；工作台读取可选 `stock` 和 `prompt` 查询参数，仅用于预填。
- `services/api.ts` 暂时保留公共 re-export；不提交 `dist`、缓存、日志、数据库、本地配置或密钥。

## 测试与验收

- 增加 Vitest：股票代码别名与行情合并、搜索失败重试、搜索分页、Query 缓存失效、统一异步状态、任务取消与卸载、筛选结果动作、报告转义、工作台预填参数。
- 为 StockList、Watchlist、StockChart、Strategies、BacktestHistory、DLPrediction、Agent 报告和 Login 增加页面级测试；现有 Dashboard、Screener、Workspace 测试保持通过。
- 引入 Playwright，覆盖登录、仪表盘进入个股、自选行情、筛选结果、策略验证、DL 预测、报告中心跳转工作台和连续对话。
- 在 1440×900 与 1280×800 完成真实数据、空数据、部分失败、未认证、任务失败和断线恢复的视觉检查。
- ECharts 按需注册并二级懒加载；调整 Vite 分包，首屏 gzip JS 不超过约 350 KB，任一业务 chunk 不超过 500 KB。
- 最终执行 `npm run typecheck`、`npm run lint`、`npm run format:check`、`npm run build`、全部 Vitest 和 Playwright；要求零 lint warning、零弃用警告、零格式错误。
- 统一验收后创建前端聚焦提交 `feat(frontend): complete research terminal optimization`，仅暂存 `frontend/` 和本计划文档，不包含当前后端未提交修改，也不自动推送。

## 假设

- 用户选择一次性完成全部改造并统一交付，不拆成多轮功能交付。
- `/workspace` 是未来唯一的新 AI 研究主入口，`/agent` 转为报告中心。
- 桌面端优先；移动端不主动破坏，但不纳入本轮视觉和 E2E 验收。
- 浅色主题先行，深色 token 仅保持可扩展性，不提供主题切换入口。
- 后端现有接口足以完成本轮改造；真实契约缺陷使用兼容适配解决，不扩大为后端重构。

## 实施记录与验收结果（2026-08-27）

- 已在 `codex/frontend-research-terminal` 完成桌面端首期全面改造：股票 identity、服务端搜索、Query 缓存与失效、任务轮询、按需图表、报告安全导出、研究型共享组件、应用壳、九个一级入口和 Agent 工作台均已接入。
- API 与响应适配统一规范化 `sh.600000` 等股票代码；保留 `services/api.ts` 兼容导出，未增加后端接口、迁移或环境变量。
- 已加入 Playwright 桌面主流程（登录 → 仪表盘 → 个股 → 周 K；报告中心 → 工作台预填）以及报告 HTML 注入回归测试。
- 已完成 1440×900、1280×800 的页面视觉检查，覆盖仪表盘、股票管理、自选股、筛选、策略、DL 预测、回测历史、分析报告、Agent 工作台和个股 K 线；移动端不纳入本轮验收。
- 验收命令全部通过：`npm run typecheck`、`npm run lint`、`npm run format:check`、`npm test -- --run`（25 个文件、98 个测试）、`npm run build`（bundle budget 通过，最大 gzip 约 173.5 KB，最大业务 chunk 约 71.7 KB）和 `npm run test:e2e`（2 个桌面用例通过）。
- 构建产物、Playwright 测试结果、缓存、日志和本地配置未纳入提交；现有后端未提交修改保持原样。
