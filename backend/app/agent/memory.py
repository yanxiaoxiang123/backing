# -*- coding: utf-8 -*-
"""Agent 记忆模块 - 简化版"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    """单条记忆"""

    role: str = "user"  # user/assistant/system
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentMemory:
    """Agent 记忆模块 - 管理会话历史"""

    def __init__(self, max_entries: int = 100):
        self.max_entries = max_entries
        self.entries: List[MemoryEntry] = []

    def add(
        self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """添加记忆"""
        entry = MemoryEntry(role=role, content=content, metadata=metadata or {})
        self.entries.append(entry)

        # 限制记忆数量
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

    def get_messages(self) -> List[Dict[str, str]]:
        """获取消息格式（用于 LLM）"""
        return [
            {"role": entry.role, "content": entry.content} for entry in self.entries
        ]

    def clear(self) -> None:
        """清空记忆"""
        self.entries.clear()

    def get_recent(self, n: int = 10) -> List[MemoryEntry]:
        """获取最近 n 条记忆"""
        return self.entries[-n:]

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "entries": [
                {
                    "role": e.role,
                    "content": e.content,
                    "timestamp": e.timestamp,
                    "metadata": e.metadata,
                }
                for e in self.entries
            ],
            "count": len(self.entries),
        }
