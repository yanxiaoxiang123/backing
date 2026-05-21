# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Superpowers 工作流规则 (必须严格遵守)

**所有任务必须使用 superpowers skill 流程，不得跳过。**

收到任何任务后，按以下顺序执行：

1. **立即调用 `Skill` 工具**检查适用的 superpowers skill（哪怕只有 1% 可能性）
2. **Announce**：明确宣布"Using [skill] to [purpose]"
3. **遵循 skill 流程**：严格按照 skill 内容执行，不得自行简化或跳过步骤

### 必须使用的核心 skills

| 场景 | Skill |
|------|-------|
| 任何 bug/问题排查 | `superpowers:systematic-debugging` |
| 任何新功能/特性开发 | `superpowers:brainstorming` (先行) + `superpowers:test-driven-development` |
| 完成实现后、提交前 | `superpowers:verification-before-completion` |
| 代码审查 | `superpowers:requesting-code-review` |
| 收到代码审查反馈 | `superpowers:receiving-code-review` |
| 复杂多步骤任务 | `superpowers:subagent-driven-development` |

### Red Flags (禁止的思维模式)

以下想法意味着 **STOP**，必须先调用 skill 检查：
- "这只是个小问题" — 问题即任务，必须检查
- "我需要先了解上下文" — skill 检查在澄清问题之前
- "先探索代码库" — skills 指导如何探索
- "这不需要 formal skill" — 如果 skill 存在，就必须使用
- "我知道这意味着什么" — 知道概念 ≠ 使用 skill
- "我先做完这个" — 先检查，再行动
- "感觉很有成效" — 无纪律的行动浪费时间

### 规则优先级

1. 用户的明确指令 (CLAUDE.md, GEMINI.md, AGENTS.md, 直接请求) — **最高优先级**
2. Superpowers skills — 覆盖默认行为
3. 默认 system prompt — **最低优先级**

## Project Overview

Backing is a stock research and backtesting system with React + FastAPI. The repository contains multiple projects; this file focuses on the `backing/` subdirectory.

## Commands

### Backend

```bash
cd backing/backend

# Setup - uses conda virtual environment named 'stockbacking'
conda activate stockbacking
pip install -r requirements.txt
cp .env.example .env

# Run migrations
alembic upgrade head

# Development server (hot reload)
python main.py
# Or: uvicorn main:app --reload --host 0.0.0.0 --port 8808

# Run tests
pytest
pytest tests/test_backtest_executor.py  # Single test file
pytest -v  # Verbose output

# Linting
ruff check .
ruff check --fix .  # Auto-fix

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"  # Create new migration
```

### Frontend

```bash
cd backing/frontend

# Install dependencies
npm install

# Development
npm run dev

# Build for production
npm run build
```

### Frontend Page Organization

- `Dashboard.tsx` — Main dashboard with market overview
- `StockList.tsx` — Stock sync and management
- `StockChart.tsx` — K-line chart with indicators
- `Strategies.tsx` — Main strategy research interface (signals, backtest, optimization)
- `Backtest.tsx` — Legacy MA-based backtest compatibility page
- `BacktestHistory.tsx` — Historical backtest results viewer
- `AgentAnalysis.tsx` — AI multi-stage analysis (technical + news + risk + strategy + decision)
- `DLPrediction.tsx` — Deep learning price prediction
- `Screener.tsx` — Stock screener
- `Watchlist.tsx` — User watchlists

## Architecture

### Backend Structure

```
backend/
├── app/
│   ├── api/              # FastAPI route handlers
│   │   ├── routes.py     # Stock data, backtest, job status
│   │   ├── strategies.py # Strategy signals, backtest, optimization
│   │   ├── agent.py      # AI analysis endpoints
│   │   ├── dl_prediction.py # Deep learning predictions
│   │   ├── screener.py   # Stock screener
│   │   └── watchlist.py  # User watchlists
│   ├── services/         # Business logic
│   │   ├── backtest_engine.py   # Core backtesting engine
│   │   ├── backtest_executor.py # Unified backtest executor
│   │   ├── baostock_service.py  # Stock data sync
│   │   ├── dashboard_service.py # Dashboard data
│   │   ├── indicator_service.py # Technical indicators
│   │   ├── job_store.py         # Async job status storage
│   │   ├── dl_prediction/       # DL model training & inference
│   │   │   ├── backtest.py, features.py, model_loader.py, predictor.py
│   │   └── strategy/
│   │       ├── base.py    # Strategy abstract class
│   │       ├── factors.py # Technical indicators library
│   │       ├── optimizer.py # Parameter optimization
│   │       ├── registry.py # Strategy registration
│   │       └── strategies.py # Built-in strategies
│   ├── agent/            # Multi-stage AI analysis
│   │   ├── agents/
│   │   │   ├── technical_agent.py  # Technical analysis
│   │   │   ├── intel_agent.py      # News/intelligence
│   │   │   ├── risk_agent.py       # Risk assessment
│   │   │   ├── strategy_agent.py   # Strategy suggestions
│   │   │   └── decision_agent.py   # Final decision
│   │   ├── memory.py       # Agent conversation memory
│   │   ├── protocols.py     # Agent communication protocols
│   │   ├── orchestrator.py  # Agent orchestration
│   │   ├── runner.py       # Agent execution
│   │   ├── llm_adapter.py  # DeepSeek API integration
│   │   └── config.py       # Agent configuration
│   ├── auth.py           # JWT authentication
│   ├── limiter.py        # Rate limiting
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   └── config.py         # Settings (pydantic-settings)
├── migrations/           # Alembic DB migrations
└── tests/                # pytest tests
```

### Key Patterns

**Strategy System**: All strategies inherit from `Strategy` base class in `app/services/strategy/base.py`. New strategies are registered using the `@register_strategy` decorator in `app/services/strategy/registry.py`.

**Backtesting Flow**:
1. API receives backtest request (`POST /api/strategies/backtest`)
2. `backtest_executor.py` coordinates execution
3. `backtest_engine.py` runs the simulation
4. Returns trade history and metrics

**Long-running Tasks**: Uses job submission pattern with polling:
- Submit task → get job_id
- Poll `GET /api/jobs/{job_id}` for status
- Job states: `pending` → `running` → `completed` | `failed`
- **Note**: Job status is stored in-process memory (`job_store.py`); restarts clear state. Use Redis or DB for production.

**Agent System**: Multi-stage pipeline:
```
technical_agent → intel_agent → risk_agent → strategy_agent → decision_agent
```

**API Endpoints** (all under `/api`):
- Stocks: `GET /stocks`, `GET /stocks/{code}`, `GET /stocks/{code}/kline`, `GET /stocks/{code}/indicators`
- Backtest: `POST /backtest`, `GET /backtest/results`, `GET /backtest/{id}`
- Strategies: `GET /strategies`, `POST /strategies/signals`, `POST /strategies/backtest`, `POST /strategies/optimize`
- Agent: `POST /agent/analyze`, `GET /agent/history`, `GET /agent/indices`
- Jobs (async): `POST /stocks/sync/submit`, `POST /strategies/optimize/submit`, `GET /jobs/{job_id}`

### Database

- Default: SQLite (`stock_backtest.db`)
- Optional: MySQL (configure via `.env`)
- Uses SQLAlchemy 2.0 with Pydantic v2

### Environment Variables

Key variables in `.env`:
- `DATABASE_URL` - Database connection
- `DEEPSEEK_API_KEY` - AI model API key
- `TAVILY_API_KEY` - Web search (optional)
- `KLINE_PROVIDER` - `akshare` (default) or other
- `PORT` - Server port (default 8808)

## Adding New Strategies

1. Create new class in `app/services/strategy/strategies.py` extending `Strategy`
2. Use `@register_strategy("strategy_name")` decorator
3. Implement: `generate_signals()`, `get_parameters()`, `get_name()`, `get_description()`
4. The strategy auto-registers and appears in API

## Testing Strategy Code

```python
# Pattern for testing strategies
from app.services.strategy.strategies import MACrossStrategy
from app.services.strategy.factors import TechnicalFactors

def test_ma_cross_signal():
    strategy = MACrossStrategy(short_period=5, long_period=20)
    # Create test DataFrame with OHLCV data
    df = pd.DataFrame({...})
    result = strategy.generate_signals(df)
    assert 'signal' in result.columns
```

## gstack

Use gstack's `/browse` skill for web browsing. All available gstack skills (including `/qa`, `/review`, `/investigate`) are listed in the skills panel and discoverable at runtime.
