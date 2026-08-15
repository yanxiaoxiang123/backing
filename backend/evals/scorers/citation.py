"""证据引用覆盖率：期望证据锚点在结果中得到引用的比例。"""

from typing import Any

#: golden case 中证据要求的关键词 → 证据 source_id 中应出现的特征
EVIDENCE_ANCHORS: dict[str, tuple[str, ...]] = {
    "kline": ("kline", "k线", "ohlc"),
    "volume": ("volume", "volume", "量"),
    "announcement": ("announcement", "公告", "notice"),
    "news": ("news", "新闻", "policy"),
    "financials": ("financials", "财报", "financial"),
}


def citation_coverage(case: dict[str, Any], result: dict[str, Any]) -> float:
    """返回 [0,1]：被引用的期望证据锚点 / 期望证据锚点总数。

    无证据要求的 case（expected.evidence_requirements 为空）返回 1.0。
    """
    expected = (case.get("expected") or {}).get("evidence_requirements") or []
    if not expected:
        return 1.0

    claims = result.get("claims") or []
    if not isinstance(claims, list) or not claims:
        return 0.0

    # 收集结果中出现的全部证据 source_id / summary 文本
    cited_texts: list[str] = []
    for claim in claims:
        for evidence in (claim.get("evidence") or []):
            cited_texts.append(str(evidence.get("source_id", "")))
            cited_texts.append(str(evidence.get("summary", "")))

    def is_cited(anchor: str) -> bool:
        features = EVIDENCE_ANCHORS.get(anchor, (anchor,))
        joined = " ".join(cited_texts).lower()
        return any(feature.lower() in joined for feature in features)

    cited = sum(1 for anchor in expected if is_cited(anchor))
    return cited / len(expected)
