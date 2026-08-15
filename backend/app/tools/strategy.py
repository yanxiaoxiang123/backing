"""strategy.* 工具：策略注册表查询与 StrategySpec 校验（写/高成本需 strategy 权限）。"""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.strategy import StrategySpec
from app.services.strategy.registry import StrategyRegistry
from app.tools.base import Permission, Tool, ToolContext


class StrategyListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _strategy_list(params: StrategyListParams, context: ToolContext) -> dict:
    names = sorted(StrategyRegistry.list_strategies())
    return {
        "source_id": "strategy-registry",
        "vendor": context.vendor,
        "strategies": names,
        "count": len(names),
    }


class StrategyValidateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec: dict = Field(..., description="StrategySpec 声明式定义（禁止代码字符串）")


def _strategy_validate(params: StrategyValidateParams, context: ToolContext) -> dict:
    spec = StrategySpec.model_validate(params.spec)
    if spec.signal not in StrategyRegistry.list_strategies():
        raise ValueError(f"信号 {spec.signal!r} 未在策略注册表中注册")
    return {
        "source_id": "strategy-spec",
        "vendor": context.vendor,
        "valid": True,
        "name": spec.name,
        "signal": spec.signal,
        "schema_version": spec.schema_version,
    }


STRATEGY_TOOLS = [
    Tool(
        name="strategy.list",
        domain="strategy",
        version="1.0.0",
        permission=Permission.READ,
        description="列出已注册策略（只读）",
        input_schema=StrategyListParams,
        handler=_strategy_list,
    ),
    Tool(
        name="strategy.validate",
        domain="strategy",
        version="1.0.0",
        permission=Permission.STRATEGY,
        description="校验 StrategySpec（声明式；写策略需策略权限）",
        input_schema=StrategyValidateParams,
        handler=_strategy_validate,
    ),
]
