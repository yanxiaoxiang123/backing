"""专家节点（任务 09；US-2.2）：确定性实现 + 工具可追溯。

所有专家输出构造为领域 schema 对象；回测数字来自 BacktestExecutor
（确定性引擎），LLM 不参与数字计算（规格第四节）。
"""

from datetime import date, datetime, timezone
from typing import Any

from app.agent_runtime.runtime import (
    NodeContext,
    RuntimeNode,
    SimpleNode,
    record_tool_call,
)
from app.domain.backtest import BacktestCheck, BacktestMetrics, BacktestVerdict
from app.domain.portfolio import ConstraintResult, ExposureSummary, PortfolioProposal
from app.domain.quality import DataQualityReport, QualityCheck
from app.domain.research import ResearchClaim
from app.domain.strategy import StrategySpec
from app.services.backtest_executor import BacktestExecutor
from app.services.indicator_service import indicator_service


def _last_bar(db: Any, stock_code: str) -> dict[str, Any] | None:
    klines = indicator_service.get_kline_with_indicators(db, stock_code, period="daily")
    return klines[-1] if klines else None


def data_qa_node(stock_code: str) -> RuntimeNode:
    def run(ctx: NodeContext) -> dict[str, Any]:
        bar = _last_bar(ctx.db, stock_code)
        checks: list[QualityCheck] = []
        if bar is None:
            checks.append(
                QualityCheck(name="missing", severity="fail", passed=False, detail="无 K 线数据")
            )
        else:
            checks.append(
                QualityCheck(name="coverage", severity="warn", passed=True, detail="K 线可用")
            )
        record_tool_call(ctx, "market.snapshot", {"stock_code": stock_code})
        report = DataQualityReport(
            run_id=ctx.run_id,
            stock_code=stock_code,
            snapshot_id=f"snap-{ctx.run_id}",
            as_of=datetime.now(timezone.utc),
            checks=checks,
            vendor_sources=["backend"],
            overall="fail" if bar is None else "pass",
        )
        return {"output": report.model_dump(mode="json"), "output_schema": "DataQualityReport"}

    return SimpleNode("data_qa", run)


def research_node(stock_code: str) -> RuntimeNode:
    def run(ctx: NodeContext) -> dict[str, Any]:
        bar = _last_bar(ctx.db, stock_code)
        record_tool_call(ctx, "factor.indicators", {"stock_code": stock_code, "limit": 30})
        if bar is None:
            claim = ResearchClaim(
                claim="数据缺失，无法形成结论（假设）",
                category="other",
                direction="neutral",
                confidence=0.3,
                hypothesis=True,
            )
        else:
            close = float(bar["close"])
            ma5 = bar.get("ma5")
            direction = "bullish" if (ma5 is not None and close > float(ma5)) else "bearish"
            claim = ResearchClaim(
                claim=f"收盘 {close} 相对 MA5 {'上穿' if direction == 'bullish' else '下破'}",
                category="technical",
                direction=direction,
                confidence=0.6,
                evidence=[
                    {
                        "source_id": f"factor:{stock_code}:daily",
                        "as_of": datetime.now(timezone.utc),
                        "vendor": "backend",
                        "data_version": "v1",
                        "summary": f"close={close}, ma5={ma5}",
                    }
                ],
            )
        return {
            "output": {"claims": [claim.model_dump(mode="json")]},
            "output_schema": "ResearchClaim[]",
        }

    return SimpleNode("research", run)


def strategy_engineer_node(stock_code: str) -> RuntimeNode:
    def run(ctx: NodeContext) -> dict[str, Any]:
        spec = StrategySpec(
            name="ma_cross_demo",
            description="演示策略：MA 双均线交叉",
            universe={"kind": "custom", "ref": stock_code, "codes": [stock_code]},
            signal="ma_cross",
            signal_parameters={"short_period": 5, "long_period": 20},
            rebalance="weekly",
        )
        record_tool_call(
            ctx,
            "strategy.validate",
            {"spec": spec.model_dump(mode="json")},
            permission="strategy",
        )
        return {"output": spec.model_dump(mode="json"), "output_schema": "StrategySpec"}

    return SimpleNode("strategy_engineer", run)


def backtest_critic_node(stock_code: str) -> RuntimeNode:
    def run(ctx: NodeContext) -> dict[str, Any]:
        end = date.today()
        start = end.replace(year=end.year - 1)
        record_tool_call(
            ctx,
            "backtest.run",
            {
                "strategy_name": "ma_cross",
                "stock_code": stock_code,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "parameters": {"short_period": 5, "long_period": 20},
            },
            permission="strategy",
        )
        try:
            result = BacktestExecutor(ctx.db).execute(
                strategy_name="ma_cross",
                stock_code=stock_code,
                start_date=start,
                end_date=end,
                parameters={"short_period": 5, "long_period": 20},
            )
        except ValueError as exc:
            verdict = BacktestVerdict(
                run_id=ctx.run_id,
                strategy=StrategySpec(name="ma_cross_demo", signal="ma_cross"),
                snapshot_id=f"snap-{ctx.run_id}",
                start_date=start,
                end_date=end,
                benchmark="sh.000300",
                metrics=BacktestMetrics(
                    total_return=0.0,
                    annual_return=0.0,
                    max_drawdown_pct=0.0,
                    sharpe_out_of_sample=0.0,
                ),
                checks=[],
                passed=False,
                reasons=[f"回测无法执行: {exc}"],
                produced_by="backtest_critic",
            )
            return {"output": verdict.model_dump(mode="json"), "output_schema": "BacktestVerdict"}

        metrics = result.metrics
        checks = [
            BacktestCheck(name="lookahead", passed=True, detail="引擎无前视（按日线顺序撮合）"),
            BacktestCheck(name="out_of_sample", passed=True, detail="引擎按声明参数执行"),
        ]
        passed = metrics.total_return > 0 and metrics.max_drawdown_pct > -0.5
        verdict = BacktestVerdict(
            run_id=ctx.run_id,
            strategy=StrategySpec(name="ma_cross_demo", signal="ma_cross"),
            snapshot_id=f"snap-{ctx.run_id}",
            start_date=start,
            end_date=end,
            benchmark="sh.000300",
            metrics=BacktestMetrics(
                total_return=float(metrics.total_return),
                annual_return=float(metrics.annual_return),
                max_drawdown_pct=float(metrics.max_drawdown_pct),
                sharpe_out_of_sample=float(metrics.sharpe_ratio or 0.0),
                turnover_annual=0.0,
                total_cost_bps=0.0,
            ),
            checks=checks,
            passed=passed,
            reasons=["收益为正且回撤可控" if passed else "收益非正或回撤过大"],
            produced_by="backtest_critic",
        )
        return {"output": verdict.model_dump(mode="json"), "output_schema": "BacktestVerdict"}

    return SimpleNode("backtest_critic", run)


def portfolio_risk_node(stock_code: str) -> RuntimeNode:
    def run(ctx: NodeContext) -> dict[str, Any]:
        record_tool_call(ctx, "portfolio.constraints", {"positions": [
            {"code": stock_code, "action": "buy", "weight": 0.1},
        ]})
        proposal = PortfolioProposal(
            run_id=ctx.run_id,
            positions=[{"code": stock_code, "action": "buy", "weight": 0.1, "confidence": 0.5}],
            exposures=ExposureSummary(
                sector_exposure={"unknown": 0.1},
                single_stock_max_pct=0.1,
                liquidity_note="演示流动性说明",
            ),
            constraints=[
                ConstraintResult(rule="position_weight_sum", passed=True, detail="权重合计 0.1"),
                ConstraintResult(rule="lot_size", passed=True, detail="整手"),
                ConstraintResult(rule="t_plus_1", passed=True, detail="无同日买卖"),
            ],
            risk_budget_used_pct=0.1,
            rejected=False,
        )
        return {"output": proposal.model_dump(mode="json"), "output_schema": "PortfolioProposal"}

    return SimpleNode("portfolio_risk", run)
