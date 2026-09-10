"""运行时评测（任务 12）：golden cases 走新运行时并确定性打分。

- 每个 case：以 ``data_available_at`` 注入 ``as_of``（避免前视）创建 run，
  经 Supervisor 动态路由执行，产出 claims/tool_calls 后用既有评分器打分
- 附加指标：plan_completion（节点完成率）、token 用量、P95 耗时
- 完全确定性（无 LLM、无网络），两次运行分数一致
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.agent_runtime.graphs import build_supervisor_pipeline
from app.agent_runtime.runtime import RunExecutor
from app.agent_runtime.stores import Stores, create_stores
from app.domain.plans import RunBudget
from app.domain.stock_codes import (
    canonicalize_stock_code_in_text,
    normalize_stock_code,
    stock_code_from_text,
)
from evals.runner import DEFAULT_DATASET, load_cases
from evals.scorers import (
    citation_coverage,
    lookahead_check,
    schema_validity_score,
    trading_rules_check,
)

SessionFactory = Callable[[], Any]


def _result_from_run(stores: Stores, run_id: str) -> dict[str, Any]:
    steps = {s["node"]: s for s in stores.steps.list_steps(run_id)}
    claims: list[dict] = []
    research = steps.get("research")
    if research and research.get("output_json"):
        claims = research["output_json"].get("claims") or []
    tool_calls = [
        {"tool_name": c["tool_name"], "result_ref": c.get("result_ref")}
        for c in stores.tool_calls.list_tool_calls(run_id)
    ]
    return {"claims": claims, "tool_calls": tool_calls, "orders": [], "positions": []}


def _parse_available_at(case: dict[str, Any]) -> datetime | None:
    raw = case.get("data_available_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _stock_code_of(case: dict[str, Any]) -> str:
    from app.agent_runtime.graphs.supervisor import extract_stock_code

    if case.get("stock_code"):
        return normalize_stock_code(case["stock_code"])
    return extract_stock_code(case.get("objective", ""))


_FIXTURE_FILE = Path(__file__).parent / "datasets" / "v1" / "research_fixtures.json"


def _load_research_fixtures() -> dict[str, dict[str, dict[str, Any]]]:
    """case_id → {tool: entry}。研究数据层夹具，保证评测确定性（无网络）。"""
    if not _FIXTURE_FILE.exists():
        return {}
    return json.loads(_FIXTURE_FILE.read_text(encoding="utf-8"))


RESEARCH_FIXTURES = _load_research_fixtures()


def _apply_case_fixtures(case: dict[str, Any]) -> None:
    """为该 case 注册研究数据夹具（as_of 统一为 data_available_at）。

    未显式配置的工具也注册"空数据"默认夹具，保证评测全程无网络、
    确定性可回放。
    """
    from app.services import research_data

    fixtures = dict(RESEARCH_FIXTURES.get(case["id"]) or {})
    available_at = _parse_available_at(case)
    stock = _stock_code_of(case)

    empty: dict[str, dict[str, Any]] = {
        "event.news": {
            "payload": {"stock_code": stock, "rows": 0, "news": []},
            "source_id": "news:none",
            "as_of": "",
            "vendor": "akshare",
            "data_version": "1.0.0",
        },
        "event.announcement": {
            "payload": {"stock_code": stock, "rows": 0, "announcements": []},
            "source_id": "notice:none",
            "as_of": "",
            "vendor": "akshare",
            "data_version": "1.0.0",
        },
        "fundamental.financials": {
            "payload": {"stock_code": stock, "rows": 0, "financials": []},
            "source_id": "financials:none",
            "as_of": "",
            "vendor": "akshare",
            "data_version": "1.0.0",
        },
    }
    for tool, value in empty.items():
        fixtures.setdefault(tool, value)

    def provider(params: dict[str, Any], entry: dict[str, Any], at: Any) -> dict[str, Any]:
        result = dict(entry)
        if at is not None:
            result["as_of"] = at.isoformat()
        return result

    for tool, entry in fixtures.items():
        research_data.set_fixture(tool, lambda p, e=entry, a=available_at: provider(p, e, a))


def _clear_case_fixtures() -> None:
    from app.services import research_data

    research_data.clear_fixtures()


def evaluate_case_through_runtime(
    case: dict[str, Any], session: Any, *, budget: RunBudget | None = None
) -> dict[str, Any]:
    """在运行时上执行单个 golden case 并打分。"""
    stores = create_stores(session)
    objective = canonicalize_stock_code_in_text(case.get("objective", ""))
    if stock_code_from_text(objective) is None and case.get("stock_code"):
        objective = f"{objective}（股票：{case['stock_code']}）"
    budget = budget or RunBudget(max_rounds=12, max_tool_calls=40)
    executor = RunExecutor(stores, db=session, as_of=_parse_available_at(case))
    run_id = executor.create_run(objective=objective, budget=budget)
    pipeline = build_supervisor_pipeline(objective, budget)
    _apply_case_fixtures(case)
    try:
        final = executor.execute(run_id, pipeline)
    finally:
        _clear_case_fixtures()

    result = _result_from_run(stores, run_id)
    scores = {
        "schema_validity": round(schema_validity_score(result), 4),
        "citation_coverage": round(citation_coverage(case, result), 4),
    }
    lookahead_ok, lookahead_detail = lookahead_check(case, result)
    rules_ok, rules_detail = trading_rules_check(case, result)

    steps = stores.steps.list_steps(run_id)
    total = len(steps)
    completed = sum(1 for s in steps if s["status"] == "completed")
    tokens = sum(s.get("tokens_used") or 0 for s in steps)
    duration_s = 0.0
    started = final.get("started_at")
    finished = final.get("finished_at")
    if started and finished:
        try:
            duration_s = round(
                (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds(),
                4,
            )
        except ValueError:
            duration_s = 0.0

    return {
        "case_id": case["id"],
        "scenario": case.get("scenario"),
        "run_id": run_id,
        "run_status": final["status"],
        "scores": scores,
        "checks": {
            "lookahead": {"passed": lookahead_ok, "detail": lookahead_detail},
            "trading_rules": {"passed": rules_ok, "detail": rules_detail},
        },
        "plan_completion": round(completed / total, 4) if total else 0.0,
        "steps": total,
        "tokens_used": tokens,
        "duration_s": duration_s,
        "evidence_cited": {
            "expected": len((case.get("expected") or {}).get("evidence_requirements") or []),
            "cited": round(scores["citation_coverage"], 2),
        },
    }


def evaluate_runtime_cases(
    cases: list[dict[str, Any]],
    session_factory: SessionFactory,
    *,
    budget: RunBudget | None = None,
) -> dict[str, Any]:
    """跑全部 golden cases，输出聚合报告（确定性）。"""
    evaluated: list[dict[str, Any]] = []
    for case in cases:
        session = session_factory()
        try:
            evaluated.append(evaluate_case_through_runtime(case, session, budget=budget))
        finally:
            session.close()

    durations = [c["duration_s"] for c in evaluated]
    lookahead_pass = sum(1 for c in evaluated if c["checks"]["lookahead"]["passed"])
    plan_avg = (
        sum(c["plan_completion"] for c in evaluated) / len(evaluated) if evaluated else 0.0
    )
    citation_avg = (
        sum(c["scores"]["citation_coverage"] for c in evaluated) / len(evaluated)
        if evaluated
        else 0.0
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "runtime-replay",
        "cases_total": len(evaluated),
        "lookahead_pass_rate": round(lookahead_pass / len(evaluated), 4) if evaluated else 0.0,
        "plan_completion_avg": round(plan_avg, 4),
        "citation_coverage_avg": round(citation_avg, 4),
        "p95_duration_s": round(statistics.quantiles(durations, n=20)[18], 4) if durations else 0.0,
        "total_tokens": sum(c["tokens_used"] for c in evaluated),
        "cases": evaluated,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    from app.config import SessionLocal

    parser = argparse.ArgumentParser(description="运行时评测门禁")
    parser.add_argument("--cases", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    report = evaluate_runtime_cases(cases, SessionLocal)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"报告已写入 {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
