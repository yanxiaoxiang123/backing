"""Agent 评测骨架（任务 03）。

- datasets/v1: 10 个 golden cases（缓存回放，CI 不依赖外网与 API key）
- scorers: 确定性评分器（纯函数）
- cache: LLM 响应 record/replay
- runner: 跑批入口，输出 JSON 报告

live 跑批由环境变量 EVAL_LIVE=1 控制，默认关闭。
"""

__version__ = "0.1.0"
