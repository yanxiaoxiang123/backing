from collections.abc import Generator
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from app.domain.risk import RiskLimits

BACKEND_DIR = Path(__file__).resolve().parents[1]
LLM_DIR = BACKEND_DIR / "models" / "llm"


class Settings(BaseSettings):
    PAPER_RISK_LIMITS: RiskLimits = Field(default_factory=RiskLimits)
    PAPER_SOAK_ENABLED: bool = True
    PAPER_SOAK_INTERVAL_S: float = Field(default=60, ge=1)
    DATABASE_URL: str = "sqlite:///./stock_backtest.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10
    DB_BOOTSTRAP_URL: str | None = None
    HOST: str = "0.0.0.0"
    PORT: int = 8808
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )
    FRONTEND_ORIGIN: str = "http://localhost:5174"
    KLINE_PROVIDER: str = "akshare"
    STOCK_LIST_PROVIDER: str = "akshare"
    MOOTDX_SERVERS: str = (
        "180.153.18.170:7709,180.153.18.171:7709,180.153.18.172:80"
    )
    MOOTDX_TIMEOUT_S: float = 3.0
    MOOTDX_AUTO_DISCOVER: bool = True
    REALTIME_SNAPSHOT_PROVIDER: str = "mootdx"
    REALTIME_BARS_PROVIDER: str = "mootdx"
    # WebSocket 实时行情增量推送间隔（秒）
    REALTIME_WS_POLL_S: float = 10.0
    REALTIME_MEMORY_CACHE_MAX_ENTRIES: int = 512
    REALTIME_MEMORY_CACHE_MAX_BYTES: int = 64 * 1024 * 1024

    # API 认证配置
    API_KEY: str | None = None  # 用于 API 认证的密钥，为 None 时表示禁用认证
    # 浏览器登录账号（启动时写入 users 表）。AUTH_PASSWORD 未配置时回退到
    # API_KEY，保证已有部署升级后仍能登录。
    AUTH_USERNAME: str = "admin"
    AUTH_PASSWORD: str | None = None
    SESSION_SECRET: str | None = None  # session cookie 签名密钥，默认用 API_KEY
    # 运行环境：development | production。production 下若 Session secret 仍为
    # 默认值，服务启动直接拒绝（防止用默认密钥上线）。
    APP_ENV: str = "development"
    # Session cookie 参数：短期 HttpOnly cookie（SameSite + https_only + 过期）
    SESSION_MAX_AGE_S: int = 8 * 3600  # 8 小时
    SESSION_SAMESITE: str = "lax"  # lax | strict | none
    SESSION_HTTPS_ONLY: bool = False  # production 必须为 True（仅 HTTPS 发送）

    # Agent 配置
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    TAVILY_API_KEY: str | None = None
    AGENT_ORCHESTRATOR_MODE: str = "standard"
    AGENT_MAX_STEPS: int = 6
    AGENT_ORCHESTRATOR_TIMEOUT_S: int = 600
    AGENT_MEMORY_ENABLED: bool = False
    AGENT_RISK_OVERRIDE: bool = True
    # Native backend chat runtime. fake is reserved for tests/demo only.
    AGENT_CHAT_BACKEND: str = "native"
    AGENT_CHAT_MAX_STEPS: int = 6
    AGENT_CHAT_TIMEOUT_S: float = 600.0
    AGENT_CHAT_MAX_WORKERS: int = 4

    # 代理配置
    USE_PROXY: bool = False
    PROXY_HOST: str | None = None
    PROXY_PORT: int | None = None

    # 自选股列表（仪表盘用），留空则从数据服务获取所有股票
    WATCHLIST_STOCKS: str = ""

    # 长任务配置
    MAX_OPTIMIZE_COMBINATIONS: int = 200

    # 日志配置
    LOG_LEVEL: str = "INFO"

    # 任务执行配置：threads = 进程内线程执行器（开发/单实例）；
    # arq = 独立 worker + Redis（生产多实例），需设置 REDIS_URL 并安装
    # requirements-arq.txt 中的依赖。
    TASK_BACKEND: str = "threads"
    REDIS_URL: str | None = None
    TASK_MAX_RETRIES: int = 2  # 瞬时失败(provider 不可用等)的重试次数
    TASK_RETRY_BACKOFF_S: float = 5.0  # 重试退避基数（秒）
    TASK_LEASE_SECONDS: int = 120  # 租约时长，超时视为执行者失联
    TASK_HEARTBEAT_INTERVAL_S: float = 15.0  # 心跳间隔
    TASK_SWEEP_INTERVAL_S: float = 5.0  # 重试扫描间隔
    TASK_MAX_WORKERS: int = 8  # 进程内任务执行器并发上限

    # DL 模型配置
    DL_MODEL_PATH: str = str(LLM_DIR / "mg/000001/mg")
    DL_LLAMA_PATH: str = str(LLM_DIR / "Finance-Llama-8B")
    DL_MODEL_NAME: str = "best_model_r2.pth"
    DL_TIME_STEPS: int = 60
    DL_HIDDEN_SIZE: int = 256
    DL_NUM_LAYERS: int = 2
    DL_OUTPUT_SIZE: int = 5
    DL_DEVICE: str = "cuda:0"
    DL_USE_LLM: bool = True  # 是否加载 LLM 模型，设置为 False 可跳过 LLM 加载
    KRONOS_SERVICE_URL: str = ""
    KRONOS_SERVICE_TOKEN: str = ""
    KRONOS_REQUEST_TIMEOUT_S: float = Field(default=180, ge=1, le=600)
    KRONOS_JOB_TIMEOUT_S: float = Field(default=3600, ge=30, le=14400)

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    @property
    def watchlist_stocks(self) -> list[str]:
        return [s.strip() for s in self.WATCHLIST_STOCKS.split(",") if s.strip()]

    @property
    def database_name(self) -> str | None:
        return make_url(self.DATABASE_URL).database

    @property
    def session_secret(self) -> str:
        """Session cookie signing key – defaults to API_KEY or a dev fallback."""
        return self.SESSION_SECRET or self.API_KEY or "dev-session-secret-do-not-use-in-prod"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def bootstrap_database_url(self) -> str | None:
        if self.DB_BOOTSTRAP_URL:
            return self.DB_BOOTSTRAP_URL

        url = make_url(self.DATABASE_URL)
        if url.drivername.startswith("mysql") and url.database:
            return str(url.set(database=None))
        return None


# 开发环境的 Session 签名密钥回退值（生产禁止使用）
DEV_SESSION_SECRET = "dev-session-secret-do-not-use-in-prod"


def assert_safe_production_settings(s: Settings) -> None:
    """生产模式安全校验：拒绝使用默认 Session secret / 明文 cookie。

    main.py 启动时调用；校验失败直接抛错阻止启动。
    """
    if not s.is_production:
        return
    if s.session_secret == DEV_SESSION_SECRET:
        raise RuntimeError(
            "Refusing to start in production: SESSION_SECRET is not configured "
            "(using the development fallback). Set SESSION_SECRET (and API_KEY) "
            "in backend/.env before deploying."
        )
    if not s.SESSION_HTTPS_ONLY:
        raise RuntimeError(
            "Refusing to start in production: SESSION_HTTPS_ONLY must be True "
            "(session cookie would otherwise be sent over plain HTTP)."
        )


settings = Settings()

_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "echo": False,
}
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(
        {
            "pool_size": max(1, settings.DB_POOL_SIZE),
            "max_overflow": max(0, settings.DB_MAX_OVERFLOW),
            "pool_timeout": 30,
        }
    )

engine = create_engine(
    settings.DATABASE_URL,
    **_engine_kwargs,
)

if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite does not enforce foreign keys unless the PRAGMA is set on every
    # connection. Also enable WAL mode and busy timeout to avoid concurrency locks.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_pragmas(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
