# 06 TradingAgents 子图 + gateway vendor 深接线

**交付**：TradingAgents 图作为 Supervisor 深度研究子图运行；新增 `gateway` vendor 使 7 类分析师取数全部经类型化工具网关；产出归一为 claims + 报告 artifact。

**范围**：
- gateway vendor：在 TradingAgents vendor 路由层注册 `gateway`，各数据方法映射到工具网关（in-process Tool Registry，ToolContext 带 db session）；调用记录为 tool_call（关联 run/step）；未映射方法显式返回"未接入"，禁止回退直连 vendor。
- 子图：Supervisor 路由"深度研究"目标时运行 TA 子图（复用运行时 checkpoint 与预算边界）；子图步骤作为 run step 可见。
- 产出归一：研究报告 → `ResearchClaim` 列表 + 报告 artifact；辩论/多空结论保留结构化字段。
- 兼容：langchain 1.5.4 差异逐方法验证；不可调和处回退进程内独立执行 + 网关适配并记录。

**验收**：
- pytest：映射方法经网关、权限拒绝、未映射显式失败、gateway 模式下无直连回退（探针证明）。
- 集成：一个深度研究 run 端到端产出 claims + artifact，SSE 可见子图步骤。

**阻塞**：None
**委派**：ineligible（runtime+gateway+TA 耦合）
