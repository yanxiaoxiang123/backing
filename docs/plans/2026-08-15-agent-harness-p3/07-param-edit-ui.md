# 07 前端参数编辑 → 新 run

**交付**：工作台回测页签可编辑策略参数（均线窗口、股票池等）并提交新 run；新 run 生成新 `run_id`；旧回测与产物不可变可查。

**范围**：
- BacktestPanel 增加参数编辑表单（基于 `StrategySpec` 字段），提交调用 run 创建 API 并跳转/刷新到新 run 流。
- 参数非法（越界/缺字段）就地校验提示，不发请求。
- 旧 run 视图只读展示，无覆盖写路径。

**验收**：
- Vitest：编辑→提交创建新 run_id、旧产物不变、非法参数拦截。
- `npm run build` 全绿；手动：改参数提交后新 run 在 timeline 可见。

**阻塞**：None
**委派**：eligible（纯前端，API 接缝已稳定）
