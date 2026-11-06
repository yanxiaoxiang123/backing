# 无效代码与废弃接口清理

日期：2026-11-05。

## 判定依据

- 前端使用 TypeScript 编译器分析静态导入、动态导入、类型引用、重导出以及测试引用。重导出本身不能证明存在业务调用。
- 后端核对路由注册、Python 引用、测试、CLI、任务 runner、工具网关和部署文档。没有前端调用的接口不自动视为废弃。
- 清理发生在已有未提交改动的工作区；欢迎页、公开行情和工作台的原有改动保留。

## 已移除的接口

| 接口 | 清理原因 | 当前入口 |
| --- | --- | --- |
| `GET /api/v1/dashboard` | 当前仪表盘已分别查询实时行情、自选股、分析历史、任务指标与告警；旧 hook 与聚合服务没有页面调用 | `/watchlist`、`/realtime/*`、`/agent/history`、`/jobs/metrics`、`/paper/alerts` |
| `POST /api/v1/screener` | 已标记 deprecated，前端使用异步 AI 选股；旧同步条件筛选模块没有其他业务引用 | `POST /api/v1/screener/submit`，然后查询任务或历史 |
| `GET /api/v1/agent/indices` | 没有页面调用，且原路由排列在 `/agent/{record_id}` 后面，字符串路径会被整数参数校验截获 | 指数清单使用 `/api/v1/indices`，实时指数使用 `/api/v1/realtime/indices` |
| `POST /api/v1/agent/market/analyze` | 大盘分析页面调用已退出当前应用，封装仅剩重导出，配套模型与提示词没有其他引用 | 当前 AI 研究入口为分析报告与 Agent 工作台；未保留旧接口的同形返回值 |

异步 AI 选股使用已有综合评分流程，不接收旧同步接口的自定义条件请求。移除同步接口后，不再提供该旧请求契约。

## 代码清理

- 前端移除 15 个没有实际调用的 API 函数，以及 DL 同步接口请求/响应类型和无用重导出。
- 移除 `useDashboardBriefing`、`useRefreshDashboard`、对应 query key、`ChartRegion`、`DataFreshness` 和孤立类型。保留仍被个股概览引用的 `ResearchActivity`。
- 删除旧浮动导航与旧布局的 CSS；保留当前侧栏、页面标题、加载状态和副驾驶样式。
- 后端删除同步选股模块、旧仪表盘服务、大盘分析提示词，以及孤立的 schema、异常别名和枚举。
- 策略优化保留当前网格搜索及统一回测实现；移除没有调用者的随机搜索和旧指标计算函数。
- 删除未被评测入口引用的 `evals/pipeline_llm.py`；评测仍支持通过 `run_evaluation(..., llm_fn=...)` 注入调用方。
- TradingAgents 删除 4 个无引用的通用 helper，保留图执行器与 checkpoint 使用的 `safe_ticker_component`。
- 删除根目录孤立的 mootdx 调试脚本 `test.py`。
- 更新接口文档、版本前缀与浏览器测试 fixture；新增路由清单与异步选股提交回归测试。

## 有明确用途的保留项

- DL 同步预测、同步回测与股票同步分析接口具有兼容说明或既有合约测试，后端继续提供；前端闲置封装已移除。
- 策略注册模块、兼容导出、Arq worker、持久化任务 runner、Agent native runtime 和测试 fake 保留。
- `dsh-quant-plugin/` 等历史参考、数据库、迁移和 vendor 代码保留。
- 未新增依赖或环境变量，不需要数据库迁移。

## 验证

| 检查 | 结果 |
| --- | --- |
| 后端 Ruff，含 `evals/` | 通过 |
| 后端全量 pytest | 794 passed，1 skipped |
| TradingAgents 全量 pytest | 107 passed，1 skipped，44 subtests passed |
| 前端 typecheck / lint / format:check | 通过 |
| 前端单元及组件测试 | 36 个文件，176 项通过 |
| 前端生产构建及 chunk budget | 通过 |
| Playwright 研究终端与 DL 主流程 | 3 项通过 |
| 旧导航 CSS 恢复前后计算样式比较 | 1440 / 768 / 390px：受检节点的 12 项样式属性均无变化 |
| 生产构建截图及移动导航 | 已检查三种宽度，菜单可打开 |

浏览器检查使用 API fixture，不发起真实行情、模型推理或付费调用。截图保存在未纳入 Git 的 `.taste-skill/cleanup/`。

TradingAgents 的跳过项为缺少可选 `langchain_google_genai` 的测试文件。构建保留现有 Vite 大 chunk 提示，项目独立包预算全部通过。
