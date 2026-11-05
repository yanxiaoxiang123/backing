# Backing

### Remote Kronos on the DL prediction page

The DL page supports remote Kronos-small/base forecasts (60–512 historical bars,
1–30 future exchange sessions) alongside the existing predictor. Forecasts and
rolling backtests use durable jobs with progress, cancellation and refresh
recovery. Configure `KRONOS_SERVICE_URL` and the backend-only
`KRONOS_SERVICE_TOKEN`; deployment, pinned revisions, unit conventions, operational
checks and historical evaluation limitations are in
[deploy/kronos/README.md](deploy/kronos/README.md).

### Quant foundation update (2026-10-30)

Backend commands on this Windows workstation use the `backing` Conda environment.
New backtests use prior-session signals and next-bar open execution, configurable
fees/slippage, prior-session volume participation limits and daily-equity Sharpe.
The optimizer uses the same simulation. Existing historical results are unchanged.
Rates are research assumptions, not a historical exchange-rule database.
Locked OHLC bars are conservatively blocked, residual exits are all-or-nothing,
and positions remaining at the end are marked to market rather than forcibly sold.

Run `python -m alembic upgrade head` before starting the updated backend. Revision
`20261030_02` adds nullable backtest execution metadata. New records include source
bars, signals, costs, a checksum and engine version; old records cannot be replayed.
Authenticated endpoints:

- `GET /api/v1/data/quality`: coverage and invalid OHLCV counts.
- `GET /api/v1/data/backtests/{result_id}/replay`: replay saved inputs without providers.
- `POST /api/v1/strategies/backtest`: optional `costs` object with `commission_rate`,
  `minimum_commission`, `sell_tax_rate`, `transfer_rate`, `slippage_rate`,
  `max_participation` and `lot_size`.

Data synchronization commands (working directory `backend/`):

```powershell
conda run -n backing python data_sync_cli.py --quality-only
conda run -n backing python data_sync_cli.py --codes sz.000001 sh.600000 --days 730
conda run -n backing python data_sync_cli.py --days 730
conda run -n backing python data_sync_cli.py --all --days 730
```

Without `--codes`/`--all`, synchronization uses the watchlist. Missing history or
provider failures return exit code 2. Linux scheduler examples are in
`deploy/systemd/stockbacking-data-sync.{service,timer}`; adapt installation paths
and enable the timer on the intended host. These templates are not automatically
installed. A verified exchange calendar, corporate actions and PIT adjustments are
still required: coverage alone does not certify historical data correctness.
Research runs no longer create hardcoded demonstration buy approvals.

Implementation status: `docs/plans/2026-10-30-quant-platform-implementation.md`.

### Versioned market data (2026-10-30, batch 2)

Migration `20261030_03` adds raw-price batches with content checksums, dated
exchange sessions, security observations (including delisted securities), and
corporate-action/factor observations. Existing candles are archived explicitly as
`legacy_unknown`; archival preserves the original rows. Raw and adjusted prices
are never merged into the same query result. Observation time is distinct from
effective date; missing publication times cannot support historical event queries.
The factor semantics follow the [BaoStock adjustment-factor description](https://www.baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%9B%A0%E5%AD%90%E7%AE%80%E4%BB%8B.pdf).

The synchronization CLI now downloads versioned raw prices by default. Use
`--legacy` only for the old adjusted-price synchronization path. Additional modes:

```powershell
conda run -n backing python data_sync_cli.py --archive-legacy
conda run -n backing python data_sync_cli.py --calendar-only --days 730
conda run -n backing python data_sync_cli.py --securities --codes sz.000001 --metadata
conda run -n backing python data_sync_cli.py --all --report-file data/sync/full-market-report.json
```

`--metadata` requests corporate actions and factors. It stores provider payloads;
it does not relabel an unverified publication date or automatically apply factors
to old experiments. Ingestion checks all verified open sessions, including holes
inside an existing date interval. Missing sessions remain explicit failures until
verified suspension/status data or missing candles resolve them. API/CLI ingestion
shares a process-held file lock on each database for this single-host deployment.

The stock-management screen now displays real data coverage and supports a
persisted raw-price download job for the current page. Authenticated endpoints:

- `POST /api/v1/data/history/sync`: submit codes, start/end dates and optional metadata.
- `GET /api/v1/data/history/{stock_code}`: raw-price history, provenance, optional
  observation cutoff, and calendar-gap report.

Windows installation: `deploy/windows/install-data-sync.ps1 -Python <backing-python>`.
It registers `Backing-MarketDataSync` at 17:00 in the workstation's local timezone,
with overlapping scheduled instances disabled. The current workstation uses
Asia/Shanghai. The task uses the logged-in user token; unattended execution after
logout requires an appropriate service account on the deployment host.

Task startup recovery now preserves queued jobs and jobs with live execution
leases. Only expired executions are requeued; restarting an API must not mark a
different worker's live ingestion failed.

基于 React + FastAPI 的股票研究与回测系统，包含以下核心能力：

- **数据服务**：股票列表同步、K 线数据、技术指标计算
- **策略研究**：多策略信号生成、统一回测、参数优化
- **AI 分析**：基于 DeepSeek 的多阶段 AI 分析（技术面 + 消息面 + 风险 + 策略 + 决策）
- **股票筛选器**：全市场扫描 + 技术指标选股 + AI 深度分析 TOP 5
- **实时行情**：股票/指数实时行情（HTTP + WebSocket）

## 技术栈

- 前端：React 18、TypeScript、Vite、Ant Design、ECharts
- 后端：FastAPI、SQLAlchemy、Pydantic v2、slowapi（限流）
- 数据：SQLite（默认）/ MySQL、baostock、mootdx
- AI：DeepSeek（支持多 Agent 编排）、可选 Tavily 搜索

## 项目结构

```
frontend/
  src/
    pages/
      Dashboard.tsx         仪表盘
      StockList.tsx         股票同步和管理
      StockChart.tsx         K线与指标查看
      Strategies.tsx         多策略研究/回测/优化
      AgentAnalysis.tsx      AI 个股/大盘分析
      Screener.tsx           AI 股票筛选器
      DLPrediction.tsx       深度学习价格预测
      Watchlist.tsx          自选股管理
      BacktestHistory.tsx    历史回测结果
    components/
      ErrorBoundary.tsx      React 错误边界
      strategies/            策略配置和结果显示组件
      analysis/               AI 分析结果展示组件
    services/api.ts          前端 API 调用封装

backend/
  app/
    api/
      routes.py              基础股票、回测、任务状态接口
      strategies.py           策略研究接口
      agent.py                AI 分析接口
      screener.py             股票筛选器接口
      screener_agent.py       筛选器 AI 深度分析任务
      realtime.py             实时行情（HTTP + WebSocket）
      watchlist.py            自选股接口
      dl_prediction.py        深度学习预测接口
    services/
      backtest_executor.py    统一回测执行器
      indicator_service.py    技术指标计算（带缓存）
      screener_service.py     选股扫描服务
      realtime_service.py     实时行情服务
      job_store.py            后台任务状态存储
      baostock_service.py     股票数据同步服务
      dashboard_service.py    仪表盘数据服务
      strategy/
        base.py              策略基类
        factors.py           技术指标库
        optimizer.py          参数优化器
        registry.py          策略注册表
        strategies.py        内置策略
    agent/
      agents/
        technical_agent.py   技术面分析 Agent
        intel_agent.py       消息面/情报 Agent
        risk_agent.py        风险评估 Agent
        strategy_agent.py    策略建议 Agent
        decision_agent.py    最终决策 Agent
      tools/                  Agent 工具集
      orchestrator.py         多阶段 Agent 编排器
      runner.py               Agent 运行器
      memory.py               Agent 记忆管理
    models/
      models.py              核心数据模型
      analysis.py            分析记录模型
    error_handlers.py         统一错误处理
    exceptions.py            自定义异常类
    limiter.py               限流配置
  migrations/                 Alembic 数据库迁移
  tests/                     pytest 测试
```

## 已完成的关键收敛

- 统一了策略回测核心：旧回测接口、新策略接口共享同一套执行器
- 前后端参数契约统一：策略参数现在直接输出前端可消费的 `min/max/step/options`
- 长任务支持后台提交 + 轮询：股票同步、K 线同步、策略优化、AI 分析均支持提交任务后查询状态
- 去掉代码中的敏感默认值：数据库和 API key 改为环境变量输入
- 增加 Alembic 迁移骨架和 pytest 基础测试
- 实时行情统一认证（HTTP + WebSocket 均需 API Key）
- 股票筛选器：全市场并行扫描 + 技术指标 + AI 深度分析 TOP 5

## 快速开始

### 1. 后端

需要 Python **3.11+**（已在 3.12 验证）。依赖已按验证过的版本固定，`mootdx` 使用仓库内 `backend/vendor/mootdx` 的本地补丁版（放宽了与 `httpx>=0.28` 冲突的过期约束，详见该目录 README）：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
python main.py
```

需要完全可复现的环境（含全部传递依赖）时，用锁文件安装：

```bash
pip install -r requirements.lock
```

默认后端地址：`http://localhost:8808`

#### 可选 Redis 缓存

行情、研究数据和技术指标可以使用 Redis 作为共享二级缓存。Redis 仅保存可丢弃缓存，不替代数据库，也不会因为设置 `REDIS_URL` 自动切换到 Arq 任务队列。Redis 暂时不可用时服务会退回进程内缓存，因此个人单机部署可以不安装 Redis。

##### 方式 A：使用 Docker Compose

macOS 首次使用需要先安装并启动 Docker Desktop。确认 Docker 引擎已运行后，在项目根目录执行：

```bash
brew install --cask docker       # 仅首次执行
open -a Docker                   # 等待 Docker Desktop 启动完成
docker --version
docker compose version
docker compose -f deploy/docker-compose.redis.yml up -d
```

##### 方式 B：使用 Homebrew 原生 Redis（macOS）

不想安装 Docker 时，可以直接安装 Redis 服务：

```bash
brew install redis                # 仅首次执行
brew services start redis
redis-cli ping                     # 应返回 PONG
```

##### 接入后端

Redis 启动后，在 `backend/.env` 添加或取消注释：

```env
REDIS_URL=redis://127.0.0.1:6379/1
```

然后重启后端。检查 Redis 状态：

```bash
redis-cli ping
```

如果暂时不使用 Redis，请不要设置 `REDIS_URL`；后端会自动使用有容量上限的内存缓存。Redis 连接失败时也会自动降级，不影响应用启动。

#### 内存基线

可用脚本记录进程 RSS 和 Python 分配峰值，比较冷启动或固定观察窗口的变化：

```bash
cd backend
python scripts/memory_baseline.py --import-app --seconds 30
```

实时行情缓存的条目数、估算字节数和淘汰次数可通过认证接口
`GET /api/v1/realtime/health` 的 `memory_cache` 字段查看。

### 2. 前端

```bash
cd frontend
npm ci            # 或首次开发用 npm install
npm run dev
```

默认前端地址：`http://localhost:5174`（Vite 代理 `/api` 到 `:8808`）

### 3. 认证与会话

- **不要**在构建期注入密钥：`VITE_*` 变量会进入浏览器 bundle，前端已无 `VITE_API_KEY`。
- 首次打开前端会跳转登录页，输入 `backend/.env` 中的 `API_KEY` 换取**短期 HttpOnly session cookie**（8 小时，SameSite=Lax，生产环境仅 HTTPS 发送）。
- 状态变更请求自动携带 `csrf_token`（double-submit）；登录接口限流 10 次/分钟。
- 生产部署：`APP_ENV=production` 时必须设置独立 `SESSION_SECRET` 且 `SESSION_HTTPS_ONLY=true`，否则服务拒绝启动。
- 外部 API 客户端仍可用 `X-API-Key` 头直接调用。

### 4. 代码质量与 CI

```bash
cd frontend
npm run typecheck   # tsc --noEmit
npm run lint        # ESLint
npm run format:check # Prettier 格式检查
npm run build       # 类型检查 + 产物构建
npm test            # Vitest
cd ../backend
ruff check app/ main.py task_worker.py maintenance_cli.py migrations/ tests/
pytest
```

PR 由 [`.github/workflows/ci.yml`](.github/workflows/ci.yml) 强制执行上述检查（后端 ruff+pytest、前端 typecheck+lint+format+build+test）；在仓库设置中把对应 status check 设为 required 即为 PR 必过。

## 主要接口

### 基础数据

- `GET /api/stocks` - 股票列表
- `GET /api/stocks/{code}` - 股票详情
- `GET /api/stocks/{code}/kline` - K线数据
- `GET /api/stocks/{code}/indicators` - 技术指标
- `GET /api/dashboard` - 仪表盘数据
- `GET /api/health` - 健康检查
- `GET /api/indices` - 指数列表
- `GET /api/indices/{code}/kline` - 指数K线

### 实时行情

- `GET /api/realtime/quotes?codes=600036,000001` - 批量股票行情（provider 不可达时返回 503 + `provider_unavailable`）
- `GET /api/realtime/indices` - 主要指数行情（同上）
- `GET /api/realtime/{code}?period=daily|weekly|monthly` - 股票K线数据（可达但无数据 → 200 + `data: []`；provider 不可达 → 503）
- `GET /api/realtime/health` - Provider 健康快照：选中节点、池规模、计数器（requests/failovers/cache_hits/provider_unavailable）
- `WS /api/ws/realtime/{code}?api_key=xxx` - WebSocket 实时K线推送（init/update 帧附带 `status` 字段）

### 股票筛选器

- `POST /api/screener` - 执行筛选（同步）
- `POST /api/screener/submit` - 提交筛选任务（异步，AI 深度分析）
- `GET /api/screener/{job_id}` - 查询筛选任务状态

### 回测与策略

- `POST /api/backtest`
- `GET /api/backtest/results`
- `GET /api/backtest/{id}`
- `GET /api/strategies`
- `POST /api/strategies/signals`
- `POST /api/strategies/backtest`
- `POST /api/strategies/optimize`

### AI 分析

- `POST /api/agent/analyze`
- `GET /api/agent/history`
- `GET /api/agent/{id}`
- `GET /api/agent/indices`
- `POST /api/agent/market/analyze`

## 研究行情、公司行动与风险证据

策略研究页默认使用原始价格及含分红送转的记账口径。先选择区间并点击
“补齐研究数据”；数据不完整、分红登记/支付日期不明确时会拒绝执行。
“仅价格收益”不计分红送转；旧行情兼容模式会明确标注复权口径未知。
历史图表、信号、参数优化和回测使用统一行情选择逻辑，禁止在同一区间
拼接原始价格与旧复权价格。

```powershell
cd backend
python data_sync_cli.py --codes sh.600000 --days 730 --metadata
# 独立补齐分红与全量复权因子，不与正在运行的价格补数争用同一个下载锁
python data_sync_cli.py --codes sh.600000 --days 730 --metadata-only
```

分红按登记日持仓取得权益，除息日计应收现金，支付日才可使用；送转股
上市前计入估值但不可卖出。分红税率是用户选择的固定研究假设，0 代表
税前收益。缺少付款/上市日期、无法确定碎股分配、无法匹配的配股等除权
事件会使 `verified` 口径失败，禁止静默忽略。交易前一已完成日的信号仅
尝试在下一交易日执行；停牌日只记估值，不制造原始价格蜡烛。

`GET /api/v1/data/history/{code}?start_date=...&end_date=...&adjustment=raw|qfq|hfq`
返回来源批次、观察截止时间和覆盖检查。前后复权图是按当前可核验因子
生成的回顾视图，不代表历史当时已知的信息，也不作为成交价格。
因子算法依据 [BaoStock 官方复权说明](https://www.baostock.com/helpdocs/pdf/BaoStock%E5%A4%8D%E6%9D%83%E5%9B%A0%E5%AD%90%E7%AE%80%E4%BB%8B.pdf)。

`GET /api/v1/data/backtests/{id}/replay` 从保存的输入、信号、交易日历、成本和
公司行动快照重放；新结果包含执行快照校验和，不依赖后来修改的行情。
全市场下载可能耗时较长；进度报告中失败或未处理证券不计为补数完成。
下载适配器通过独立进程限制单次 SDK 请求为 45 秒，超时后关闭该连接并
报告失败，不让阻塞的网络调用无限占用任务。

Agent 工作台“风险”页可输入明确的目标权重、止损距离和理由。
`POST /api/v1/agent-runs/{run_id}/risk` 接收 `targets`，每项包含
`stock_code/target_weight/stop_loss_pct/reason`；可提供 `limits` 调整研究约束。
创建 run 时也可用 `risk_request` 保存同一结构，供风险节点读取。
服务端核对真实账户、T+1 可卖股数、在途委托资金、最新已完成日原始价格、
集中度、止损风险及成交量容量，保存请求与评估证据。评估不会创建委托或
审批。模拟委托的提议、审批及成交现在均要求绑定风险证据并重新核验；
没有风险证据的历史未完成委托不会继续撮合。当前仍是单账户模型，
多账户归属、角色权限和审批人员隔离尚待完成。

## 组合研究

启动前执行 `cd backend && alembic upgrade head`，新增实验表对应迁移
`20261031_01`。前端侧栏“组合研究”（`/portfolio`）支持指定最多 20 只股票的
目标权重、初始资金、再平衡频率与买入持有基准；权重不足 100% 的部分留在现金。
选中股票或更换研究区间后，页面自动获取该区间的原始行情与分红送转，并显示进度。
基准证券也会一起检查；已准备好的同区间数据会复用。获取失败可在页面内重试，
点击运行时会先等待所选数据准备完成，再执行回测，无需跳到股票管理手工同步。

组合共用一笔资金，按前一交易日收盘确定数量，下一交易日开盘先卖后买。
资金不足时按比例缩减买单，成交量容量仅使用前一已完成交易日；停牌、一字板及
未成交余量不会被延后到任意未来日期成交。每周/每月配置在当期首个交易日收盘后
确定，随后开盘执行。成本、税率和滑点均为可修改的固定研究假设。

默认要求原始行情、完整交易日历、停牌证据和分红送转覆盖；也可明确选择仅价格收益。
这是用户指定股票集合的事后研究，不代表历史时点的自动选股结果或实盘表现。
基准使用相同资金、成本和分红处理买入持有，不等同于指数发布收益。

认证接口 `POST/GET /api/v1/portfolio-research` 创建或列出当前主体的实验，
`GET /{experiment_id}` 查看结果，`POST /{experiment_id}/replay` 从保存输入重放，
`GET /{experiment_id}/export` 下载完整 JSON 实验包（后三项均在同一路径前缀下）。
行情、交易日历、公司行动与参数组成输入快照，输入快照和结果分别保存校验和；
重放不读取后来修订的行情。
该主体范围沿用现有登录/API key 认证，完整的多用户角色权限仍在后续计划中。

## 测试

```bash
cd backend
pytest
```

## 数据生命周期

后台任务状态持久化在数据库（`jobs` 表，幂等键/租约/重试），K 线、分析记录与回测结果按保留期清理，K 线可归档：

```bash
cd backend
python maintenance_cli.py jobs --days 30        # 清理过期任务记录
python maintenance_cli.py analysis --days 180   # 清理过期分析记录
python maintenance_cli.py backtests --days 365  # 清理过期回测结果
python maintenance_cli.py archive-klines --before 2015-01-01  # 归档历史 K 线
python maintenance_cli.py backup --out /backup/dir   # SQLite 备份（WAL checkpoint + 自动命名）
python maintenance_cli.py all                    # 默认保留期执行全部清理
```

生产环境挂 systemd timer 每日执行（`deploy/systemd/stockbacking-maintenance.{service,timer}`）。
MySQL 备份用 `mysqldump`；**恢复演练**：停服 → 用备份文件覆盖数据库 → 起服 →
`alembic upgrade head` 校验迁移版本 → 抽查关键表计数（stocks / jobs / 最新 K 线日期）。

## 注意事项

- 默认数据库已切到 SQLite，方便本地快速启动；如需 MySQL，请修改 `.env`
- 启动前必须 `alembic upgrade head`（schema 完全由迁移管理，`compare_metadata` 差异应为空）
- 资金/价格/收益列为 `Numeric`（元 / 百分比 % / 无量纲，见模型注释）；外键显式 `ondelete=CASCADE`
- 自选股当前归属默认用户（多用户就绪：`users` 表 + `(user_id, stock_code)` 唯一约束）
- `Backtest.tsx` 为兼容页，主策略研究能力集中在 `Strategies.tsx`
- 后台任务默认在进程内线程执行（`TASK_BACKEND=threads`，状态持久化，重启自动重置在途任务）；
  生产多实例用 `TASK_BACKEND=arq` + Redis（`pip install -r requirements-arq.txt` + `python task_worker.py`）
