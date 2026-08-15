"""预算检查（规格决策 1；US-1.3：超预算自动终止并给出明确失败原因）。"""

from dataclasses import dataclass

from app.domain.plans import RunBudget


@dataclass(frozen=True)
class BudgetState:
    """预算消耗快照。"""

    attempts: int = 0  # 已尝试执行的轮次（含重试）
    tool_calls: int = 0
    tokens_used: int = 0
    elapsed_s: float = 0.0


def check_budget(budget: RunBudget, state: BudgetState) -> tuple[bool, str | None]:
    """返回 (ok, reason)；超限时 reason 形如 ``budget:max_rounds``。"""
    if state.attempts > budget.max_rounds:
        return False, f"budget:max_rounds（尝试 {state.attempts} 轮，上限 {budget.max_rounds}）"
    if state.tool_calls > budget.max_tool_calls:
        return False, f"budget:max_tool_calls（调用 {state.tool_calls} 次，上限 {budget.max_tool_calls}）"
    if state.tokens_used > budget.max_tokens:
        return False, f"budget:max_tokens（消耗 {state.tokens_used}，上限 {budget.max_tokens}）"
    if state.elapsed_s > budget.timeout_s:
        return False, f"budget:timeout（耗时 {state.elapsed_s:.1f}s，上限 {budget.timeout_s}s）"
    return True, None
