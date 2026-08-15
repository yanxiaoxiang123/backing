"""agent_api：run/stream/resume/cancel/artifact 的 HTTP 面（规格决策 4；US-1.1）。

事件流走 SSE（``Last-Event-ID`` 断线重放）；任务 09 前使用确定性占位流水线。
"""
