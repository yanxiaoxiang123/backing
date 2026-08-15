"""LLM 响应缓存：record/replay（按 case id + 输入 hash 落盘）。"""

import hashlib
import json
from pathlib import Path
from typing import Any


class ResponseCache:
    """文件缓存；回放确定性，不依赖网络与 API key。"""

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _digest(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def key_for(self, case_id: str, input_digest: str) -> str:
        return f"{case_id}-{self._digest(input_digest)}.json"

    def get(self, case_id: str, input_digest: str) -> dict[str, Any] | None:
        path = self.cache_dir / self.key_for(case_id, input_digest)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, case_id: str, input_digest: str, response: dict[str, Any]) -> Path:
        path = self.cache_dir / self.key_for(case_id, input_digest)
        path.write_text(
            json.dumps(response, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return path

    def record_or_replay(
        self,
        case_id: str,
        input_digest: str,
        llm_fn: Any,
        *,
        live: bool,
    ) -> tuple[dict[str, Any] | None, bool]:
        """返回 (response, cache_hit)。live=False 时只回放，缺失返回 (None, False)。"""
        cached = self.get(case_id, input_digest)
        if cached is not None:
            return cached, True
        if not live:
            return None, False
        response = llm_fn()
        if response is None:
            return None, False
        self.put(case_id, input_digest, response)
        return response, False
