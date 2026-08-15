# 08 类型化 Tool Gateway

- **用户可见交付**：`backend/app/tools/` 提供八域工具（market/fundamental/event/factor/strategy/backtest/portfolio/execution.paper 占位）的注册表、统一 JSON Schema、参数校验与三级权限（只读默认开放 / 策略写与高成本回测需策略权限 / 模拟下单需人工审批）；Agent 无数据库写权限与 Shell。
- **验收标准**：
  1. 每域至少 1–2 个工具落地并包装既有确定性服务（`baostock_service`/`indicator_service`/`backtest_executor`/`strategy.registry`），provider 全部 mock 化测试。
  2. 权限矩阵 pytest：只读工具匿名可用（运行上下文内）、策略/回测写入无权限被拒、paper 下单无审批被拒。
  3. allowlist 与参数校验（范围/枚举/输出大小）有测试；工具调用参数 hash 与 04 表结构一致。
  4. 工具返回统一 envelope（数据 + source_id + as_of + vendor），证据字段缺失即校验失败。
  5. `ruff check` + 全量 pytest 绿；无真实网络调用。
- **阻塞任务**：02
- **委派**：eligible（服务包装边界清晰；需在 prompt 中给出各服务公共签名）
