# 02 领域契约 schema

- **用户可见交付**：`backend/app/domain/` 提供六大结构化契约：`RunPlan`、`ResearchClaim`、`StrategySpec`、`BacktestVerdict`、`PortfolioProposal`、`DataQualityReport`；所有证据字段强制 `source_id`、`as_of`、vendor、数据版本；无证据结论只能标记为假设。
- **验收标准**：
  1. 每个 schema 有 pytest 正反例：合法样例通过、缺证据/缺 `as_of`/非法枚举被拒。
  2. `as_of` 语义明确为"市场当时可获得时间"，非法未来时间或缺失在证据类 schema 上被拒。
  3. `StrategySpec` 为纯声明式（universe/signal/rebalance/position sizing/risk constraints/cost model），不接受代码字符串。
  4. schema 版本号随模块走（`SCHEMA_VERSION`），序列化可往返。
  5. 模块不 import 数据库/服务层（纯 Pydantic），`ruff check` 通过。
- **阻塞任务**：None
- **委派**：eligible（自包含模块，契约已由规格定稿）
