# 09 Supervisor 动态路由图

- **用户可见交付**：Supervisor 节点按目标生成 `RunPlan` 并动态路由 Data QA/Research/Strategy Engineer/Backtest Critic/Portfolio Risk 专家；专家输出经领域 schema 校验；证据冲突或高风险提案才触发辩论（复用 TradingAgents 多空/风险辩论作为可选模式）；`BacktestVerdict` 为确定性引擎产出，LLM 不得篡改。
- **验收标准**：
  1. fake model 测试：简单目标只路由 2–3 个专家，高风险提案触发辩论，全程在预算内。
  2. 每个专家节点输出必须过对应 schema（`ResearchClaim`/`StrategySpec`/`BacktestVerdict`/`PortfolioProposal`），非法输出重试后失败并记录原因。
  3. 回测数字来自 `backtest_executor`，LLM 只生成解释文本；pytest 证明篡改被拒绝。
  4. 与 05 的 checkpoint/事件/取消完全兼容（中断恢复测试）。
  5. TradingAgents A 股规则（质量门控、游资/解禁约束）保留有效。
- **阻塞任务**：05, 08, 02
- **委派**：ineligible（runtime + tools + LLM 三方耦合，主 agent 执行）
