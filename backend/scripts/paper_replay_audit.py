"""模拟盘重放审计工具（切片 12；US-3.5）。

从 append-only 事件（资金流水 + 成交）重建账户，与当前物化状态比对；
并回放每个订单的生命周期事件链。通过即输出 PASS。

用法（在 backend/ 下）：
    python scripts/paper_replay_audit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ 入路径

from app.agent_runtime.paper import service as paper_service
from app.agent_runtime.paper.replay import replay_account
from app.config import SessionLocal
from app.models.paper_trading import PaperCashEvent, PaperFill, PaperOrder, PaperOrderEvent


def main() -> int:
    db = SessionLocal()
    try:
        fills = db.query(PaperFill, PaperOrder).join(
            PaperOrder, PaperOrder.order_id == PaperFill.order_id
        ).all()
        cash_events = db.query(PaperCashEvent).order_by(PaperCashEvent.seq.asc()).all()
        order_events = db.query(PaperOrderEvent).order_by(PaperOrderEvent.id.asc()).all()

        print(f"事件统计: 订单事件 {len(order_events)}, 成交 {len(fills)}, 资金事件 {len(cash_events)}")

        # 1) 账户重放一致性
        state = paper_service.account_state(db)
        replayed = replay_account(
            initial_cash=paper_service.DEFAULT_INITIAL_CASH,
            cash_events=[
                {"event_type": e.event_type, "amount": e.amount} for e in cash_events
            ],
            fills=[
                {
                    "stock_code": o.stock_code,
                    "side": o.side,
                    "price": f.price,
                    "quantity": f.quantity,
                }
                for f, o in fills
            ],
        )
        cash_ok = abs(state["cash"] - replayed["cash"]) < 1e-3
        positions_ok = {
            (p["stock_code"], round(p["quantity"], 4))
            for p in state["positions"]
        } == {
            (code, round(pos["quantity"], 4))
            for code, pos in replayed["positions"].items()
        }
        print(f"现金一致: {cash_ok} ({state['cash']} vs {replayed['cash']})")
        print(f"持仓一致: {positions_ok}")

        # 2) 订单生命周期链：proposed → … → 终态/在途，seq 连续
        #    终态：filled/rejected/expired/cancelled；在途：proposed（待审批）。
        chains: dict[str, list[str]] = {}
        for e in order_events:
            chains.setdefault(e.order_id, []).append(e.event_type)
        TERMINAL = ("filled", "rejected", "expired", "cancelled")
        broken = [
            (oid, chain)
            for oid, chain in chains.items()
            if chain[0] != "proposed"
            or (chain[-1] not in TERMINAL and chain[-1] != "proposed")
        ]
        for oid, chain in chains.items():
            print(f"  {oid}: {' → '.join(chain)}")
        lifecycle_ok = not broken
        print(f"生命周期链完整: {lifecycle_ok}" + (f" 异常: {broken}" if broken else ""))

        all_ok = cash_ok and positions_ok and lifecycle_ok
        print("\n重放审计:", "PASS ✓" if all_ok else "FAIL ✗")
        return 0 if all_ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
