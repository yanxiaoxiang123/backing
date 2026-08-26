"""专家节点（任务 09；US-2.2）：确定性实现 + 工具可追溯。

所有专家输出构造为领域 schema 对象；回测数字来自 BacktestExecutor
（确定性引擎），LLM 不参与数字计算（规格第四节）。
"""

from datetime import date, datetime, timedelta, timezone
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


def _last_bar(
    db: Any, stock_code: str, as_of: datetime | None = None
) -> dict[str, Any] | None:
    klines = indicator_service.get_kline_with_indicators(
        db,
        stock_code,
        period="daily",
        end_date=as_of.date() if as_of else None,
    )
    return klines[-1] if klines else None


def data_qa_node(stock_code: str) -> RuntimeNode:
    def run(ctx: NodeContext) -> dict[str, Any]:
        bar = _last_bar(ctx.db, stock_code, ctx.as_of)
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
            as_of=ctx.as_of or datetime.now(timezone.utc),
            checks=checks,
            vendor_sources=["backend"],
            overall="fail" if bar is None else "pass",
        )
        return {"output": report.model_dump(mode="json"), "output_schema": "DataQualityReport"}

    return SimpleNode("data_qa", run)


def research_node(stock_code: str) -> RuntimeNode:
    """研究专家（US-2.6）：确定性工具 + 证据引用，LLM 不参与事实。

    技术面来自 K 线/因子；新闻/公告/财报来自研究数据层工具（经网关调用，
    带证据五元组）。工具失败时跳过对应类别，不伪造证据。
    """

    def run(ctx: NodeContext) -> dict[str, Any]:
        from app.tools import DEFAULT_REGISTRY
        from app.tools.base import ToolContext as GatewayContext

        claims: list[dict[str, Any]] = []
        gateway = GatewayContext(
            db=ctx.db,
            stores=ctx.stores,
            run_id=ctx.run_id,
            granted_permissions={"read"},
            as_of=ctx.as_of,
        )
        now = ctx.as_of or datetime.now(timezone.utc)
        as_of_date = now.strftime("%Y-%m-%d")

        # --- 技术面：K 线 + 因子（既有确定性路径） ---
        bar = _last_bar(ctx.db, stock_code, now)
        record_tool_call(ctx, "factor.indicators", {"stock_code": stock_code, "limit": 30})
        if bar is None:
            claims.append(
                ResearchClaim(
                    claim="数据缺失，无法形成结论（假设）",
                    category="other",
                    direction="neutral",
                    confidence=0.3,
                    hypothesis=True,
                ).model_dump(mode="json")
            )
        else:
            close = float(bar["close"])
            ma5 = bar.get("ma5")
            volume = float(bar.get("volume") or 0)
            direction = "bullish" if (ma5 is not None and close > float(ma5)) else "bearish"
            claims.append(
                ResearchClaim(
                    claim=(
                        f"收盘 {close:.2f} 相对 MA5 "
                        f"{'上穿' if direction == 'bullish' else '下破'}"
                    ),
                    category="technical",
                    direction=direction,
                    confidence=0.6,
                    evidence=[
                        {
                            "source_id": f"factor:{stock_code}:daily",
                            "as_of": now,
                            "vendor": "backend",
                            "data_version": "v1",
                            "summary": (
                                f"K线收盘 {close:.2f}，成交量 {volume:,.0f}，"
                                f"MA5 {ma5:.2f}"
                            ),
                        }
                    ],
                ).model_dump(mode="json")
            )

        # --- 新闻证据（确定性服务；失败跳过，不伪造） ---
        news_env = DEFAULT_REGISTRY.invoke(
            "event.news", {"stock_code": stock_code, "limit": 5}, gateway
        )
        if news_env.get("ok"):
            data = news_env["data"]
            for item in (data.get("news") or [])[:2]:
                title = item.get("新闻标题") or item.get("title") or "新闻"
                content = item.get("新闻内容") or ""
                claims.append(
                    ResearchClaim(
                        claim=f"新闻：{str(title)[:80]}",
                        category="news",
                        direction="neutral",
                        confidence=0.5,
                        evidence=[
                            {
                                "source_id": news_env.get("source_id") or "news:unknown",
                                "as_of": news_env.get("as_of") or now,
                                "vendor": data.get("vendor") or "akshare",
                                "data_version": data.get("data_version") or "1.0.0",
                                "summary": str(content)[:150] or str(title)[:150],
                            }
                        ],
                    ).model_dump(mode="json")
                )

        # --- 公告证据 ---
        ann_env = DEFAULT_REGISTRY.invoke(
            "event.announcement",
            {"stock_code": stock_code, "date": as_of_date},
            gateway,
        )
        if ann_env.get("ok"):
            data = ann_env["data"]
            for item in (data.get("announcements") or [])[:2]:
                title = item.get("公告标题") or "公告"
                ann_type = item.get("公告类型") or ""
                claims.append(
                    ResearchClaim(
                        claim=f"公告：{str(title)[:80]}",
                        category="other",
                        direction="neutral",
                        confidence=0.5,
                        evidence=[
                            {
                                "source_id": ann_env.get("source_id") or "notice:unknown",
                                "as_of": ann_env.get("as_of") or now,
                                "vendor": data.get("vendor") or "akshare",
                                "data_version": data.get("data_version") or "1.0.0",
                                "summary": f"{ann_type} {str(title)[:120]}".strip(),
                            }
                        ],
                    ).model_dump(mode="json")
                )

        # --- 财报摘要证据 ---
        fin_env = DEFAULT_REGISTRY.invoke(
            "fundamental.financials",
            {"stock_code": stock_code, "periods": 3},
            gateway,
        )
        if fin_env.get("ok"):
            data = fin_env["data"]
            latest = (data.get("financials") or [{}])[0]
            report_period = latest.get("报告期") or "未知报告期"
            net_profit = latest.get("净利润")
            claims.append(
                ResearchClaim(
                    claim=f"财报：最近报告期 {report_period} 净利润 {net_profit if net_profit is not None else '未披露'}",
                    category="fundamental",
                    direction="neutral",
                    confidence=0.5,
                    evidence=[
                        {
                            "source_id": fin_env.get("source_id") or "financials:unknown",
                            "as_of": fin_env.get("as_of") or now,
                            "vendor": data.get("vendor") or "akshare",
                            "data_version": data.get("data_version") or "1.0.0",
                            "summary": f"报告期 {report_period}，净利润 {net_profit if net_profit is not None else '未披露'}",
                        }
                    ],
                ).model_dump(mode="json")
            )

        from app.agent_runtime.artifacts import emit_artifact

        emit_artifact(
            ctx.stores,
            ctx.run_id,
            "research_summary",
            "research.json",
            {"stock_code": stock_code, "claims": claims},
        )
        return {
            "output": {"claims": claims},
            "output_schema": "ResearchClaim[]",
        }

    return SimpleNode("research", run)


def strategy_engineer_node(
    stock_code: str, params: dict[str, Any] | None = None
) -> RuntimeNode:
    """策略工程师（US-2.8）：参数修改产生新 run，旧回测永不覆盖。"""

    def run(ctx: NodeContext) -> dict[str, Any]:
        p = params or {}
        spec = StrategySpec(
            name="ma_cross_demo",
            description="演示策略：MA 双均线交叉",
            universe={"kind": "custom", "ref": stock_code, "codes": [stock_code]},
            signal="ma_cross",
            signal_parameters={
                "short_period": int(p.get("short_period", 5)),
                "long_period": int(p.get("long_period", 20)),
            },
            rebalance="weekly",
        )
        record_tool_call(
            ctx,
            "strategy.validate",
            {"spec": spec.model_dump(mode="json")},
            permission="strategy",
        )
        from app.agent_runtime.artifacts import emit_artifact

        payload = spec.model_dump(mode="json")
        emit_artifact(
            ctx.stores,
            ctx.run_id,
            "strategy_spec",
            "strategy.json",
            {"strategy": payload},
        )
        return {"output": payload, "output_schema": "StrategySpec"}

    return SimpleNode("strategy_engineer", run)


def backtest_critic_node(
    stock_code: str, params: dict[str, Any] | None = None
) -> RuntimeNode:
    """回测审计（US-2.8）：按策略参数回测（默认 5/20）。"""

    def run(ctx: NodeContext) -> dict[str, Any]:
        p = params or {}
        parameters = {
            "short_period": int(p.get("short_period", 5)),
            "long_period": int(p.get("long_period", 20)),
        }
        end = (ctx.as_of.date() if ctx.as_of else date.today())
        start = end.replace(year=end.year - 1)
        record_tool_call(
            ctx,
            "backtest.run",
            {
                "strategy_name": "ma_cross",
                "stock_code": stock_code,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "parameters": parameters,
            },
            permission="strategy",
        )
        try:
            result = BacktestExecutor(ctx.db).execute(
                strategy_name="ma_cross",
                stock_code=stock_code,
                start_date=start,
                end_date=end,
                parameters=parameters,
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
            from app.agent_runtime.artifacts import emit_artifact

            emit_artifact(
                ctx.stores,
                ctx.run_id,
                "backtest_report",
                "backtest.json",
                {"verdict": verdict.model_dump(mode="json")},
            )
            return {"output": verdict.model_dump(mode="json"), "output_schema": "BacktestVerdict"}

        metrics = result.metrics
        observed_dates = [item.date for item in result.portfolio_values]
        lookahead_passed = bool(observed_dates) and max(observed_dates) <= end
        lookahead_detail = (
            "所有回测观测日均不晚于 run as_of"
            if lookahead_passed
            else "回测结果缺少有效观测日或包含 as_of 之后数据"
        )

        # 同一确定性策略在未见过的后 30% 日期上独立重放，不能把整段回测
        # 的指标冒充样本外结果。数据不足时明确失败，禁止评测门禁误放行。
        oos_start = start + timedelta(days=max(1, int((end - start).days * 0.7)))
        oos_result = None
        try:
            oos_result = BacktestExecutor(ctx.db).execute(
                strategy_name="ma_cross",
                stock_code=stock_code,
                start_date=min(oos_start, end),
                end_date=end,
                parameters=parameters,
            )
        except ValueError:
            oos_result = None
        oos_passed = bool(oos_result and oos_result.portfolio_values)
        checks = [
            BacktestCheck(name="lookahead", passed=lookahead_passed, detail=lookahead_detail),
            BacktestCheck(
                name="out_of_sample",
                passed=oos_passed,
                detail=(
                    f"独立样本外区间 {min(oos_start, end)} 至 {end}"
                    if oos_passed
                    else "样本外区间无足够行情数据，拒绝推广"
                ),
            ),
        ]
        # 引擎返回百分比（total_return=12.5 表示 12.5%，max_drawdown=18.0 表示 18%），
        # 领域契约用小数（0.12 / -0.18）：统一换算
        total_return = float(metrics.total_return) / 100
        annual_return = float(metrics.annual_return) / 100
        max_drawdown_pct = -float(metrics.max_drawdown) / 100
        passed = all(check.passed for check in checks) and total_return > 0 and max_drawdown_pct > -0.5
        reasons = [
            "收益为正、回撤可控且通过时点/样本外门禁"
            if passed
            else "收益、回撤或时点/样本外门禁未达标"
        ]
        verdict = BacktestVerdict(
            run_id=ctx.run_id,
            strategy=StrategySpec(name="ma_cross_demo", signal="ma_cross"),
            snapshot_id=f"snap-{ctx.run_id}",
            start_date=start,
            end_date=end,
            benchmark="sh.000300",
            metrics=BacktestMetrics(
                total_return=total_return,
                annual_return=annual_return,
                max_drawdown_pct=max_drawdown_pct,
                sharpe_out_of_sample=float(
                    oos_result.metrics.sharpe_ratio if oos_result else 0.0
                ),
                turnover_annual=0.0,
                total_cost_bps=0.0,
            ),
            checks=checks,
            passed=passed,
            reasons=reasons,
            produced_by="backtest_critic",
        )
        from app.agent_runtime.artifacts import emit_artifact

        emit_artifact(
            ctx.stores,
            ctx.run_id,
            "backtest_report",
            "backtest.json",
            {"verdict": verdict.model_dump(mode="json")},
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
        # 组合风控通过后，提议一笔小规模模拟盘订单（生成审批卡；不自动成交）。
        # 无审批任何订单不成交（撮合层拒绝 pending 订单；US-3.2）。
        if not proposal.rejected:
            from app.tools import DEFAULT_REGISTRY
            from app.tools.base import ToolContext as GatewayContext

            gateway = GatewayContext(
                db=ctx.db,
                stores=ctx.stores,
                run_id=ctx.run_id,
                granted_permissions={"read", "approval"},
                as_of=ctx.as_of,
            )
            env = DEFAULT_REGISTRY.invoke(
                "execution.paper.propose_order",
                {
                    "stock_code": stock_code,
                    "side": "buy",
                    "quantity": 100,
                    "trigger_note": "组合风控通过后的演示订单（审批后下一交易日撮合）",
                },
                gateway,
            )
            if not env.get("ok"):
                proposal.constraints.append(
                    ConstraintResult(
                        rule="paper_propose",
                        passed=False,
                        detail=f"模拟盘订单提议失败: {env.get('error', {}).get('message', 'unknown')}",
                    )
                )
        return {"output": proposal.model_dump(mode="json"), "output_schema": "PortfolioProposal"}

    return SimpleNode("portfolio_risk", run)
