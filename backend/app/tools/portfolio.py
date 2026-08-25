"""portfolio.* 工具：组合风险硬约束（确定性纯函数，只读）。"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.tools.base import Permission, Tool, ToolContext

Action = Literal["buy", "sell"]


class PositionParam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1)
    action: Action
    weight: float = Field(..., ge=0, le=1)
    shares: int | None = Field(default=None, ge=0)


class PortfolioConstraintsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positions: list[PositionParam] = Field(min_length=1)
    lot_size: int = Field(default=100, ge=1)
    t_plus_1: bool = Field(default=True)


def _portfolio_constraints(
    params: PortfolioConstraintsParams, context: ToolContext
) -> dict:
    results: list[dict] = []

    total_weight = sum(p.weight for p in params.positions)
    weight_ok = total_weight <= 1.0 + 1e-9
    results.append(
        {
            "rule": "position_weight_sum",
            "passed": weight_ok,
            "detail": f"仓位权重合计 {total_weight:.3f}（≤1.0）",
        }
    )

    lot_violations = [
        p.code
        for p in params.positions
        if p.shares is not None and p.shares > 0 and p.shares % params.lot_size != 0
    ]
    results.append(
        {
            "rule": "lot_size",
            "passed": not lot_violations,
            "detail": (
                f"手数违规: {lot_violations}" if lot_violations else "全部委托为整数手"
            ),
        }
    )

    if params.t_plus_1:
        codes_with_both = {
            p.code for p in params.positions if p.action == "buy"
        } & {p.code for p in params.positions if p.action == "sell"}
        results.append(
            {
                "rule": "t_plus_1",
                "passed": not codes_with_both,
                "detail": (
                    f"同日买卖违规: {sorted(codes_with_both)}"
                    if codes_with_both
                    else "无同日买卖"
                ),
            }
        )

    passed = all(r["passed"] for r in results)
    return {
        "source_id": "portfolio-constraints",
        "as_of": context.as_of or datetime.now(timezone.utc),
        "vendor": context.vendor,
        "passed": passed,
        "total_weight": round(total_weight, 4),
        "constraints": results,
        "rejected": not passed,
        "rejection_reasons": [r["detail"] for r in results if not r["passed"]],
    }


PORTFOLIO_TOOLS = [
    Tool(
        name="portfolio.constraints",
        domain="portfolio",
        version="1.0.0",
        permission=Permission.READ,
        description="组合硬约束检查（仓位合计/手数/T+1，确定性纯函数）",
        input_schema=PortfolioConstraintsParams,
        handler=_portfolio_constraints,
    ),
]
