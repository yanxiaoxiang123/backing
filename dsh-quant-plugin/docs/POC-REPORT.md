# DSH POC 报告（任务 11）

> 日期：2026-08-15
> 固定 commit：`47f9438`（`deepseek-harness/` 克隆，未修改本体）
> 结论：**HTTP 直连路径已验证通过**；DSH 运行时构建与插件装配列为后续切片。

## 1. 发现（SDK 可用性）

| 项 | 结果 |
|---|---|
| Python SDK（deepseek-harness-sdk） | PyPI **无发布版本**（`pip index versions` 无匹配） |
| sdk-runtime 二进制 | 克隆内**无预编译** `dsh-jsonrpc-agent-pkg-*`，需源码构建 |
| 平台支持 | macOS arm64 受支持（`macosx_14_0_arm64`） |
| 构建前置 | 需要 pnpm + 整个 harness workspace 构建（当前无 pnpm） |

因此 SDK 无法在不动克隆本体的情况下直接安装运行——构建整个 harness runtime 是独立的大切片。

## 2. 决策（执行约定 5 的回退路径）

- **本轮交付**：`dsh-quant-plugin/` POC 骨架 + **HTTP 直连验证**（DSH 插件将来调用的后端 HTTP 面）。
- **延后**：DSH bundled runtime 构建、独立 Web UI 启动、工具审批卡端到端、session↔run 映射实测。
- profile（`quant.cordis.yml`）为装配草案：禁 Bash/FS 编辑、预留 quant.gateway 工具消费者（TS 插件），运行时构建后逐项校验。

## 3. 探针证据（live 后端实测，2026-08-15）

后端 `python main.py`（8808）启动后，`scripts/gateway_probe.py`（X-API-Key 认证）：

```
[1] 创建 run: 6899e5c862084318 status=completed
[2] run 状态: completed 目标: 研究 sh.600000 趋势
[3] SSE 事件:
    step seq=1 node=supervisor status=completed
    step seq=2 node=data_qa status=completed
    tool market.snapshot status=ok
    step seq=3 node=research status=completed
    tool factor.indicators status=ok
    step seq=4 node=portfolio_risk status=completed
    tool portfolio.constraints status=ok
    合计: 4 节点事件, 3 工具事件
[4] artifacts: 0 条
探针通过 ✓
```

## 4. 与任务 11 验收标准对照

| 验收项 | 状态 |
|---|---|
| 一键启动独立 UI 并完成"查 K 线 → 发起分析 run"对话闭环 | ⏳ 待运行时构建（HTTP 路径已验证） |
| 插件只经 FastAPI 网关（无直连库）；只读工具可用 | ✅ 网关/agent-runs API 直连验证通过 |
| 审批流程可演示（拒绝终止） | ⏳ 审批卡前端组件已交付（任务 10），DSH 端到端待运行时 |
| session↔run 映射可查、事件可 SSE 重放 | ✅ 事件 SSE 回放验证通过；映射表字段已入 `agent_runs.thread_id` |
| 不修改上游克隆本体 | ✅（外部 profile 方式） |

## 5. 后续切片（DSH 运行时装配）

1. 在 `deepseek-harness/` 安装 pnpm 并执行 `pnpm install && pnpm run build`，产出
   `dsh-jsonrpc-agent-pkg-macos-arm64`（独立大任务，需单独验证）。
2. `pip install -e python/sdk -e python/sdk-runtime`，跑通官方 `examples/jsonrpc-agent/minimal.py`。
3. 编写 quant.gateway 工具消费者（Cordis TS 插件，装配到 `quant.cordis.yml`），
   把 `market.*`/`factor.*`/`backtest.*` 等网关工具暴露给对话代理；移除 Bash/FS 编辑。
4. 校验：独立 UI 启动、工具审批卡、session↔run 映射与 SSE 恢复。
