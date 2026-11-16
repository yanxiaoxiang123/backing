"""Evidence-based portfolio sizing; evaluation never creates or approves an order."""

from datetime import datetime
from math import floor

from app.domain.portfolio import ConstraintResult, ExposureSummary, PortfolioProposal, PositionAllocation
from app.domain.risk import (
    PortfolioRiskRequest, RiskAccountEvidence, RiskMarketEvidence, RiskOrder,
)
from app.services.backtest_simulation import ExecutionCosts
from app.services.market_data import digest, naive_utc


def evaluate_portfolio_risk(request: PortfolioRiskRequest, account: RiskAccountEvidence,
                             market: dict[str, RiskMarketEvidence], *,
                             run_id: str, as_of: datetime,
                             costs: ExecutionCosts | None = None,
                             fixed_order: RiskOrder | None = None) -> dict:
    costs = costs or ExecutionCosts()
    constraints: list[ConstraintResult] = []

    def check(rule: str, passed: bool, detail: str):
        constraints.append(ConstraintResult(rule=rule, passed=passed, detail=detail))

    required = (set(account.positions) | {target.stock_code for target in request.targets}
                | set(account.pending_codes) | set(account.pending_buys))
    check("market_coverage", required <= set(market), "所有现有持仓与目标证券必须有行情证据")
    age = (naive_utc(as_of) - naive_utc(account.observed_at)).total_seconds()
    check("account_freshness", 0 <= age <= 300, "账户快照须在评估前五分钟内观测")
    check("kill_switch", not account.kill_switch, "账户停止交易开关关闭")
    check("cash_reservations", account.reserved_cash <= account.cash, "在途委托冻结现金不得超过账面现金")
    for code in sorted(required & set(market)):
        quote = market[code]
        check(f"price_evidence:{code}", quote.stock_code == code and quote.raw and quote.session == quote.expected_session,
              "使用最近已完成交易日的原始价格和成交量")
        check(f"listed:{code}", quote.listed, "证券须处于已核验的上市区间")
    equity = account.cash + sum(position.quantity * market[code].price
                                for code, position in account.positions.items() if code in market)
    check("positive_equity", equity > 0, "组合权益必须为正")
    targets = {target.stock_code: target for target in request.targets}
    quantities = {code: position.quantity for code, position in account.positions.items()}
    orders: list[RiskOrder] = []
    # Do not fund buys from sell orders that have not executed.
    cash_budget = max(0, account.cash - account.reserved_cash - equity * request.limits.minimum_cash_weight)
    if required <= set(market) and equity > 0 and fixed_order is None:
        for code, target in sorted(targets.items()):
            quote = market[code]
            held = account.positions.get(code)
            owned = held.quantity if held else 0
            check(f"single_target:{code}", target.target_weight <= request.limits.max_single_weight + 1e-9,
                  "目标单票权重不得超过集中度上限")
            desired = floor(equity * target.target_weight / quote.price / costs.lot_size) * costs.lot_size
            delta = desired - owned
            if delta == 0:
                continue
            check(f"pending_order:{code}", code not in account.pending_codes, "同票在途委托须先核对或撤销")
            check(f"tradable:{code}", not quote.suspended and not quote.locked and quote.volume > 0,
                  "已停牌、封板或无成交量时不生成委托")
            capacity = floor(quote.volume * request.limits.max_participation / costs.lot_size) * costs.lot_size
            if delta > 0:
                check(f"stop_evidence:{code}", target.stop_loss_pct is not None, "加仓须提供明确止损距离")
                if target.stop_loss_pct is None:
                    continue
                reference = round(quote.price * (1 + costs.slippage_rate), 4)
                risk_cap = floor(equity * request.limits.max_position_loss / target.stop_loss_pct
                                 / reference / costs.lot_size) * costs.lot_size
                risk_capacity = max(0, risk_cap - owned)
                cash_capacity = floor(cash_budget / reference / costs.lot_size) * costs.lot_size
                quantity = min(delta, capacity, risk_capacity, cash_capacity)
                def fits(quantity):
                    estimated = costs.fees("buy", quantity * reference)
                    paid_costs = sum(order.estimated_fees + abs(order.reference_price - market[order.stock_code].price)
                                     * order.quantity for order in orders)
                    remaining_equity = equity - paid_costs - estimated - quantity * (reference - quote.price)
                    value = (owned + quantity) * quote.price
                    return (quantity * reference + estimated <= cash_budget
                            and value <= remaining_equity * request.limits.max_single_weight + 1e-9
                            and value * target.stop_loss_pct <= remaining_equity * request.limits.max_position_loss + 1e-9)

                while quantity > 0 and not fits(quantity):
                    quantity -= costs.lot_size
                check(f"minimum_buy:{code}", quantity > 0, "现金、止损预算及流动性须至少支持一手")
                if quantity <= 0:
                    continue
                fees = costs.fees("buy", quantity * reference)
                cash_budget -= quantity * reference + fees
                quantities[code] = owned + quantity
                reasons = ["目标权重", "账户可用现金", "单票止损预算", "前一已完成日成交量容量"]
                if quantity < delta:
                    reasons.append("已按风险容量缩减委托量")
                orders.append(RiskOrder(stock_code=code, side="buy", quantity=quantity,
                                         reference_price=reference, estimated_fees=fees, sizing_reasons=reasons))
            else:
                needed = -delta
                available = held.available_to_sell if held else 0
                quantity = min(needed, available, capacity)
                # A complete liquidation may include an odd-lot residual.
                if not (desired == 0 and quantity == owned):
                    quantity = quantity // costs.lot_size * costs.lot_size
                check(f"t_plus_one:{code}", quantity > 0, "仅可卖出账户中已可用的股份")
                if quantity <= 0:
                    continue
                reference = round(quote.price * (1 - costs.slippage_rate), 4)
                fees = costs.fees("sell", quantity * reference)
                quantities[code] = owned - quantity
                orders.append(RiskOrder(stock_code=code, side="sell", quantity=quantity,
                                         reference_price=reference, estimated_fees=fees,
                                         sizing_reasons=["目标仓位差额", "T+1 可用股份", "前一日成交量容量"]))
    if fixed_order is not None and required <= set(market) and equity > 0:
        code = fixed_order.stock_code
        target = targets.get(code)
        quote = market.get(code)
        check("explicit_order_target", target is not None and quote is not None, "委托须对应已确认目标证券")
        if target is not None and quote is not None:
            held = account.positions.get(code)
            owned = held.quantity if held else 0
            check(f"single_target:{code}", target.target_weight <= request.limits.max_single_weight + 1e-9,
                  "目标单票权重不得超过集中度上限")
            check(f"pending_order:{code}", code not in account.pending_codes, "同票在途委托须先核对或撤销")
            check(f"tradable:{code}", not quote.suspended and not quote.locked and quote.volume > 0,
                  "停牌、封板或无成交量时禁止委托")
            capacity = floor(quote.volume * request.limits.max_participation / costs.lot_size) * costs.lot_size
            check("order_liquidity", fixed_order.quantity <= capacity, "委托数量不得超过前一已完成日成交量容量")
            desired = floor(equity * target.target_weight / quote.price / costs.lot_size) * costs.lot_size
            if fixed_order.side == "buy":
                check("order_lot", fixed_order.quantity % costs.lot_size == 0, "买入数量须符合申报单位")
                check("order_target_quantity", owned + fixed_order.quantity <= desired, "买入后不得超过明确目标数量")
                quantities[code] = owned + fixed_order.quantity
                check("order_cash", fixed_order.quantity * fixed_order.reference_price + fixed_order.estimated_fees <= cash_budget,
                      "冻结其他委托资金及现金缓冲后不得透支")
            else:
                available = held.available_to_sell if held else 0
                check("order_t_plus_one", fixed_order.quantity <= available, "委托不得超过 T+1 可卖数量")
                check("order_target_quantity", fixed_order.quantity <= max(0, owned - desired), "卖出不得超出明确减仓目标")
                check("order_lot", fixed_order.quantity % costs.lot_size == 0 or fixed_order.quantity == owned,
                      "零股须一次性清仓")
                quantities[code] = max(0, owned - fixed_order.quantity)
            orders.append(fixed_order)
    for code, quantity in account.pending_buys.items():
        quantities[code] = quantities.get(code, 0) + quantity
    values = {code: quantity * market[code].price for code, quantity in quantities.items() if code in market}
    fees = sum(order.estimated_fees for order in orders)
    projected_cash = account.cash - account.reserved_cash - sum(order.quantity * order.reference_price + order.estimated_fees
                                       for order in orders if order.side == "buy")
    projected_cash += sum(order.quantity * order.reference_price - order.estimated_fees
                          for order in orders if order.side == "sell")
    projected_equity = projected_cash + sum(values.values())
    denominator = max(projected_equity, 1e-9)
    check("projected_equity", projected_equity > 0 and projected_cash >= 0,
          "费用与滑点后权益须为正且现金不得透支")
    weights = {code: value / denominator for code, value in values.items()}
    check("gross_exposure", sum(weights.values()) <= request.limits.max_gross_weight + 1e-9,
          "成交后总持仓须在组合仓位上限内")
    check("single_exposure", max(weights.values(), default=0) <= request.limits.max_single_weight + 1e-9,
          "成交后单票持仓须在集中度上限内（含现有仓位）")
    check("cash_buffer", projected_cash >= projected_equity * request.limits.minimum_cash_weight - 1e-6,
          "预留在途委托资金及最低现金缓冲")
    sectors = {}
    risk = 0.0
    for code, weight in weights.items():
        if weight <= 0:
            continue
        target = targets.get(code)
        stop = target.stop_loss_pct if target else None
        check(f"portfolio_stop:{code}", stop is not None, "全部保留持仓均须有明确的止损风险假设")
        if stop is not None:
            risk += weight * stop
            check(f"position_loss:{code}", weight * stop <= request.limits.max_position_loss + 1e-9,
                  "成交后单票止损损失须在风险预算内")
        sector = market[code].sector
        if request.limits.max_sector_weight is not None:
            check(f"sector_evidence:{code}", sector is not None, "启用行业限制时必须有可核验分类")
        if sector:
            sectors[sector] = sectors.get(sector, 0) + weight
    check("portfolio_loss", risk <= request.limits.max_portfolio_loss + 1e-9, "组合止损损失不超过总预算")
    if request.limits.max_sector_weight is not None:
        check("sector_exposure", max(sectors.values(), default=0) <= request.limits.max_sector_weight + 1e-9,
              "成交后行业暴露不超过上限")
    failures = [row.detail + " (" + row.rule + ")" for row in constraints if not row.passed]
    order_by_code = {order.stock_code: order for order in orders}
    positions = []
    for code in sorted(weights):
        order = order_by_code.get(code)
        action = ("buy" if order.side == "buy" else "sell" if quantities[code] == 0 else "reduce") if order else "hold"
        positions.append(PositionAllocation(code=code, action=action, weight=min(1, max(0, weights[code])),
                                             confidence=0, reason=targets[code].reason if code in targets else "保留现有持仓"))
    proposal = PortfolioProposal(run_id=run_id, positions=[] if failures else positions,
                                 exposures=ExposureSummary(sector_exposure=sectors,
                                                           single_stock_max_pct=min(1, max(weights.values(), default=0)),
                                                           liquidity_note="容量基于已完成日成交量；实际成交前须重验价格与交易状态"),
                                 constraints=constraints, risk_budget_used_pct=min(1, risk / request.limits.max_portfolio_loss),
                                 rejected=bool(failures), rejection_reasons=failures)
    evidence = {"account": account.model_dump(mode="json"),
                "market": {code: quote.model_dump(mode="json") for code, quote in sorted(market.items())},
                "request": request.model_dump(mode="json"), "costs": costs.__dict__}
    if fixed_order is not None:
        evidence["fixed_order"] = fixed_order.model_dump(mode="json")
    return {"engine_version": "portfolio-risk-v1", "run_id": run_id, "as_of": as_of.isoformat(),
            "proposal": proposal.model_dump(mode="json"),
            "orders": [] if failures else [order.model_dump() for order in orders],
            "account_id": account.account_id, "equity": round(equity, 4),
            "projected_cash": round(projected_cash, 4), "estimated_fees": round(fees, 4),
            "projected_weights": weights, "projected_stop_loss_pct": risk,
            "evidence": evidence, "evidence_sha256": digest(evidence),
            "limitations": ["reference_prices_are_not_fill_guarantees", "stop_losses_can_gap",
                            "sector_limit_disabled" if request.limits.max_sector_weight is None else "verified_sector_required"]}
