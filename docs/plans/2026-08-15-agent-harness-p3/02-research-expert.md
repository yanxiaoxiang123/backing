# 02 研究专家升级 + 引用 ≥95%

**交付**：研究专家节点升级为真实引用型：经研究数据层工具采集证据，产出带证据引用的 `ResearchClaim` 列表；golden cases 引用覆盖率 ≥95%。

**范围**：
- 专家行为：LLM 只做工具选择、检索参数与结论解释；事实必须来自工具 envelope；无证据表述 `hypothesis=True`。
- 引用评分器：覆盖率为"有证据引用的 claims / 全部 claims"；golden 研究场景用例扩展（新闻/公告/财报/指数），工具响应走缓存回放。
- 运行预算沿用既有 run 预算；外呼失败降级为 DataQualityReport 条目。

**验收**：
- pytest：claims 证据五元组校验、无证据即 hypothesis、评分器确定性。
- 评测：缓存回放下引用覆盖率 ≥95% 证据（`evals/run_eval.py` 输出）。
- 回归：既有专家/评测测试全绿。

**阻塞**：01
**委派**：ineligible（experts+evals+supervisor 耦合）
