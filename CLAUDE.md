# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Architecture

### Backend Structure

```
backend/
├── app/
│   ├── api/              # FastAPI route handlers
│   │   ├── routes.py    # Stock data, backtest, job status
│   │   ├── strategies.py # Strategy signals, backtest, optimization
│   │   └── agent.py     # AI analysis endpoints
│   ├── services/        # Business logic
│   │   ├── backtest_engine.py   # Core backtesting engine
│   │   ├── backtest_executor.py # Unified backtest executor
│   │   ├── baostock_service.py  # Stock data sync
│   │   ├── dashboard_service.py # Dashboard data
│   │   ├── indicator_service.py # Technical indicators
│   │   ├── job_store.py         # Async job status storage
│   │   └── strategy/
│   │       ├── base.py    # Strategy abstract class
│   │       ├── factors.py # Technical indicators library
│   │       ├── optimizer.py # Parameter optimization
│   │       ├── registry.py # Strategy registration
│   │       └── strategies.py # 7 built-in strategies
│   ├── agent/            # Multi-stage AI analysis
│   │   ├── agents/
│   │   │   ├── technical_agent.py  # Technical analysis
│   │   │   ├── intel_agent.py      # News/intelligence
│   │   │   ├── risk_agent.py       # Risk assessment
│   │   │   ├── strategy_agent.py   # Strategy suggestions
│   │   │   └── decision_agent.py   # Final decision
│   │   ├── orchestrator.py  # Agent orchestration
│   │   ├── runner.py        # Agent execution
│   │   ├── llm_adapter.py  # DeepSeek API integration
│   │   └── config.py       # Agent configuration
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   └── config.py         # Settings (pydantic-settings)
├── migrations/          # Alembic DB migrations
└── tests/               # pytest tests
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

**Agent System**: Multi-stage pipeline:
```
technical_agent → intel_agent → risk_agent → strategy_agent → decision_agent
```

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
