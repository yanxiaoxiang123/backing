"""P2 验收演示（任务 12）：自然语言目标 → RunPlan → 专家执行 → 确定性回测 → 通过/拒绝及原因。

进程内运行（无需后端进程）；使用开发库 stock_backtest.db。
"""

import sys

from app.agent_runtime.graphs import build_supervisor_pipeline
from app.agent_runtime.runtime import RunExecutor
from app.agent_runtime.stores import create_stores
from app.config import SessionLocal
from app.domain.backtest import BacktestVerdict
from app.domain.plans import RunBudget


def run_demo(objective: str) -> int:
    session = SessionLocal()
    try:
        stores = create_stores(session)
        budget = RunBudget(max_rounds=12, max_tool_calls=40)
        executor = RunExecutor(stores, db=session)
        run_id = executor.create_run(objective=objective, budget=budget)
        pipeline = build_supervisor_pipeline(objective, budget)
        final = executor.execute(run_id, pipeline)

        steps = {s["node"]: s for s in stores.steps.list_steps(run_id)}
        print(f"run_id: {run_id}")
        print(f"状态:   {final['status']}")

        plan = steps.get("supervisor")
        if plan and plan.get("output_json"):
            print("\n[RunPlan]")
            for step in plan["output_json"]["steps"]:
                print(f"  {step['order']}. {step['node']}: {step['description']}")

        verdict_step = steps.get("backtest_critic")
        if verdict_step and verdict_step.get("output_json"):
            verdict = BacktestVerdict.model_validate(verdict_step["output_json"])
            print("\n[回测审计]")
            print(f"  结论: {'通过' if verdict.passed else '拒绝'}")
            for reason in verdict.reasons:
                print(f"  原因: {reason}")
            m = verdict.metrics
            print(
                f"  指标: 总收益 {m.total_return:.2%} 年化 {m.annual_return:.2%} "
                f"最大回撤 {m.max_drawdown_pct:.2%} 样本外Sharpe {m.sharpe_out_of_sample:.2f}"
            )
        else:
            print("\n[回测审计] 目标未触发 backtest_critic（需包含'策略/回测'关键词）")

        return 0
    finally:
        session.close()


if __name__ == "__main__":
    objective = (
        " ".join(sys.argv[1:])
        or "生成 ma_cross 策略并回测验证 sh.600000"
    )
    raise SystemExit(run_demo(objective))
