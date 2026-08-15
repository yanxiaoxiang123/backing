"""运行时评测门禁测试（任务 12 验收）。

覆盖：10 个 golden cases 经运行时全跑通、lookahead 100%、plan_completion 100%、
as_of 注入（证据时间 = case 可得时间）、分数确定性可重复、报告可 JSON 序列化。
"""

import json
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.strategy  # noqa: F401
from app.config import Base
from app.models.models import DailyKline, Stock
from evals.runner import load_cases
from evals.runtime_runner import (
    evaluate_case_through_runtime,
    evaluate_runtime_cases,
)

CASE_CODES = {
    "sh.600519",
    "sz.000001",
    "sh.600000",
    "sz.000002",
    "sh.601318",
    "sz.300750",
    "sz.002594",
    "sh.600036",
}


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    start = date(2026, 6, 1)
    closes = [10.0, 10.2, 10.5, 10.9, 11.2, 10.8, 10.4, 10.0, 9.8, 10.3, 10.9, 11.4]
    for code in CASE_CODES:
        session.add(Stock(code=code, name=code, market=code[:2]))
        for idx, close in enumerate(closes):
            session.add(
                DailyKline(
                    stock_code=code,
                    date=start + timedelta(days=idx),
                    open=close - 0.1,
                    high=close + 0.2,
                    low=close - 0.2,
                    close=close,
                    volume=100000 + idx * 1000,
                    amount=close * 100000,
                )
            )
    session.commit()
    session.close()
    return lambda: sessionmaker(bind=engine)()


def test_all_cases_pass_through_runtime(session_factory):
    cases = load_cases()
    report = evaluate_runtime_cases(cases, session_factory)
    assert report["cases_total"] == 10
    assert all(c["run_status"] == "completed" for c in report["cases"])
    assert report["lookahead_pass_rate"] == 1.0
    assert report["plan_completion_avg"] == 1.0
    assert report["total_tokens"] == 0  # 确定性流水线无 LLM 调用


def test_scores_deterministic(session_factory):
    cases = load_cases()
    first = evaluate_runtime_cases(cases, session_factory)
    second = evaluate_runtime_cases(cases, session_factory)
    for c1, c2 in zip(first["cases"], second["cases"], strict=True):
        assert c1["scores"] == c2["scores"]
        assert c1["checks"] == c2["checks"]
        assert c1["plan_completion"] == c2["plan_completion"]


def test_kline_volume_case_citation_full(session_factory):
    cases = {c["id"]: c for c in load_cases()}
    case = cases["case-001"]  # 期望 kline + volume
    session = session_factory()
    try:
        evaluated = evaluate_case_through_runtime(case, session)
    finally:
        session.close()
    assert evaluated["scores"]["citation_coverage"] == 1.0
    assert evaluated["checks"]["lookahead"]["passed"] is True


def test_citation_coverage_reaches_target(session_factory):
    """研究专家升级（US-2.6）：夹具回放下引用覆盖率 ≥95%（规格 v2 验收）。"""
    report = evaluate_runtime_cases(load_cases(), session_factory)
    assert report["citation_coverage_avg"] >= 0.95
    assert all(c["scores"]["citation_coverage"] >= 0.95 for c in report["cases"])


def test_as_of_injection_matches_case_available_at(session_factory):
    cases = {c["id"]: c for c in load_cases()}
    case = cases["case-003"]
    session = session_factory()
    try:
        evaluated = evaluate_case_through_runtime(case, session)
        from app.agent_runtime.stores import create_stores

        stores = create_stores(session)
        steps = {s["node"]: s for s in stores.steps.list_steps(evaluated["run_id"])}
        research = steps["research"]["output_json"]
        evidence = research["claims"][0]["evidence"][0]
    finally:
        session.close()
    expected = datetime.fromisoformat(case["data_available_at"])
    assert datetime.fromisoformat(evidence["as_of"]) == expected


def test_report_json_serializable(session_factory):
    report = evaluate_runtime_cases(load_cases(), session_factory)
    json.dumps(report, ensure_ascii=False)  # 不抛异常即可
