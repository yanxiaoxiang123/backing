"""研究专家升级测试（切片 02；US-2.6）。

确定性工具引用：新闻/公告/财报证据携带五元组、引用锚点与评分器匹配、
工具失败跳过不伪造、无证据即假设。
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.strategy  # noqa: F401
from app.agent_runtime.graphs.experts import research_node
from app.agent_runtime.runtime import NodeContext
from app.agent_runtime.stores import create_stores
from app.config import Base
from app.models.agent_runtime import AgentRun
from app.models.models import DailyKline, Stock
from app.services import research_data

AS_OF = datetime(2026, 8, 14, 7, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add(AgentRun(run_id="run-r-1", objective="测试"))
    s.add(Stock(code="sh.600000", name="浦发银行", market="sh"))
    closes = [10, 10.2, 10.5, 10.9, 11.2, 10.8, 10.4, 10.0, 9.8, 10.3, 10.9, 11.4]
    for idx, close in enumerate(closes):
        s.add(
            DailyKline(
                stock_code="sh.600000",
                date=date(2026, 8, 1) + timedelta(days=idx),
                open=close - 0.1,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=100000 + idx * 1000,
                amount=close * 100000,
            )
        )
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def stores(session):
    return create_stores(session)


@pytest.fixture(autouse=True)
def _clear_fixtures():
    yield
    research_data.clear_fixtures()


def _run_node(session, stores) -> list[dict]:
    ctx = NodeContext(
        run_id="run-r-1",
        seq=1,
        node="research",
        stores=stores,
        step_db_id=None,
        db=session,
        as_of=AS_OF,
    )
    result = research_node("sh.600000").run(ctx)
    assert result["output_schema"] == "ResearchClaim[]"
    return result["output"]["claims"]


def _install_entry(tool: str, entry: dict) -> None:
    research_data.set_fixture(tool, entry)


def _fixture_entry(case_id: str, tool: str) -> dict:
    from evals.runtime_runner import RESEARCH_FIXTURES

    return RESEARCH_FIXTURES[case_id][tool]


class TestEvidenceClaims:
    def test_news_claim_with_evidence(self, session, stores):
        _install_entry("event.news", _fixture_entry("case-005", "event.news"))
        claims = _run_node(session, stores)
        news_claims = [c for c in claims if c["category"] == "news"]
        assert news_claims, "应产出新闻类 claim"
        evidence = news_claims[0]["evidence"][0]
        assert evidence["source_id"].startswith("news:")
        assert evidence["as_of"]
        assert evidence["vendor"] == "akshare"
        assert evidence["data_version"]

    def test_announcement_claim_with_evidence(self, session, stores):
        _install_entry(
            "event.announcement",
            _fixture_entry("case-004", "event.announcement"),
        )
        claims = _run_node(session, stores)
        ann = [c for c in claims if c["claim"].startswith("公告")]
        assert ann, "应产出公告类 claim"
        assert ann[0]["evidence"][0]["source_id"].startswith("notice:")

    def test_financials_claim_with_evidence(self, session, stores):
        _install_entry(
            "fundamental.financials",
            _fixture_entry("case-007", "fundamental.financials"),
        )
        claims = _run_node(session, stores)
        fin = [c for c in claims if c["claim"].startswith("财报")]
        assert fin, "应产出财报类 claim"
        assert fin[0]["evidence"][0]["source_id"].startswith("financials:")

    def test_all_claims_have_evidence_or_hypothesis(self, session, stores):
        for tool, case_id in (
            ("event.news", "case-005"),
            ("event.announcement", "case-004"),
            ("fundamental.financials", "case-007"),
        ):
            _install_entry(tool, _fixture_entry(case_id, tool))
        claims = _run_node(session, stores)
        assert claims
        for claim in claims:
            assert claim["evidence"] or claim["hypothesis"] is True

    def test_evidence_as_of_not_future(self, session, stores):
        _install_entry("event.news", _fixture_entry("case-005", "event.news"))
        claims = _run_node(session, stores)
        for claim in claims:
            for ev in claim["evidence"]:
                as_of = datetime.fromisoformat(ev["as_of"])
                assert as_of.tzinfo is not None
                assert as_of <= datetime.now(timezone.utc)


class TestFailureHandling:
    def test_failed_tools_skipped_without_fake_evidence(self, session, stores):
        def boom(params):
            raise ValueError("network down")

        research_data.set_fixture("event.news", boom)
        research_data.set_fixture("event.announcement", boom)
        research_data.set_fixture("fundamental.financials", boom)
        claims = _run_node(session, stores)
        assert len(claims) == 1  # 仅技术面 claim
        assert claims[0]["category"] == "technical"
        # 无伪造证据
        assert not any(
            c["category"] == "news"
            or c["claim"].startswith("公告")
            or c["claim"].startswith("财报")
            for c in claims
        )

    def test_empty_fixtures_skip_all_event_claims(self, session, stores):
        for tool in ("event.news", "event.announcement", "fundamental.financials"):
            _install_entry(
                tool,
                {
                    "payload": {"rows": 0},
                    "source_id": f"{tool}:none",
                    "as_of": AS_OF.isoformat(),
                    "vendor": "akshare",
                    "data_version": "1.0.0",
                },
            )
        claims = _run_node(session, stores)
        assert len(claims) == 1
        assert claims[0]["category"] == "technical"
