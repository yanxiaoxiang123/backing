"""评测缓存 record/replay 确定性测试（任务 03 验收 3）。"""

from pathlib import Path

import pytest

from evals.cache import ResponseCache

RESPONSE = {"claims": [{"claim": "测试结论"}], "tokens_used": 123}


@pytest.fixture
def cache(tmp_path: Path) -> ResponseCache:
    return ResponseCache(tmp_path / "cache")


def test_replay_returns_cached_without_llm(cache: ResponseCache):
    cache.put("case-001", "digest-a", RESPONSE)
    response, hit = cache.record_or_replay("case-001", "digest-a", lambda: None, live=False)
    assert hit is True
    assert response == RESPONSE


def test_replay_miss_returns_none_without_calling_llm(cache: ResponseCache):
    called = False

    def llm():
        nonlocal called
        called = True
        return RESPONSE

    response, hit = cache.record_or_replay("case-002", "digest-x", llm, live=False)
    assert hit is False
    assert response is None
    assert called is False  # 回放模式不调用 LLM


def test_live_records_and_replays(cache: ResponseCache):
    response, hit = cache.record_or_replay("case-003", "digest-y", lambda: RESPONSE, live=True)
    assert hit is False
    assert response == RESPONSE
    # 二次回放命中
    response2, hit2 = cache.record_or_replay("case-003", "digest-y", lambda: None, live=False)
    assert hit2 is True
    assert response2 == RESPONSE


def test_same_input_same_key(cache: ResponseCache):
    k1 = cache.key_for("case-001", "same-input")
    k2 = cache.key_for("case-001", "same-input")
    k3 = cache.key_for("case-001", "other-input")
    assert k1 == k2
    assert k1 != k3
