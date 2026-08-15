"""评测 runner 测试（任务 03 验收 3/4/5）：mock LLM、JSON 报告、确定性。"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evals.cache import ResponseCache
from evals.runner import load_cases, run_evaluation

NOW = datetime.now(timezone.utc)
PAST = (NOW - timedelta(days=2)).isoformat()


def _mock_llm(case: dict) -> dict:
    return {
        "claims": [
            {
                "claim": f"针对 {case['stock_code']} 的结论",
                "category": "technical",
                "direction": "neutral",
                "confidence": 0.5,
                "evidence": [
                    {
                        "source_id": "kline-1",
                        "as_of": PAST,
                        "vendor": "mock",
                        "data_version": "v1",
                        "summary": "K线数据",
                    }
                ],
                "hypothesis": False,
            }
        ],
        "tokens_used": 42,
    }


def _single_case() -> dict:
    return {
        "id": "case-001",
        "scenario": "bull",
        "stock_code": "sh.600519",
        "objective": "判断趋势",
        "data_available_at": PAST,
        "expected": {"conclusion_points": ["趋势"], "evidence_requirements": ["kline"]},
        "risk_markers": [],
    }


def test_load_cases_dataset(tmp_path: Path):
    dataset = tmp_path / "cases.json"
    dataset.write_text(json.dumps([_single_case()]), encoding="utf-8")
    cases = load_cases(dataset)
    assert len(cases) == 1
    assert cases[0]["id"] == "case-001"


def test_run_evaluation_live_roundtrip(tmp_path: Path):
    cache = ResponseCache(tmp_path / "cache")
    report = run_evaluation([_single_case()], _mock_llm, cache, live=True)
    assert report["mode"] == "live"
    assert report["cases_total"] == 1
    assert report["cases_scored"] == 1
    case = report["cases"][0]
    assert case["cache_hit"] is False
    assert case["tokens_used"] == 42
    assert case["scored"] is True
    assert case["scores"]["schema_validity"] == 1.0
    assert case["scores"]["citation_coverage"] == 1.0
    assert case["checks"]["lookahead"]["passed"] is True


def test_run_evaluation_replay_deterministic(tmp_path: Path):
    cache = ResponseCache(tmp_path / "cache")
    run_evaluation([_single_case()], _mock_llm, cache, live=True)
    report1 = run_evaluation([_single_case()], _mock_llm, cache, live=False)
    report2 = run_evaluation([_single_case()], _mock_llm, cache, live=False)

    assert report1["mode"] == "replay"
    assert report1["cases_cache_miss"] == 0
    assert report1["cases"][0]["cache_hit"] is True
    # 确定性：两次回放分数一致（忽略时长/时间戳）
    for key in ("scores", "checks"):
        assert report1["cases"][0][key] == report2["cases"][0][key]
    # LLM 未再被调用（无 cache 时走 mock，但这里全命中）
    assert report1["cases"][0]["tokens_used"] == 42


def test_run_evaluation_replay_cache_miss_not_fatal(tmp_path: Path):
    cache = ResponseCache(tmp_path / "cache")
    report = run_evaluation([_single_case()], _mock_llm, cache, live=False)
    assert report["cases_cache_miss"] == 1
    assert report["cases"][0]["scored"] is False
    assert "cache miss" in report["cases"][0]["note"]


def test_run_evaluation_report_is_json_serializable(tmp_path: Path):
    cache = ResponseCache(tmp_path / "cache")
    report = run_evaluation([_single_case()], _mock_llm, cache, live=True)
    json.dumps(report, ensure_ascii=False)  # 不抛异常即可
