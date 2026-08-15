"""Schema 校验评分：结果能否通过领域契约（app.domain）校验。"""

import logging
from collections.abc import Callable
from typing import Any

from app.domain.research import ResearchClaim

logger = logging.getLogger(__name__)


def schema_validity_score(
    result: dict[str, Any],
    *,
    claim_loader: Callable[[dict[str, Any]], Any] | None = None,
) -> float:
    """返回 [0,1]：合法 claims 占全部 claims 的比例。

    result 期望形如 ``{"claims": [...]}``；claims 缺失时视为 0。
    """
    claims = result.get("claims")
    if claims is None:
        return 0.0
    if not isinstance(claims, list) or len(claims) == 0:
        return 0.0

    loader = claim_loader or (lambda item: ResearchClaim.model_validate(item))
    valid = 0
    for item in claims:
        try:
            loader(item)
            valid += 1
        except Exception as exc:
            logger.debug("claim 校验失败: %s", exc)
    return valid / len(claims)
