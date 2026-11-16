"""AI naming is persistent, independent of chat execution, and best effort."""

import threading
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import sessionmaker

from app.agent_chat.seam import FakeHarnessChatSeam
from app.agent_chat.service import HarnessChatService
from app.agent_chat.stores import create_chat_stores
from app.agent_chat.titles import (
    DeepSeekTitleGenerator,
    clean_title,
    fallback_title,
    needs_title,
)
from tests.test_agent_chat_service import (
    BlockingSeam,
    _engine,
    threads_get,
    turns_of,
    wait_until,
)


@pytest.fixture()
def session_factory(tmp_path):
    engine = _engine(tmp_path)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('标题：“浦发银行均线回测”\n解释：省略', "浦发银行均线回测"),
        ("## **银行股估值分析**", "银行股估值分析"),
        ("Title: `MA 策略`", "MA 策略"),
        ("未命名会话", ""),
        (" \n ", ""),
        ("股" * 50, "股" * 36),
    ],
)
def test_clean_title(raw, expected):
    assert clean_title(raw) == expected


def test_title_generator_uses_configured_provider_with_bounded_request(monkeypatch):
    model = Mock()
    model.invoke.return_value = SimpleNamespace(content="银行股估值比较")
    constructor = Mock(return_value=model)
    monkeypatch.setattr("langchain_openai.ChatOpenAI", constructor)
    generator = DeepSeekTitleGenerator(
        api_key_provider=lambda: "test-only",
        base_url="https://provider.invalid/v1",
        model_name="configured-model",
    )
    assert generator("股" * 8000) == "银行股估值比较"
    kwargs = constructor.call_args.kwargs
    assert kwargs["model"] == "configured-model"
    assert kwargs["base_url"] == "https://provider.invalid/v1"
    assert kwargs["timeout"] == 12
    assert kwargs["max_retries"] == 0
    assert kwargs["max_tokens"] == 64
    assert kwargs["streaming"] is False
    messages = model.invoke.call_args.args[0]
    assert len(messages[1]["content"]) == 2000


def test_missing_provider_key_is_safe():
    generator = DeepSeekTitleGenerator(
        api_key_provider=lambda: None, base_url="unused", model_name="unused"
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        generator("分析银行股")


def seed_chat(session_factory, service, *, title=None, archived=False):
    thread = service.create_thread(title=title)
    with session_factory() as session:
        stores = create_chat_stores(session)
        stores.turns.create_turn(
            turn_id=f"first-{thread['thread_id']}",
            thread_id=thread["thread_id"],
            user_input="比较银行股估值与风险",
            status="completed",
        )
        # A later turn must not become the naming source.
        stores.turns.create_turn(
            turn_id=f"last-{thread['thread_id']}",
            thread_id=thread["thread_id"],
            user_input="另一条消息",
            status="completed",
        )
        if archived:
            stores.threads.update_thread(thread["thread_id"], archived=True)
        return stores.threads.get_thread(thread["thread_id"])


def test_generation_does_not_wait_for_chat_or_repeat(session_factory):
    chat_gate = threading.Event()
    title_gate = threading.Event()
    entered = threading.Event()
    calls = []

    def generate(text):
        calls.append(text)
        entered.set()
        assert title_gate.wait(3)
        return '标题：“浦发银行均线回测”'

    seam = BlockingSeam(FakeHarnessChatSeam(session_factory), chat_gate)
    service = HarnessChatService(session_factory, seam, title_generator=generate)
    service.startup()
    try:
        thread = service.create_thread()
        tid = thread["thread_id"]
        turn = service.submit_turn(tid, "帮我回测浦发银行均线策略", idempotency_key="same")
        assert entered.wait(2)
        assert seam.entered.wait(2)
        assert service.ensure_thread_title(thread) is True
        assert service.submit_turn(tid, "重复", idempotency_key="same")["id"] == turn["id"]
        title_gate.set()
        assert wait_until(
            lambda: threads_get(session_factory, tid)["title"] == "浦发银行均线回测"
        )
        # Chat is still blocked; an old list snapshot cannot trigger another AI call.
        assert turns_of(session_factory, tid)[0]["status"] == "running"
        assert service.ensure_thread_title(thread) is False
        assert thread["title"] == "浦发银行均线回测"
        assert len(calls) == 1
    finally:
        title_gate.set()
        chat_gate.set()
        service.shutdown()


def test_backfill_uses_first_turn_and_preserves_recent_order(session_factory):
    generate = Mock(return_value="银行股估值比较")
    service = HarnessChatService(
        session_factory, FakeHarnessChatSeam(session_factory), title_generator=generate
    )
    service.startup()
    try:
        thread = seed_chat(session_factory, service, title="未命名会话")
        with session_factory() as session:
            stores = create_chat_stores(session)
            stores.threads.update_thread(
                thread["thread_id"], updated_at=datetime(2026, 8, 18)
            )
            thread = stores.threads.get_thread(thread["thread_id"])
        assert service.ensure_thread_title(thread)
        assert wait_until(
            lambda: threads_get(session_factory, thread["thread_id"])["title"]
            == "银行股估值比较"
        )
        generate.assert_called_once_with("比较银行股估值与风险")
        assert threads_get(session_factory, thread["thread_id"])["updated_at"] == thread["updated_at"]
    finally:
        service.shutdown()


@pytest.mark.parametrize("result", [RuntimeError("provider failed"), "", "未命名会话"])
def test_failed_or_empty_generation_persists_fallback(session_factory, result, caplog):
    generate = Mock(
        side_effect=result if isinstance(result, Exception) else None,
        return_value=result if isinstance(result, str) else "",
    )
    service = HarnessChatService(
        session_factory, FakeHarnessChatSeam(session_factory), title_generator=generate
    )
    service.startup()
    try:
        thread = seed_chat(session_factory, service)
        assert service.ensure_thread_title(thread)
        assert wait_until(
            lambda: threads_get(session_factory, thread["thread_id"])["title"]
            == "比较银行股估值与风险"
        )
        assert service.ensure_thread_title(thread) is False
        assert generate.call_count == 1
        assert "provider failed" not in caplog.text
    finally:
        service.shutdown()


def test_no_model_calls_for_named_empty_or_archived_chats(session_factory):
    generate = Mock(return_value="不应调用")
    service = HarnessChatService(
        session_factory, FakeHarnessChatSeam(session_factory), title_generator=generate
    )
    service.startup()
    try:
        assert not service.ensure_thread_title(service.create_thread())
        named = seed_chat(session_factory, service, title="手动标题")
        assert not service.ensure_thread_title(named)
        archived = seed_chat(session_factory, service, archived=True)
        assert not service.ensure_thread_title(archived)
        generate.assert_not_called()
    finally:
        service.shutdown()


@pytest.mark.parametrize("archive", [False, True])
def test_model_result_cannot_overwrite_new_title_or_archived_chat(session_factory, archive):
    gate = threading.Event()
    entered = threading.Event()

    def generate(_text):
        entered.set()
        assert gate.wait(3)
        return "模型生成标题"

    service = HarnessChatService(
        session_factory, FakeHarnessChatSeam(session_factory), title_generator=generate
    )
    service.startup()
    try:
        thread = seed_chat(session_factory, service)
        assert service.ensure_thread_title(thread)
        assert entered.wait(2)
        with session_factory() as session:
            fields = {"archived": True} if archive else {"title": "人工修改标题"}
            create_chat_stores(session).threads.update_thread(thread["thread_id"], **fields)
        gate.set()
    finally:
        gate.set()
        service.shutdown()
    saved = threads_get(session_factory, thread["thread_id"])
    expected = None if archive else "人工修改标题"
    assert saved["title"] == expected


def test_fallback_is_single_line_and_not_an_unnamed_placeholder():
    assert fallback_title("分析\n 银行股") == "分析 银行股"
    assert not needs_title(fallback_title("未命名会话"))
