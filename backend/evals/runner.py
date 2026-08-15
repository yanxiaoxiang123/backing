"""评测跑批入口：对 golden cases 打分并输出 JSON 报告。

live 模式（真实调用 LLM）由环境变量 EVAL_LIVE=1 控制，默认关闭；
回放模式确定性、无需 API key、无网络。
"""

import hashlib
import json
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.cache import ResponseCache
from evals.scorers import (
    citation_coverage,
    lookahead_check,
    schema_validity_score,
    trading_rules_check,
)

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "v1" / "golden_cases.json"
DEFAULT_CACHE_DIR = Path(__file__).parent / "cache"

LlmFn = Callable[[dict[str, Any]], dict[str, Any] | None]


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    dataset = Path(path) if path else DEFAULT_DATASET
    cases = json.loads(dataset.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"数据集为空: {dataset}")
    return cases


def _input_digest(case: dict[str, Any]) -> str:
    canonical = json.dumps(case, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _score_case(case: dict[str, Any], response: dict[str, Any] | None) -> dict[str, Any]:
    """对单 case 应用全部确定性评分器。"""
    if response is None:
        return {
            "scores": {},
            "checks": {},
            "scored": False,
            "note": "cache miss（live 模式未开）",
        }
    scores = {
        "schema_validity": round(schema_validity_score(response), 4),
        "citation_coverage": round(citation_coverage(case, response), 4),
    }
    lookahead_ok, lookahead_detail = lookahead_check(case, response)
    rules_ok, rules_detail = trading_rules_check(case, response)
    checks = {
        "lookahead": {"passed": lookahead_ok, "detail": lookahead_detail},
        "trading_rules": {"passed": rules_ok, "detail": rules_detail},
    }
    return {"scores": scores, "checks": checks, "scored": True}


def run_evaluation(
    cases: list[dict[str, Any]],
    llm_fn: LlmFn,
    cache: ResponseCache,
    *,
    live: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    report_cases: list[dict[str, Any]] = []
    cache_misses = 0

    for case in cases:
        case_started = time.perf_counter()
        response, cache_hit = cache.record_or_replay(
            case["id"],
            _input_digest(case),
            lambda c=case: llm_fn(c),
            live=live,
        )
        if not cache_hit and not live:
            cache_misses += 1
        scored = _score_case(case, response)
        report_cases.append(
            {
                "case_id": case["id"],
                "scenario": case.get("scenario"),
                "cache_hit": cache_hit,
                "duration_s": round(time.perf_counter() - case_started, 4),
                "tokens_used": (response or {}).get("tokens_used"),
                **scored,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "replay",
        "cases_total": len(cases),
        "cases_scored": sum(1 for c in report_cases if c["scored"]),
        "cases_cache_miss": cache_misses,
        "total_duration_s": round(time.perf_counter() - started, 4),
        "cases": report_cases,
    }


def default_llm(case: dict[str, Any]) -> dict[str, Any] | None:
    """占位 LLM：不真实调用。live 集成时替换为 pipeline 适配器。"""
    return None


def is_live_mode() -> bool:
    return os.environ.get("EVAL_LIVE", "0") == "1"


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Agent 评测跑批")
    parser.add_argument("--cases", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--live", action="store_true", help="真实调用 LLM（默认回放）")
    parser.add_argument("--output", type=Path, default=None, help="报告输出路径（默认 stdout）")
    args = parser.parse_args(argv)

    live = args.live or is_live_mode()
    cases = load_cases(args.cases)
    cache = ResponseCache(args.cache_dir)
    report = run_evaluation(cases, default_llm, cache, live=live)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"报告已写入 {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
