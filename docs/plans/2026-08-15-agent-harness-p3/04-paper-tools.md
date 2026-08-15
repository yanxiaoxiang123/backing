# 04 execution.paper.* 工具域

**交付**：`execution.paper.propose_order`（提议订单→创建订单+审批卡）、`cancel_order`、`positions`、`account`、`orders` 五个网关工具；权限 = 需人工审批。

**范围**：
- propose_order：输入声明式订单（方向/代码/数量/限价/触发条件），输出订单 id + 待审批状态；高风险操作出现在工作台审批卡。
- 数量/限价/代码严格校验；无审批任何订单不成交（撮合层拒绝 pending 订单）。
- 查询类只读（positions/account/orders），返回统一 envelope。
- tool_call 落库关联 run/step；审批关联 approval 记录。

**验收**：
- pytest：propose/cancel/查询路径、参数校验、权限拒绝（无审批标记）、tool_call 记录关联。
- 既有网关测试全绿。

**阻塞**：03
**委派**：ineligible（网关+权限耦合）
