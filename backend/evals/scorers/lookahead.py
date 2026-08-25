"""无前视检查：证据/结论的 as_of 不得晚于数据可得时间（data_available_at）。"""

from datetime import datetime, timezone
from typing import Any

Check = tuple[bool, str]


def lookahead_check(case: dict[str, Any], result: dict[str, Any]) -> Check:
    """返回 (passed, detail)。

    规则：case.data_available_at 是「市场当时可获得时间」；任何结论/证据的
    as_of 晚于该时间即视为前视（使用了未来信息）。
    """
    available_raw = case.get("data_available_at")
    if not available_raw:
        return True, "case 未声明 data_available_at，跳过"

    try:
        available_at = datetime.fromisoformat(available_raw)
    except (TypeError, ValueError):
        return False, f"data_available_at 无法解析: {available_raw!r}"
    if available_at.tzinfo is None:
        return False, "data_available_at 必须携带时区"
    available_at = available_at.astimezone(timezone.utc)

    claims = result.get("claims") or []
    if not isinstance(claims, list) or not claims:
        return True, "无 claims，跳过"

    violations: list[str] = []
    for idx, claim in enumerate(claims):
        evidence = claim.get("evidence") or []
        if not evidence and not claim.get("hypothesis", False):
            violations.append(f"claim[{idx}] 非假设结论缺少 evidence")
            continue
        for evidence_item in evidence:
            as_of_raw = evidence_item.get("as_of")
            if not as_of_raw:
                violations.append(f"claim[{idx}] evidence 缺少 as_of（无法证明无前视）")
                continue
            try:
                as_of = datetime.fromisoformat(as_of_raw)
            except (TypeError, ValueError):
                violations.append(f"claim[{idx}] evidence as_of 无法解析: {as_of_raw!r}")
                continue
            if as_of.tzinfo is None:
                violations.append(f"claim[{idx}] evidence as_of 必须携带时区: {as_of_raw!r}")
                continue
            if as_of.astimezone(timezone.utc) > available_at:
                violations.append(
                    f"claim[{idx}] as_of {as_of_raw} 晚于可得时间 {available_raw}（前视）"
                )
    if violations:
        return False, "; ".join(violations)
    return True, "无前视违规"
