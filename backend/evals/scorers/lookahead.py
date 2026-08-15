"""无前视检查：证据/结论的 as_of 不得晚于数据可得时间（data_available_at）。"""

from datetime import datetime
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
    except ValueError:
        return True, "data_available_at 无法解析，跳过"

    claims = result.get("claims") or []
    if not isinstance(claims, list) or not claims:
        return True, "无 claims，跳过"

    violations: list[str] = []
    for idx, claim in enumerate(claims):
        evidence = claim.get("evidence") or []
        for evidence_item in evidence:
            as_of_raw = evidence_item.get("as_of")
            if not as_of_raw:
                continue
            try:
                as_of = datetime.fromisoformat(as_of_raw)
            except ValueError:
                violations.append(f"claim[{idx}] evidence as_of 无法解析: {as_of_raw!r}")
                continue
            if as_of > available_at:
                violations.append(
                    f"claim[{idx}] as_of {as_of_raw} 晚于可得时间 {available_raw}（前视）"
                )
    if violations:
        return False, "; ".join(violations)
    return True, "无前视违规"
