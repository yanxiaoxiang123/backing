"""模拟盘（paper trading）领域逻辑包。

- rules：确定性撮合规则与费用（纯函数）
- replay：append-only 事件重放（纯函数）
- service：DB 编排（撮合调度、审批状态机，切片 05 引入）
"""
