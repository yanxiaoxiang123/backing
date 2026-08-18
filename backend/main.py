import logging
from contextlib import asynccontextmanager

import pymysql
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from starlette.middleware.sessions import SessionMiddleware

import app.services.strategy  # side-effect import: registers built-in strategies
from app.agent_api.paper import router as paper_router
from app.agent_api.routes import router as agent_runtime_router
from app.agent_api.tools import router as tools_router
from app.agent_chat.api import router as agent_chat_router
from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from app.api.dl_prediction import router as dl_prediction_router
from app.api.realtime import router as realtime_router
from app.api.routes import router
from app.api.screener_agent import router as screener_agent_router
from app.api.strategies import router as strategies_router
from app.api.watchlist import router as watchlist_router
from app.config import (
    SessionLocal,
    assert_safe_production_settings,
    engine,
    settings,
)
from app.error_handlers import register_error_handlers
from app.limiter import limiter
from app.logging_config import setup_logging
from app.middleware import CsrfMiddleware, RequestLoggingMiddleware
from app.models.models import Strategy
from app.services.job_store import job_store
from app.services.tasks import get_task_executor

# Structured JSON logging (request/job correlation + redaction)
setup_logging(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)


def init_db():
    """Initialize database state (bootstrap MySQL DB, seed default data).

    Schema is managed exclusively by Alembic migrations — run
    ``alembic upgrade head`` (backend/) before starting the server.
    ``Base.metadata.create_all`` was removed from startup because it silently
    masked missing migrations and let the live schema drift from the chain.
    """
    try:
        bootstrap_url = settings.bootstrap_database_url
        db_name = settings.database_name

        if bootstrap_url and db_name:
            bootstrap = make_url(bootstrap_url)
            connection = pymysql.connect(
                host=bootstrap.host or "localhost",
                port=bootstrap.port or 3306,
                user=bootstrap.username or "",
                password=bootstrap.password or "",
                charset="utf8mb4",
            )
            with connection.cursor() as cursor:
                # Validate db_name to prevent SQL injection (only allow \w chars)
                import re
                if not re.fullmatch(r"\w+", db_name):
                    raise ValueError(
                        f"Invalid database name {db_name!r}: only letters, digits, "
                        "and underscores are allowed"
                    )
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            connection.close()

        # Fail fast when migrations have not been applied, instead of silently
        # recreating tables and hiding schema drift.
        if not inspect(engine).has_table("strategies"):
            raise RuntimeError(
                "Database schema is not migrated (missing table 'strategies'). "
                "Run `cd backend && alembic upgrade head` before starting."
            )

        # Create default strategy if not exists
        db = SessionLocal()
        try:
            strategy = (
                db.query(Strategy).filter(Strategy.name == "均线交叉策略").first()
            )
            if not strategy:
                strategy = Strategy(
                    name="均线交叉策略",
                    description="短期均线上穿长期均线买入，下穿卖出",
                    strategy_type="ma_cross",
                    parameters={"short_period": 5, "long_period": 20},
                )
                db.add(strategy)
                db.commit()
                logger.info("Default strategy created")
        finally:
            db.close()

        logger.info("Database initialized successfully")
    except Exception:
        logger.exception("Database initialization failed")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    init_db()
    job_store.reset_stale_jobs()
    task_executor = get_task_executor()
    app.state.task_executor = task_executor
    task_executor.startup()
    # Agent 聊天 Harness 服务（规格 D6/D7：单 worker FIFO；seam-first，fake 先行）
    from app.agent_chat.seam import FakeHarnessChatSeam
    from app.agent_chat.service import HarnessChatService

    chat_service = HarnessChatService(
        session_factory=SessionLocal,
        seam=FakeHarnessChatSeam(session_factory=SessionLocal),
    )
    chat_service.startup()
    app.state.harness_chat_service = chat_service
    # 模拟盘 soak 撮合循环（可配置；默认开启，间隔 60s）
    from app.agent_runtime.paper.soak import PaperSoakRunner

    soak = PaperSoakRunner(
        interval_s=float(getattr(settings, "PAPER_SOAK_INTERVAL_S", 60) or 60),
        enabled=bool(getattr(settings, "PAPER_SOAK_ENABLED", True)),
    )
    soak.start()
    app.state.paper_soak = soak
    yield
    # Shutdown
    soak.stop()
    chat_service.shutdown()
    task_executor.shutdown()
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Stock Backtest API",
    description="股票回测系统后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

# Register unified error handlers (covers all router + middleware errors)
register_error_handlers(app)

# Request correlation + duration logging (X-Request-Id header)
app.add_middleware(RequestLoggingMiddleware)

# Add rate limiter to app state and error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# Session cookie middleware – signs the cookie so frontend can't tamper with it.
# Data is stored client-side (signed cookie). The secret key must be persistent
# across restarts so existing sessions remain valid. Cookie is short-lived
# (SESSION_MAX_AGE_S), SameSite=Lax, and HTTPS-only in production.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=settings.SESSION_MAX_AGE_S,
    same_site=settings.SESSION_SAMESITE,
    https_only=settings.SESSION_HTTPS_ONLY,
)

# CSRF: double-submit token required for cookie-authenticated mutations.
app.add_middleware(CsrfMiddleware)

# Fail fast: never run production with the default session secret or an
# HTTPS-only disabled session cookie.
assert_safe_production_settings(settings)

# Include routers
app.include_router(router, prefix="/api/v1", tags=["api"])
app.include_router(auth_router)
app.include_router(realtime_router, prefix="/api/v1", tags=["realtime"])
app.include_router(strategies_router)
app.include_router(agent_router, prefix="/api/v1", tags=["agent"])
app.include_router(agent_runtime_router, prefix="/api/v1", tags=["agent-runs"])
app.include_router(agent_chat_router, prefix="/api/v1", tags=["agent-chats"])
app.include_router(paper_router, prefix="/api/v1", tags=["paper"])
app.include_router(tools_router, prefix="/api/v1", tags=["tools"])
app.include_router(dl_prediction_router, prefix="/api/v1/dl", tags=["dl"])
app.include_router(watchlist_router)
app.include_router(screener_agent_router, prefix="/api/v1", tags=["screener_agent"])


@app.get("/")
def root():
    return {"message": "Stock Backtest API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        access_log=False,
    )
