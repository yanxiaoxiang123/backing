# 04 run 持久化

- **用户可见交付**：`agent_runs`、`agent_steps`、`tool_calls`、`artifacts`、`approvals` 五张表加入现有 SQLAlchemy 库并出 Alembic 迁移；全部读写走 repository 接口（换 PostgreSQL 只换实现类）。
- **验收标准**：
  1. Alembic 迁移可从当前 head 升级并降级成功；`test_migrations` 体系覆盖新表。
  2. repository 接口定义清晰（run/step/tool_call/artifact/approval 的 CRUD + 按 run_id/seq 查询），SQLite 实现类全部有 pytest。
  3. `tool_calls` 含工具名/版本、参数 hash、权限等级、结果引用、耗时、状态；`artifacts` 含类型、URI、checksum、source_id、as_of、schema version。
  4. 敏感字段（提示词全文、trace 内容）默认不在表中落明文，留脱敏字段位。
  5. `ruff check` + 既有 166 测试全绿。
- **阻塞任务**：None
- **委派**：ineligible（共享 models/migrations 与既有约定耦合，主 agent 执行）
