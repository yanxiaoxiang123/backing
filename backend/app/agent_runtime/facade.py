"""TradingAgents 图适配接缝（任务 05 验收 5；任务 09 深化）。

- ``get_langgraph_checkpointer``：统一 SQLite checkpointer（langgraph-checkpoint-sqlite）
- ``build_tradingagents_graph``：构建 TradingAgents 图（workspace 引擎），
  checkpoint/事件注入细节由任务 09 的统一 facade 完成
"""

from pathlib import Path
from typing import Any


def get_langgraph_checkpointer(db_path: str | Path):
    """创建 SqliteSaver（langgraph-checkpoint-sqlite）。"""
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


def build_tradingagents_graph(config: dict[str, Any] | None = None) -> Any:
    """构建 TradingAgents 图（v0.2.4，本地 A 股定制保留）。"""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    return TradingAgentsGraph(config=config or {})
