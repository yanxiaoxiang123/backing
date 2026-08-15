"""artifact 工作区（规格 v2；US-2.9）。

运行时节点把关键产物（策略规格、回测报告、研究摘要）写成每 run 独立的
工作区文件（backend/data/artifacts/{run_id}/），同时落 artifacts 记录；
文件内容与记录一致，工作台可查看/下载。
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2] / "data" / "artifacts"


def workspace_dir(run_id: str) -> Path:
    return _ROOT / run_id


def _safe_filename(filename: str) -> str:
    """拒绝路径穿越：只允许安全的相对文件名。"""
    name = Path(filename).name
    if name in ("", ".", "..") or "/" in filename or "\\" in filename:
        raise ValueError(f"非法产物文件名: {filename!r}")
    return name


def emit_artifact(
    stores: Any,
    run_id: str,
    artifact_type: str,
    filename: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """写 JSON 工作区文件 + artifacts 记录。失败不抛（记录日志，不阻断 run）。"""
    try:
        safe = _safe_filename(filename)
        directory = workspace_dir(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / safe
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        path.write_text(content, encoding="utf-8")
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return stores.artifacts.create_artifact(
            run_id=run_id,
            artifact_type=artifact_type,
            uri=f"{run_id}/{safe}",
            checksum=checksum,
            schema_version="1.0.0",
        )
    except Exception:
        logger.exception("artifact 写入失败: run=%s type=%s", run_id, artifact_type)
        return None


def read_artifact(run_id: str, filename: str) -> str | None:
    """读工作区文件内容；文件缺失返回 None。"""
    try:
        safe = _safe_filename(filename)
    except ValueError:
        return None
    path = workspace_dir(run_id) / safe
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def filename_of(uri: str) -> str:
    """artifacts.uri（run_id/filename）→ filename。"""
    return uri.split("/", 1)[1] if "/" in uri else uri
