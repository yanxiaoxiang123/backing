# Skill：A 股投研（供 DSH 对话代理加载）

## 工作原则
- 结论必须带证据（`source_id` / `as_of` / vendor）；无证据只能标注为假设。
- 行情、回测、组合约束一律经类型化工具（`market.*`/`factor.*`/`backtest.*`/`portfolio.*`）
  由确定性代码计算；LLM 只提假设、解释与审查。
- A 股规则硬约束：T+1、100 股一手、涨跌停无法成交、停牌；模拟下单需人工审批。

## 研究流程
1. `market.snapshot` / `factor.indicators` 获取行情与指标。
2. 检查数据质量（缺失/复权/停牌/时间点）。
3. 形成带证据的结论；证据不足标记假设。
4. 需要策略时给出声明式 `StrategySpec` 并提交 `strategy.validate`。
5. 回测结论由 `backtest.run` 产出 `BacktestVerdict`（通过/拒绝及原因）。
6. 组合风险由 `portfolio.constraints` 校验；模拟下单走审批卡。

## 禁止
- 把 LLM 自由文本当事实；修改回测数字；绕过风险规则；实盘指令。
