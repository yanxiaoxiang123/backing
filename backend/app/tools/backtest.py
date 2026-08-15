"""backtest.* 工具：确定性回测执行（启动高成本回测需 strategy 权限）。

回测数字来自 BacktestExecutor（确定性引擎），LLM 不得修改（规格第四节）。
"""

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.backtest_executor import BacktestExecutor
from app.tools.base import Permission, Tool, ToolContext


class BacktestRunParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_name: str = Field(..., min_length=1)
    stock_code: str = Field(..., min_length=1)
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_capital: float = Field(default=100_000, gt=0)
    parameters: dict[str, Any] = Field(default_factory=dict)


def _backtest_run(params: BacktestRunParams, context: ToolContext) -> dict:
    if context.db is None:
        raise ValueError("缺少数据库会话，无法执行回测")
    result = BacktestExecutor(context.db).execute(
        strategy_name=params.strategy_name,
        stock_code=params.stock_code,
        start_date=date.fromisoformat(params.start_date),
        end_date=date.fromisoformat(params.end_date),
        initial_capital=params.initial_capital,
        parameters=params.parameters,
    )
    api = result.to_api_dict()
    return {
        "source_id": (
            f"backtest:{params.strategy_name}:{params.stock_code}:"
            f"{params.start_date}:{params.end_date}"
        ),
        "as_of": datetime.now(timezone.utc),
        "vendor": context.vendor,
        "result": api,
    }


BACKTEST_TOOLS = [
    Tool(
        name="backtest.run",
        domain="backtest",
        version="1.0.0",
        permission=Permission.STRATEGY,
        description="执行确定性回测（启动高成本回测需策略权限）",
        input_schema=BacktestRunParams,
        handler=_backtest_run,
    ),
]
