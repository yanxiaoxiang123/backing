# 03 评测骨架

- **用户可见交付**：`evals/` 目录含版本化数据集与确定性评分器；10 个 golden cases 覆盖牛/熊/震荡/停牌/涨跌停/财报发布/解禁/数据缺失；LLM 响应缓存 record/replay，CI 不依赖外网与 API key。
- **验收标准**：
  1. `evals/datasets/v1/` 10 个 case 每个含输入、期望结论要点、证据要求与风险标记。
  2. 确定性评分器（schema 校验、引用覆盖率、无前视、A 股成交规则）为纯函数，pytest 覆盖。
  3. 对当前 `AgentOrchestrator` 跑 10 个 case：LLM 响应全缓存回放，结果可重复（同输入同分数）；缓存缺失时仅记录不失败。
  4. live 跑批为独立开关（env/标记），默认关闭。
  5. 评分结果输出 JSON 报告（分数、耗时、token 用量字段预留）。
- **阻塞任务**：None
- **委派**：eligible（独立评测域；需在 prompt 中提供当前 pipeline 接口说明）
