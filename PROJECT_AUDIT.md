# Backing 项目全量审核报告

> 审核日期：2026-08-14  
> 范围：`frontend/`、`backend/`、SQLite/Alembic、部署配置、`TradingAgents-astock/`  
> 方法：源码审阅、依赖解析、构建/测试、迁移实测、API 健康检查、桌面与移动端浏览器巡检。未执行真实交易、全市场同步、模型推理或付费 LLM 调用。

## 结论摘要

项目业务边界清晰，策略注册、统一回测、任务持久化、统一错误体和前端设计变量都是良好基础。后端已在 Python 3.12 的 `backing` Conda 环境中启动，当前测试 **162/162 通过**（前端 26/26）；mootdx 日 K 数据与前端图表已恢复。但当前仍不适合直接生产部署：仍存在已跟踪的环境文件、不可解的正式依赖、客户端内嵌 API Key、过期依赖、明显的移动端布局问题（SQLite 迁移与前端构建已修复）。

建议先完成 P0/P1，再继续扩展策略和 AI 功能。

## 验证结果

| 检查 | 结果 |
|---|---|
| 后端启动与 `/api/v1/health` | 通过，HTTP 200 |
| 后端 `python -m pytest -q` | 通过，19 tests、1 个 Starlette/httpx 弃用警告 |
| mootdx 日 K API | 通过；`600036` 返回 750 根，最新日期 2026-08-14 |
| 前端 K 线浏览器验证 | 通过；日 K 与成交量图已实际绘制，无加载或错误提示 |
| 行情相关 Ruff 检查 | 通过；`realtime_service.py`、`realtime.py` 及专项测试无问题 |
| 后端 `ruff check .` | 失败，690 项；多数来自启用新版规则后的旧式类型注解和导入排序 |
| 前端 `npm run build` | 失败，2 个 TypeScript 错误 |
| 前端 `npm audit` | 12 个漏洞：5 high、6 moderate、1 low |
| Alembic `upgrade head`（SQLite） | 失败于 `20260319_01` |
| `pip check` | `mootdx` 与 `httpx` 版本冲突 |
| 移动端 390×844 | 策略页横向溢出，主内容不可完整访问 |
| `TradingAgents-astock` 编译 | Python 3.12 语法编译通过；完整测试环境未单独安装 |

## P0：上线前必须处理

### 1. 敏感配置和运行产物已被 Git 跟踪

`backend/.env`、`logs/*.out` 和两个 `.DS_Store` 已进入版本历史；`.gitignore` 只能阻止新增，不能取消已有跟踪。即使当前仓库私有，也应视为密钥可能泄露。

**建议：** 立即轮换 `.env` 中全部密钥；执行 `git rm --cached backend/.env logs/*.out .DS_Store deploy/a-stock-screener/.DS_Store`；评估是否使用 `git filter-repo` 清理历史；CI 增加 Gitleaks/TruffleHog。

### 2. 生产服务以 root 运行 Vite 开发服务器

[`deploy/systemd/stockbacking-backend.service`](deploy/systemd/stockbacking-backend.service) 和前端服务均为 `User=root`；前端使用 `npm run dev -- --host 0.0.0.0`，没有静态构建、反向代理、TLS、安全头或最小权限隔离。

**建议：** 创建专用系统用户；CI 生成 `frontend/dist/`；由 Nginx/Caddy 托管并反代 API/WebSocket；增加 `NoNewPrivileges`、只读目录、资源限制、健康检查和日志轮转。

## P1：高优先级修复

### 3. 数据库迁移链不可用，实际结构已漂移 — ✅ 已修复

[`20260319_01_add_user_watchlist.py:33`](backend/migrations/versions/20260319_01_add_user_watchlist.py#L33) 在 SQLite 上直接 `create_foreign_key`，触发“不支持 ALTER constraint”。实测数据库停在 `20260316_02`，但 `user_watchlist` 已部分创建且无外键。`jobs` 表和模型中的 `idx_backtest_stock_created` 也没有迁移；启动时 [`Base.metadata.create_all`](backend/main.py#L60) 又掩盖了缺失迁移。SQLite `PRAGMA foreign_keys` 当前为 `0`。

**建议：** 使用 Alembic batch mode 重写自选股迁移；补 jobs/index 迁移；移除生产启动时的 `create_all`；连接时显式启用 SQLite 外键；增加“空库 upgrade → downgrade → upgrade”和模型差异 CI。

**修复（2026-08）：** `20260319_01` 改为内联 FK + batch mode 漂移修复（表已存在且缺 FK 时 copy-and-move 补上，数据不丢）；新增 `20260320_01`（`jobs` 表、`idx_backtest_stock_created`、`idx_analysis_stock_date`，均带存在性防御）；模型补齐 `idx_backtest_trades_result_stock`；`main.py` 移除启动 `create_all` 并改为迁移缺失即报错；`app/config.py` 连接时 `PRAGMA foreign_keys=ON`；systemd 启动前执行 `alembic upgrade head`；新增 [`tests/test_migrations.py`](backend/tests/test_migrations.py)（空库 upgrade→downgrade→upgrade、漂移库修复、模型差异为空的 CI）。验证：本机真实漂移库 `upgrade head` 成功（数据无损，FK/索引补齐），模型差异为空，应用连接 `PRAGMA foreign_keys=1`，后端 23 个测试全过。

### 4. 后端依赖仍无法按文档一次安装 — ✅ 已修复

[`backend/requirements.txt`](backend/requirements.txt) 要求 `httpx>=0.28`，而 `mootdx==0.11.7` 要求 `httpx>=0.25,<0.26`；标准 pip 解析和 `pip check` 仍会失败。本轮已补充 `SessionMiddleware` 所需的 `itsdangerous>=2.2.0`，但全部依赖仍仅设下限，未来安装会产生不可复现组合。

**建议：** 决定升级/替换 mootdx，或将行情适配器放入独立环境/进程；用 `uv.lock`/`pip-tools` 生成经过验证的锁文件，并明确 Python `>=3.11`（当前代码使用 `tuple[...]`）。

**修复（2026-08）：** 冲突不可调和（`mootdx==0.11.7` 已是 PyPI 最新版，其 `httpx<0.26` 与 starlette 要求的 `httpx>=0.27` 无交集），而运行时已验证 mootdx 在 `httpx 0.28.1` 下正常。因此按当前 conda 环境版本修复：`mootdx` 改为仓库内 vendored 副本（[`backend/vendor/mootdx`](backend/vendor/mootdx)，MIT，纯 Python，仅放宽 `httpx>=0.25,<0.29` 这一处元数据约束，版本 `0.11.7.post1`，`requirements.txt` 以 `./vendor/mootdx` 引用）；`requirements.txt` 全部改为环境验证过的精确 pin；新增 [`requirements.lock`](backend/requirements.lock)（`pip freeze` 全量闭包，`mootdx` 用相对路径保证跨机可移植）；README/AGENTS 明确 Python `>=3.11`（3.12 验证）与锁文件用法。验证：干净 Python 3.12 venv 中 `pip install --dry-run -r requirements.txt` 解析通过（此前 `ResolutionImpossible`）；`pip check` 输出 `No broken requirements found`；`mootdx.quotes.Quotes` 导入正常；后端 23 个测试全过。

### 5. API Key 实际被打包到浏览器 — ✅ 已修复

**修复（2026-08）：** 移除前端构建期密钥注入 — ① [`api.ts`](frontend/src/services/api.ts) 删除 `VITE_API_KEY` 读取（`vite-env.d.ts` 同步清理并加注释禁止再声明密钥变量），新增会话认证状态机：`bootstrapAuth`（`GET /auth/me` 探测）→ 未认证时路由门控跳转登录页；新增 [`Login.tsx`](frontend/src/pages/Login.tsx)（API key 仅本次 POST 提交，不落 localStorage、不进 bundle）；401 响应自动切回未认证。② 后端认证抽为 [`app/api/auth.py`](backend/app/api/auth.py)：`POST /auth/session` 登录（**登录限流 10/min**）签发**短期 HttpOnly session cookie**（`SESSION_MAX_AGE_S` 8h、`SameSite=Lax`、生产 `https_only=True`），同时下发 `csrf_token` cookie（double-submit）；`POST /auth/logout`、`GET /auth/me`。③ 新增 [`CsrfMiddleware`](backend/app/middleware.py)：session cookie 存在时的 POST/PUT/PATCH/DELETE 必须携带匹配的 `X-CSRF-Token`（前端拦截器自动附加），403 `csrf_failed`。④ 生产守卫 [`assert_safe_production_settings`](backend/app/config.py)：`APP_ENV=production` 下使用默认 Session secret 或未开 `SESSION_HTTPS_ONLY` 直接拒绝启动。验证：`test_auth_session.py` 16 用例（登录/限流/me/logout/CSRF 三种路径/生产守卫）；前端 `auth.test.ts` 5 用例；真实应用冒烟：401 → 登录 → me 200 → 无 CSRF 403 → 带 CSRF 200 → 登出后 401。**后续（建议另立任务）**：OIDC/用户名密码登录、`strict` SameSite 评估。

### 6. 前端目前不能生产构建 — ✅ 已修复

**修复（2026-08）：** 构建阻塞上轮已修（`process.env` → `import.meta.env.DEV`、未使用 state 清理），本轮补齐工程化护栏 — ① package.json 新增独立任务：`typecheck`（`tsc --noEmit`）、`lint`（ESLint 9 flat config + typescript-eslint + react-hooks + eslint-config-prettier）、`format`/`format:check`（Prettier 3，仓库风格 semi:false/singleQuote）；存量代码做了一次性 prettier 归一化提交，ESLint 存量 `no-explicit-any` 降为 warn 待逐步收紧，unused-vars/rules-of-hooks 等 error 全清（含本轮引入的 App.tsx 条件 hook 问题）。② 新增 [`ci.yml`](.github/workflows/ci.yml)：PR/push 双触发，backend job（`ruff` + `pytest`，Python 3.12）+ frontend job（`npm ci` → `typecheck` → `lint` → `format:check` → `build` → `test`），即为 PR 必过检查（分支保护在仓库设置里开启 required status check）。验证：`npm run typecheck/lint/build/test` 全部通过（lint 0 error），后端 152 测试全过。

### 7. 实时行情已恢复，但仍缺少可观测性和前端局部降级 — ✅ 已修复

根因是 `Quotes.factory(..., bestip=True)` 会扫描不稳定节点并长时间超时，同时前端 WebSocket 未携带后端要求的查询参数 API Key。上一轮已改为可配置的显式服务器池、3 秒超时、连接探测、60 秒故障节点冷却和请求失败自动切换；WebSocket 现可复用已签名 Session，外部客户端仍可使用 API Key。provider 全部失败时接口安全返回空数组，新增 7 个专项回归测试，真实 API 和浏览器图表均已验证。

剩余问题是降级响应仍未区分“合法空数据”和“provider 故障”，也没有节点健康指标、缓存或告警。首页 [`Dashboard.tsx:48`](frontend/src/pages/Dashboard.tsx#L48) 仍用 `Promise.all` 将自选股和指数绑定，任一真正失败便整页空白；全局与页面错误处理还可能产生重复 toast。

**修复（2026-08-14）：** 三类问题全部落地，分四个交付物完成（每个交付物均带专项测试）：

1. **Provider 信封与缓存（[realtime_service.py](backend/app/services/realtime_service.py)）**——新增 `FetchResult` 数据类，三态 `status: "ok" | "empty" | "unavailable"` 取代了原先的“空 data 既表示休市又表示故障”二义性；`fetch_bars / fetch_quotes / fetch_indices` 是新的有状态入口，旧 `bars / normalise_bars / get_realtime_quotes / get_index_realtime` 保留 `list[dict]` 形态作为兼容层（screener / WS / HTTP 旧路径无需改动）。新增 2 秒短期缓存：(symbol, period) 粒度的 K 线缓存，quotes/indices 各自粒度的快照缓存，避免一个页面多个组件并发拉取造成的 provider 抖动。切换/可用/缓存命中/不可用四类计数接入现有 [`task_metrics`](backend/app/services/tasks/metrics.py)（沿用 `/api/v1/jobs/metrics` 端点，不增加新的指标路径）。`get_provider_health()` 返回 `{provider, selected_server, total_servers, healthy_count, cooldown_count, cooldown_ttl_s, counters, last_failure_reason}`，供前端徽标和运维自检使用。

2. **结构化 503 与健康端点（[api/realtime.py](backend/app/api/realtime.py) + [error_handlers.py](backend/app/error_handlers.py)）**——provider 不可达统一抛 `ProviderUnavailableError`，经 `error_handlers` 渲染为：

   ```json
   {"error": {"code": "provider_unavailable", "message": "Realtime provider unavailable",
              "provider": "mootdx", "retryable": true,
              "reason": "no_healthy_server", "endpoint": "quotes",
              "selected_server": null}}
   ```

   为此 `error_handlers._build_error_body` 支持 `extra` 合并，使 `reason`/`endpoint`/`selected_server` 等域信息直接进入响应体。provider 可达但市场休市 → 200 + `data: []`（保留历史合约）。新增 `GET /api/v1/realtime/health`（与 `/realtime/{code}` 同级注册以避开通配符路由）返回 provider 健康快照。WS 处理改用 `fetch_bars`，`init`/`update` 帧附带 `status` 字段，前端可据此区分全空和故障。

3. **Dashboard 局部降级（[Dashboard.tsx](frontend/src/pages/Dashboard.tsx)）**——弃用单一 `Promise.all`，改用三个独立的 `BlockState<T> = idle | loading | ok | error` slot（indices / quotes / trend）+ watchlist 单独加载。每块自带 `Alert + Retry` 按钮，仅重试失败的那一块；整页空白场景被消除（quotes 503 时指数仍展示；trend 失败时指数和 watchlist 仍可用）。页面顶部新增统一“刷新”按钮可一次性重拉三块（仍独立调用，独立失败），但不再统一触发 toast。`Promise.allSettled` 通过独立 `useCallback` 装载实现：每次调用各自 catch、把后端 `error.userMessage` / `error.retryable` 映射到本块 `state`，重复 toast 路径被消除（页面不再调 `message.error`，全局响应拦截器也不再因业务错误二次提示）。

4. **测试覆盖**——后端 [`test_realtime_service.py`](backend/tests/test_realtime_service.py) 新增 9 个用例（envelope 三态、缓存命中不再调用 provider、计数器递增、健康快照结构、JSON 可序列化）；[`test_api_contracts.py`](backend/tests/test_api_contracts.py) 新增 5 个用例（健康端点 200、bars/quotes/indices 503 契约、empty 状态 200 + 空 data）；[`test_websocket_session.py`](backend/tests/test_websocket_session.py) 适配新的 WS 帧 shape（携带 `status`）。前端新增 [`Dashboard.test.tsx`](frontend/src/pages/__tests__/Dashboard.test.tsx) 3 个组件用例：全成功渲染、quotes 503 时指数仍展示且出现重试入口、trend 失败时点击重试会重新拉取。

**验证：**
- 后端 `pytest` 152 → **162 全过**（含本轮 +10 新测试）；`ruff check` clean。
- 前端 `npm run typecheck / lint / format:check / build` 全通过；`vitest run` 23 → **26 全过**（含本轮 +3）。
- 进程内冒烟：`GET /realtime/health` → 200 + 完整快照；`GET /realtime/quotes`（mock unavailable） → 503 + 结构化 body（含 `provider/retryable/reason/endpoint/selected_server`）。
- `requests=0 / failovers=0 / cache_hits=0 / provider_unavailable=0` 等计数器已纳入 `/api/v1/jobs/metrics`，运维可直接消费。

**显式权衡与后续：** ① 缓存 TTL 选 2 秒（小于 WS 轮询 10 秒，避免 UI 拉新延迟；大于同一渲染内的并发请求，足以去重）。② 503 改动对调用方是一次破坏性变更；唯一调用方（`api.ts` 的 `getRealtimeQuotes`/`getRealtimeIndices`/`getRealtimeBars`）已通过 axios 错误体解析 `error.code/ retryable/reason`，直接渲染到新 UI。③ `task_metrics` 原本只服务任务系统，本轮借用为 provider 计数器以复用单一指标端点；若未来迁移到 Prometheus，可在 `realtime_service` 旁路注入新 exporter，不影响调用方。

### 8. 前端依赖存在已知漏洞

2026-08-14 的官方 npm audit 检出 12 项，包括 Axios、Vite、PostCSS、nanoid 高危项，以及 ECharts XSS 和 React Router 跳转问题。

**建议：** 先升级可兼容的小版本并回归，再计划 Vite/ECharts 主版本迁移；Dependabot/Renovate 每周自动提交，CI 执行生产依赖审计。

## P2：体验、架构与可维护性

### 前端代码与视觉

- [`Strategies.tsx:253`](frontend/src/pages/Strategies.tsx#L253) 内联固定三列 `280px 1fr 1fr`，无断点规则；390 px 下页面宽度远超视口。改为 CSS Grid 类：桌面三列、平板两列、手机单列，并为表格/图表设置局部滚动。
- 全局强制覆盖 Ant Design 样式较多，禁用的黑色主按钮仍配深色文字，视觉上近乎不可读。应补全 disabled、focus-visible、error、loading、dark/高对比状态并做 WCAG 对比度检查。
- 策略名/说明为英文，页面主体为中文；策略列表过长且没有搜索、分类或折叠。统一文案语言，并按趋势/震荡/突破/AI 分类。
- 顶部导航项和 Logo 使用可点击 `div`（[`App.tsx:50`](frontend/src/App.tsx#L50)），键盘不可达；搜索按钮没有行为。改用 `Link/NavLink/button`，补 Escape 关闭菜单、焦点圈定和 `aria-current`。
- `api.ts` 全局 toast 与页面 catch 再次 toast，导致重复错误提示。集中错误归属：全局只处理未知/认证错误，业务错误由页面呈现。
- `Strategies.waitForJob` 无超时、取消或卸载清理；多个页面各自实现轮询。抽取 `useJobPolling`，支持 AbortController、指数退避和状态恢复。
- `index.css` 1089 行且页面大量内联样式；建议拆分 tokens/layout/components/pages，逐步使用 CSS Modules。补 Vitest + Testing Library、Playwright 关键路径及视觉回归。

**修复（2026-08）：** 全部 7 项已落地 — ① Strategies 改用 `.strategies-layout` 响应式 Grid（1023px 两列/767px 单列，`minmax(0,1fr)` 防溢出，结果面板表格局部滚动）；② 补 `disabled`（可读灰）、`:focus-visible` 焦点环、输入 error 状态与对应 tokens（`--color-text-disabled`/`--color-focus-ring` 等）；③ 策略元数据重写为中文（[`constants/strategy.ts`](frontend/src/constants/strategy.ts) 按后端 13 个注册名 key）+ 趋势/震荡/突破/AI 分类，列表加搜索与分组；④ [`App.tsx`](frontend/src/App.tsx) 导航改 `NavLink/Link`（自动 `aria-current`），Logo 为 Link，搜索按钮打开全局股票搜索 Modal（选中跳 `/stocks/{code}`），移动菜单 Escape 关闭 + Tab 焦点圈定 + 关闭后焦点归还 + `aria-expanded/aria-modal`；⑤ [`api.ts`](frontend/src/services/api.ts) 业务错误改为挂 `error.userMessage` 由页面呈现（新增 `getApiErrorMessage` 助手），全局仅兜底网络层未知错误，401/403 保持静默；⑥ 新增 [`useJobPolling`](frontend/src/hooks/useJobPolling.ts)（超时/AbortController 取消/卸载清理/指数退避/4xx 快速失败/onStatus），替换 Strategies、StockList、AgentAnalysis 三处重复轮询；⑦ [`index.css`](frontend/src/index.css) 拆分为 `styles/{tokens,base,layout,components,pages}.css`（入口仅 16 行聚合），新增 Vitest + Testing Library（`npm test`，18 个用例：轮询 hook、错误文案助手、策略元数据、策略列表渲染/搜索/可访问性）。**验证：** `npm run build`（tsc + vite）通过；`npm test` 18/18 通过；另修复了构建的存量阻塞——ErrorBoundary 的 `process.env` → `import.meta.env`、StockList 未使用的 `stocks` state。Playwright 关键路径与视觉回归、CSS Modules 逐步迁移留待后续轮次。

### 后端代码与架构

- `strategies.py` 1201 行、`api/strategies.py` 874 行、`orchestrator.py` 636 行。按策略族、请求 DTO、任务编排和持久化拆分，降低回归范围。
- 多处 `except Exception` 将 provider、验证、数据库和编程错误统一为 500。定义领域异常，保留 `raise ... from exc`，为外部依赖返回 502/503 和稳定错误码。
- 后台任务虽已持久化状态，但执行仍依赖 Web 进程线程；重启即失败且多实例无法协调。生产环境迁移到 Celery/RQ/Arq + Redis，增加幂等键、租约、重试和任务指标。
- 日志仅 `basicConfig`，异常栈在一次请求中被重复打印。改为结构化 JSON、request/job ID、耗时与 provider 标签；禁止记录密钥和完整模型输入。
- API 路由、服务和 schema 测试仍不足：当前主项目 4 个测试模块，行情专项测试覆盖了节点选择、故障切换、数据规范化和接口降级，但文件尚未提交。继续覆盖 WebSocket Session、迁移、后台任务并发/取消、回测边界和 API 合约。

**修复（2026-08）：** 后端 5 项全部落地 — ① 文件拆分：`strategies.py` 按策略族拆为 `strategy/{trend,reversal,breakout}.py`（`strategies.py` 保留为 re-export 枢纽，注册表仍 13 个策略）；`api/strategies.py` 拆为 `api/strategies/{schemas,routes}.py` 包 + `services/strategy/signals.py`（DTO 与信号统计独立可测）；`orchestrator.py` 拆为 `agent/{orchestrator,pipeline,prompts}.py`（四个 `_run_*` 收敛为一份通用 `run_pipeline`，quick/standard/full/strategy 阶段门控语义经测试锁定）。② 领域异常：[`exceptions.py`](backend/app/exceptions.py) 新增 `ExternalServiceError`（502，带 `provider`/`retryable`）、`ProviderUnavailableError`/`ProviderTimeoutError`（503）；API 层 provider 失败统一 `raise ... from exc`，删除了把编程错误伪装成 400/500 的 catch-all（如回测、指标、分析端点），全部走[`error_handlers.py`](backend/app/error_handlers.py) 的稳定错误码（`not_found`/`validation_error`/`provider_unavailable`/`external_service_error`…）。③ 任务执行：新增 [`services/tasks/`](backend/app/services/tasks/) — `TaskExecutor` 抽象（线程后端默认，Arq+Redis 生产后端经 `TASK_BACKEND=arq` + `requirements-arq.txt` 启用，worker 入口 `task_worker.py` 独立进程、重启不丢任务、多实例由数据库原子认领协调）；`jobs` 表新增 `job_key`（幂等键，唯一索引）、`retry_count/max_retries`（瞬时失败指数退避重试）、`lease_until/next_retry_at`（心跳租约，失联执行器任务可被回收）；同步/回测优化/Agent 分析/选股任务全部接入，`GET /api/v1/jobs/metrics` 暴露任务指标。④ 结构化日志：[`logging_config.py`](backend/app/logging_config.py) 标准库 JSON formatter + contextvars 的 request_id/job_id 关联 + 敏感键脱敏与超长截断；请求中间件记录 method/path/status/耗时并回传 `X-Request-Id`；5xx 栈只由全局 handler 打印一次（消除了重复打印），任务日志带 job_id 标签。⑤ 测试：主项目从 4 个模块扩到 14 个、`pytest` 23 → **112 全过**，新增 WebSocket Session（认证 4008/限流 4009/init 消息/连接清理）、任务系统（幂等/认领互斥/租约过期回收/重试耗尽/协作式取消/心跳）、API 错误合约、回测边界（空数据/未知标的/零资金/整手约束/单根 K 线）、pipeline 四模式门控、策略族拆分回归。**验证：** `pytest` 112/112；`alembic upgrade head` 在开发库与全新库均通过、live DB `compare_metadata` 差异为空；`ruff` 无新增债务；开发库已升级到 `20260321_01`。Arq 后端需 Redis，属生产选型，未在本机运行验证（共享生命周期逻辑与线程后端完全一致并有单测覆盖）。

### 数据模型

- 资金、价格、收益使用 `Float`，存在累计舍入误差。资金/成交金额改为 `Numeric(precision, scale)`；比例明确单位。
- `Strategy.parameters` 和分析 JSON 存为 `Text`，而 jobs 使用 JSON；应统一 JSON 类型并加 schema version。
- `user_watchlist` 没有 `user_id`，实际上是全局单用户自选股。若产品计划多用户，建立用户表和 `(user_id, stock_code)` 唯一约束。
- 缺少状态/数值约束与级联规则，如 job status、交易 action、数量/资金非负、日期区间。用 `CheckConstraint`、Enum 和明确 `ondelete` 防止脏数据。
- 需要数据生命周期：K 线归档策略、任务结果清理调度、分析记录保留期、数据库备份与恢复演练。

**修复（2026-08）：** 数据模型 5 项全部落地（迁移 `20260322_01` + `20260323_01`，开发库已升级、`compare_metadata` 差异为空）— ① **Numeric**：`daily_klines`（价格 `Numeric(12,4)`、成交量/额 `Numeric(18,2)`）、`backtest_results`（资金 `Numeric(16,2)`、收益/回撤/胜率 `Numeric(10,4)`）、`backtest_trades`（价格 `Numeric(12,4)`、金额 `Numeric(16,2)`）、`jobs.progress`/`analysis.final_confidence` `Numeric(5,4)`；列注释标明单位（元 / 百分比 % / 无量纲 / 0-1）。SQLite 读取按声明 scale 量化（与 MySQL DECIMAL 一致，ROUND_HALF_EVEN）。② **JSON 统一 + schema_version**：`strategies.parameters`、`analysis_records.opinions_json/stages_json` 由 Text 改 JSON（与 jobs 一致），三表均加 `schema_version=1`；读写端改为直接传/取对象（`json.dumps/loads` 已移除）。③ **多用户就绪**：新增 `users` 表（迁移写入默认用户 id=1），`user_watchlist.user_id`（FK CASCADE）+ `(user_id, stock_code)` 复合唯一（`uq_watchlist_user_stock`）；watchlist/dashboard 查询按 `DEFAULT_USER_ID` 隔离，前端 API 不变，接入认证后从 session 解析用户即可。④ **约束与级联**：`CheckConstraint` 覆盖 job status、trade action、数量/资金/价格非负、回测日期区间、K 线非负、analysis signal；全部外键显式命名并 `ondelete=CASCADE`（`passive_deletes=True` 配合），SQLite 整表重建（batch `copy_from`）完成。⑤ **数据生命周期**：新增 [`services/maintenance.py`](backend/app/services/maintenance.py) + [`maintenance_cli.py`](backend/maintenance_cli.py)（清理过期任务/分析/回测、K 线归档到 `daily_klines_archive`、SQLite 备份含 WAL checkpoint），systemd timer 示例（`deploy/systemd/stockbacking-maintenance.{service,timer}`，每日 03:30 执行 + 备份到独立目录）；恢复演练流程写入 README。**测试**：新增 `test_data_model.py`（精度/JSON 往返/约束/级联/多用户）+ `test_maintenance.py`（清理/归档/备份/恢复演练），`pytest` 112 → **136 全过**；迁移链 4/4（fresh upgrade、往返、compare_metadata 干净、漂移修复）。

### `TradingAgents-astock`

- 作为独立可发布包已有 `pyproject.toml`、markers 和 Docker 非 root 用户，方向正确。
- `requirements.txt` 仅包含 `.`，但没有锁文件；生产镜像每次会解析不同版本。建议生成锁、固定基础镜像 digest，并在独立 CI 中运行 unit（默认）、integration/smoke（按密钥触发）。
- `tradingagents/dataflows/a_stock.py` 达 1581 行且大量宽泛异常处理，应按数据源/领域拆分 adapter，并用统一重试、限速、缓存、数据质量 schema。
- 主应用和该包都实现行情/Agent 能力，长期会重复演进。明确边界：主应用只依赖稳定 SDK/API，子项目负责 Agent 图和数据 provider。

## 推荐实施顺序

### 第 1 周：恢复可信交付

1. 轮换密钥并清理 Git 跟踪；修复前端 build 和 Ruff。
2. 修复 SQLite 迁移，补 jobs/index 迁移和迁移 CI。
3. 解决 mootdx/httpx 依赖冲突并提交锁文件（`itsdangerous` 已补充）。
4. 升级已知漏洞依赖；用 CI 固化 test/build/audit。

### 第 2 周：修复主流程体验

1. ~~为已恢复的行情 provider 增加健康指标、缓存、明确错误状态与首页局部降级。~~ ✅ 已完成（item 7）：`FetchResult` 三态 + 2 秒缓存 + 计数器 + `/realtime/health` + 结构化 503 + Dashboard 三块独立降级 + 13 个新测试。
2. ~~重构前端认证，不再打包 API Key。~~ ✅ 已完成（item 5）：session cookie + CSRF + 生产守卫 + 21 个新测试。
3. 修复移动端 Grid、禁用态、导航可访问性和重复 toast。
4. 增加 Dashboard、策略回测、任务轮询的端到端测试。

### 第 3–4 周：生产化

1. 静态前端 + 反向代理 + 非 root systemd/Docker。
2. 独立任务队列、结构化日志、指标和告警。
3. 数据约束、Decimal/JSON 迁移、备份恢复与保留策略。
4. 拆分超大模块，统一主应用与 `TradingAgents-astock` 的接口边界。

## 完成标准

- 全新机器可用一条受支持命令安装，`pip check` 无冲突。
- 空 SQLite/MySQL 均可 `upgrade head`，模型差异为空，外键实际启用。
- `npm run build`、Ruff、后端/前端测试、依赖审计全部通过。
- 浏览器 bundle 不含长期 API Key；Cookie/CSRF/限流通过安全测试。
- Dashboard 在任一行情源失败时仍能展示其他模块；桌面、平板、390 px 手机无页面级横向滚动。
- 生产进程非 root，前端不运行 Vite dev server，具备健康检查、日志轮转、监控和恢复文档。
