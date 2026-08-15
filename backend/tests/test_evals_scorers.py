"""评测评分器纯函数测试（任务 03 验收 2）。"""

from datetime import datetime, timedelta, timezone

from evals.scorers import (
    citation_coverage,
    lookahead_check,
    schema_validity_score,
    trading_rules_check,
)

NOW = datetime.now(timezone.utc)
PAST = (NOW - timedelta(days=2)).isoformat()


def _claim(**overrides):
    data = {
        "claim": "业绩预增利好",
        "category": "fundamental",
        "direction": "bullish",
        "confidence": 0.8,
        "evidence": [
            {
                "source_id": "announcement-1",
                "as_of": PAST,
                "vendor": "akshare",
                "data_version": "v1",
                "summary": "公告披露业绩预增",
            }
        ],
        "hypothesis": False,
    }
    data.update(overrides)
    return data


def test_schema_validity_score_all_valid():
    result = {"claims": [_claim(), _claim(claim="另一条")]}
    assert schema_validity_score(result) == 1.0


def test_schema_validity_score_partial():
    bad = _claim(evidence=[])
    result = {"claims": [_claim(), bad]}
    assert schema_validity_score(result) == 0.5


def test_schema_validity_score_no_claims():
    assert schema_validity_score({}) == 0.0
    assert schema_validity_score({"claims": []}) == 0.0


def test_citation_coverage_full():
    case = {"expected": {"evidence_requirements": ["announcement", "news"]}}
    result = {
        "claims": [
            _claim(),
            _claim(
                claim="政策面消息",
                evidence=[
                    {
                        "source_id": "news-2",
                        "as_of": PAST,
                        "vendor": "tavily",
                        "data_version": "v1",
                        "summary": "政策新闻",
                    }
                ],
            ),
        ]
    }
    assert citation_coverage(case, result) == 1.0


def test_citation_coverage_partial_and_empty():
    case = {"expected": {"evidence_requirements": ["kline", "news"]}}
    kline_claim = _claim(
        claim="K线走势",
        evidence=[
            {
                "source_id": "kline-1",
                "as_of": PAST,
                "vendor": "mock",
                "data_version": "v1",
                "summary": "K线数据",
            }
        ],
    )
    result = {"claims": [kline_claim]}
    assert citation_coverage(case, result) == 0.5
    assert citation_coverage({"expected": {"evidence_requirements": []}}, result) == 1.0
    assert citation_coverage(case, {"claims": []}) == 0.0


def test_lookahead_passes_when_as_of_before_available():
    case = {"data_available_at": PAST}
    result = {"claims": [_claim(as_of=PAST)]}
    passed, _ = lookahead_check(case, result)
    assert passed


def test_lookahead_fails_on_future_evidence():
    future = (NOW + timedelta(days=1)).isoformat()
    case = {"data_available_at": PAST}
    result = {
        "claims": [
            _claim(
                evidence=[
                    {
                        "source_id": "news-2",
                        "as_of": future,
                        "vendor": "tavily",
                        "data_version": "v1",
                        "summary": "未来数据",
                    }
                ]
            )
        ]
    }
    passed, detail = lookahead_check(case, result)
    assert not passed
    assert "前视" in detail


def test_lookahead_skips_without_available_at():
    passed, detail = lookahead_check({}, {"claims": [_claim()]})
    assert passed
    assert "跳过" in detail


def test_trading_rules_t_plus_1_violation():
    case = {"risk_markers": []}
    result = {
        "orders": [
            {"code": "sh.600519", "trade_date": "2026-08-10", "action": "buy", "shares": 100},
            {"code": "sh.600519", "trade_date": "2026-08-10", "action": "sell", "shares": 100},
        ]
    }
    passed, detail = trading_rules_check(case, result)
    assert not passed
    assert "T+1" in detail


def test_trading_rules_lot_size_violation():
    case = {"risk_markers": []}
    result = {"orders": [{"code": "sz.000001", "trade_date": "2026-08-10", "action": "buy", "shares": 150}]}
    passed, detail = trading_rules_check(case, result)
    assert not passed
    assert "手数" in detail


def test_trading_rules_limit_up_buy_violation():
    case = {"risk_markers": ["limit_up"]}
    result = {"orders": [{"code": "sh.600519", "trade_date": "2026-08-10", "action": "buy", "shares": 100}]}
    passed, detail = trading_rules_check(case, result)
    assert not passed
    assert "涨停" in detail


def test_trading_rules_skips_without_input():
    passed, detail = trading_rules_check({"risk_markers": []}, {"claims": []})
    assert passed
    assert "跳过" in detail
