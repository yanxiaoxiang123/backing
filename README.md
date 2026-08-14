# Backing

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
      backtest_engine.py      回测引擎核心
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

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：`http://localhost:5173`

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

- `GET /api/realtime/quotes?codes=600036,000001` - 批量股票行情
- `GET /api/realtime/indices` - 主要指数行情
- `GET /api/realtime/{code}?period=daily|weekly|monthly` - 股票K线数据
- `WS /api/ws/realtime/{code}?api_key=xxx` - WebSocket 实时K线推送

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
