"""模拟盘归因（规格 v2 决策 24；US-3.3）。

纯函数：组合日收益相对基准（sh.000300）的分解。
- 组合收益：每日权益（现金 + 持仓市值）序列
- 基准收益：指数收盘序列
- 分解：alpha（超额）、beta（暴露）、exposure_effect、selection_effect、
  cost_drag（费用拖累）

确定性、无 IO；序列构建（equity_series）在 service 层。
"""

from __future__ import annotations

import itertools
import statistics
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AttributionReport:
    start_date: str
    end_date: str
    total_portfolio_return: float
    total_benchmark_return: float
    alpha: float
    beta: float
    exposure_effect: float
    selection_effect: float
    cost_drag: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_portfolio_return": round(self.total_portfolio_return, 6),
            "total_benchmark_return": round(self.total_benchmark_return, 6),
            "alpha": round(self.alpha, 6),
            "beta": round(self.beta, 4),
            "exposure_effect": round(self.exposure_effect, 6),
            "selection_effect": round(self.selection_effect, 6),
            "cost_drag": round(self.cost_drag, 6),
        }


def _daily_returns(values: list[float]) -> list[float]:
    returns: list[float] = []
    for prev, curr in itertools.pairwise(values):
        if prev and prev > 0:
            returns.append(curr / prev - 1.0)
    return returns


def decompose_returns(
    portfolio_values: list[float],
    benchmark_values: list[float],
    *,
    start_date: str,
    end_date: str,
    total_cost: float = 0.0,
    initial_equity: float = 0.0,
) -> AttributionReport:
    """组合收益相对基准的确定性分解。

    - total_portfolio_return = 期末/期初 - 1
    - alpha = 组合收益 - 基准收益
    - beta = cov(日收益)/var(基准日收益)（无方差时取 0）
    - exposure_effect = beta * 基准总收益（暴露贡献）
    - cost_drag = 总费用 / 期初权益
    - selection_effect = alpha - cost_drag（选股/择时残差）
    """
    if len(portfolio_values) < 2 or len(benchmark_values) < 2:
        raise ValueError("缺少权益/基准序列（至少两个观测）")
    total_portfolio = portfolio_values[-1] / portfolio_values[0] - 1.0
    total_benchmark = benchmark_values[-1] / benchmark_values[0] - 1.0
    alpha = total_portfolio - total_benchmark

    p_ret = _daily_returns(portfolio_values)
    b_ret = _daily_returns(benchmark_values)
    n = min(len(p_ret), len(b_ret))
    p_ret, b_ret = p_ret[:n], b_ret[:n]

    beta = 0.0
    if len(b_ret) >= 2 and statistics.variance(b_ret) > 1e-12:
        mean_p = statistics.mean(p_ret)
        mean_b = statistics.mean(b_ret)
        cov = sum((a - mean_p) * (b - mean_b) for a, b in zip(p_ret, b_ret)) / (n - 1)
        beta = cov / statistics.variance(b_ret)

    exposure_effect = beta * total_benchmark
    cost_drag = total_cost / initial_equity if initial_equity > 0 else 0.0
    selection_effect = alpha - cost_drag
    return AttributionReport(
        start_date=start_date,
        end_date=end_date,
        total_portfolio_return=total_portfolio,
        total_benchmark_return=total_benchmark,
        alpha=alpha,
        beta=beta,
        exposure_effect=exposure_effect,
        selection_effect=selection_effect,
        cost_drag=cost_drag,
    )
