from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import pymysql
import logging
from sqlalchemy.engine import make_url
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings, engine, Base, SessionLocal
from app.limiter import limiter
from app.api.routes import router
from app.api.strategies import router as strategies_router
from app.api.agent import router as agent_router
from app.api.dl_prediction import router as dl_prediction_router
from app.api.watchlist import router as watchlist_router
from app.api.screener import router as screener_router
from app.models.models import Strategy
import app.services.strategy  # noqa: F401 - Import to register strategies

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    """Initialize database tables"""
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
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            connection.close()

        # Create tables
        Base.metadata.create_all(bind=engine)

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
                    parameters='{"short_period": 5, "long_period": 20}',
                )
                db.add(strategy)
                db.commit()
                logger.info("Default strategy created")
        finally:
            db.close()

        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    init_db()
    yield
    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Stock Backtest API",
    description="股票回测系统后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

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

# Include routers
app.include_router(router, prefix="/api", tags=["api"])
app.include_router(strategies_router)
app.include_router(agent_router, prefix="/api", tags=["agent"])
app.include_router(dl_prediction_router, prefix="/api/dl", tags=["dl"])
app.include_router(watchlist_router)
app.include_router(screener_router, prefix="/api", tags=["screener"])


@app.get("/")
def root():
    return {"message": "Stock Backtest API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        access_log=False,
    )
