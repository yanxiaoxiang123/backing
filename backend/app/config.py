from typing import Generator, List, Optional
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
LLM_DIR = BACKEND_DIR / "models" / "llm"


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./stock_backtest.db"
    DB_BOOTSTRAP_URL: Optional[str] = None
    HOST: str = "0.0.0.0"
    PORT: int = 8808
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    KLINE_PROVIDER: str = "akshare"
    STOCK_LIST_PROVIDER: str = "akshare"

    # API 认证配置
    API_KEY: Optional[str] = None  # 用于 API 认证的密钥，为 None 时表示禁用认证

    # Agent 配置
    DEEPSEEK_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    AGENT_ORCHESTRATOR_MODE: str = "standard"
    AGENT_MAX_STEPS: int = 6
    AGENT_ORCHESTRATOR_TIMEOUT_S: int = 600
    AGENT_MEMORY_ENABLED: bool = False
    AGENT_RISK_OVERRIDE: bool = True

    # 代理配置
    USE_PROXY: bool = False
    PROXY_HOST: Optional[str] = None
    PROXY_PORT: Optional[int] = None

    # 自选股列表（仪表盘用），留空则从数据服务获取所有股票
    WATCHLIST_STOCKS: str = ""

    # 长任务配置
    MAX_OPTIMIZE_COMBINATIONS: int = 200

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

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    @property
    def cors_origins_list(self) -> List[str]:
        return [
            origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    @property
    def watchlist_stocks(self) -> List[str]:
        return [s.strip() for s in self.WATCHLIST_STOCKS.split(",") if s.strip()]

    @property
    def database_name(self) -> Optional[str]:
        return make_url(self.DATABASE_URL).database

    @property
    def bootstrap_database_url(self) -> Optional[str]:
        if self.DB_BOOTSTRAP_URL:
            return self.DB_BOOTSTRAP_URL

        url = make_url(self.DATABASE_URL)
        if url.drivername.startswith("mysql") and url.database:
            return str(url.set(database=None))
        return None


settings = Settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
