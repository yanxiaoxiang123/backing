# Backing

基于 React + FastAPI 的股票研究与回测系统，当前包含三条核心能力：

- 股票数据同步与技术指标查看
- 多策略信号生成、统一回测、参数优化
- 基于 DeepSeek 的多阶段 AI 分析（技术面 + 消息面 + 风险 + 策略 + 决策）

## 技术栈

- 前端：React 18、TypeScript、Vite、Ant Design、ECharts
- 后端：FastAPI、SQLAlchemy、Pydantic v2
- 数据：SQLite（默认开发配置）/ MySQL（可选）、baostock
- AI：DeepSeek，可选 Tavily 搜索

## 当前架构

```text
frontend/
  src/pages
    Dashboard.tsx         仪表盘
    StockList.tsx         股票同步和管理
    StockChart.tsx        K线与指标查看
    Strategies.tsx        多策略研究/回测/优化
    Backtest.tsx          兼容旧版均线回测页
    BacktestHistory.tsx   历史回测结果
    AgentAnalysis.tsx     AI 个股/大盘分析

backend/
  app/api
    routes.py             基础股票、回测、任务状态接口
    strategies.py         策略研究接口
    agent.py              AI 分析接口
  app/services
    backtest_executor.py  统一回测执行器
    backtest_engine.py   回测引擎核心
    job_store.py         轻量后台任务状态存储
    baostock_service.py  股票数据同步服务
    dashboard_service.py 仪表盘数据服务
    strategy/            策略注册、指标、优化
  app/agent/
    agents/              多阶段 AI Agent
      technical_agent.py    技术面分析
      intel_agent.py        消息面/情报分析
      risk_agent.py         风险评估
      strategy_agent.py    策略建议
      decision_agent.py    最终决策
    tools/               Agent 工具集（搜索等）
    orchestrator.py      Agent 编排器
  migrations/            Alembic 迁移
  tests/                 pytest 基础测试
```

## 已完成的关键收敛

- 统一了策略回测核心：旧回测接口、新策略接口共享同一套执行器
- 前后端参数契约统一：策略参数现在直接输出前端可消费的 `min/max/step/options`
- 长任务支持后台提交 + 轮询：股票同步、K 线同步、策略优化、AI 分析均支持提交任务后查询状态
- 去掉代码中的敏感默认值：数据库和 API key 改为环境变量输入
- 增加 Alembic 迁移骨架和 pytest 基础测试

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
python main.py
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

- `GET /api/stocks`
- `GET /api/stocks/{code}`
- `GET /api/stocks/{code}/kline`
- `GET /api/stocks/{code}/indicators`
- `GET /api/dashboard`
- `GET /api/health`

### 任务型接口

- `POST /api/stocks/sync` / `POST /api/stocks/sync/submit`
- `POST /api/stocks/sync-kline` / `POST /api/stocks/sync-kline/submit`
- `POST /api/strategies/optimize` / `POST /api/strategies/optimize/submit`
- `POST /api/agent/analyze` / `POST /api/agent/analyze/submit`
- `GET /api/jobs/{job_id}`

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

## 注意事项

- 默认数据库已切到 SQLite，方便本地快速启动；如需 MySQL，请修改 `.env`
- `Backtest.tsx` 为兼容页，主策略研究能力集中在 `Strategies.tsx`
- 任务状态当前为进程内存存储，适合单机开发；如果要上线，建议改成 Redis 或数据库持久化
