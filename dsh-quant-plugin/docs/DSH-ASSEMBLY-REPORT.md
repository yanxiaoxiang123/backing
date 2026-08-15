# DSH 量化外壳装配报告（切片 11，2026-08-15）

> 固定 commit：`47f9438`（`deepseek-harness/` 克隆）；构建产物在克隆内（gitignored），
> 未改任何上游源文件。前身：`POC-REPORT.md`（HTTP 直连路径验证）。

## 完成内容（规格 v2 决策 2、25、26；US-2.10）

| 项 | 结果 |
|---|---|
| pnpm 安装 + 全量构建 | ✅ `pnpm install --frozen-lockfile` + `pnpm run build`（lib + web） |
| 单文件运行时 exe | ✅ `dsh-jsonrpc-agent-pkg-macos-arm64`（191.6 MB）+ spawn-helper，已同步到 `python/sdk-runtime/.../runtime/` |
| node carrier | ✅ `runtime/node/` 部署闭包（dev 模式 `DSH_RUNTIME_MODE=node` 可用） |
| Python SDK | ✅ `pip install -e python/sdk -e python/sdk-runtime`（`deepseek-harness-sdk` 0.0.0.dev0） |
| quant profile | ✅ `dsh-quant-plugin/cordis/quant.cordis.yml`：仅对话 + 会话持久化 + quant.gateway；移除 Bash/子进程/FS 编辑 |
| quant.gateway 插件 | ✅ `dsh-quant-plugin/cordis/plugins/quant-gateway/index.js`：Cordis 相对路径插件，HTTP → 后端 `POST /api/v1/tools/invoke`（X-API-Key）；parameters 手工编译为完整 JSON Schema |
| 后端网关端点 | ✅ `POST /api/v1/tools/invoke`：只读/策略权限；approval 工具 403（审批留在后端工作台） |
| session↔run 映射 | ✅ `quant_run_analysis` 从 DSH 会话创建真实 run（2 笔 completed，后端零错误） |
| 独立 UI | ⏳ 内置 web 资产已构建（`apps/web`）；驱动独立 UI 会话入口留待后续切片（SDK stdio 路径已验证，UI 走同一 runtime） |

## E2E 证据（live 后端 8808 + exe 运行时）

```
$ QUANT_API_KEY=<key> DEEPSEEK_API_KEY=<key> python scripts/sdk_demo.py "查询 sh.600000 最近 5 个交易日的日 K 线，并说明数据来源。"
>>> 查询 sh.600000 最近 5 个交易日的日 K 线，并说明数据来源。
<<< （模型调用 quant_kline → 网关 market.kline → 返回真实 K 线；模型输出日期/开高低收/成交量表格
     并说明数据来源为后端确定性行情服务，含 truncated 语义）
```

- 工具 schema 修复记录：裸 `ctx.tools.register()` 不编译 parameters，直发原始 spec 导致 DeepSeek
  API 400（"schema must be a JSON Schema of type: object"）→ 插件内手工编译 `{type:object, properties, required}`。
- 认证：`tools/invoke` 沿用 `X-API-Key`；无 key 401；approval 工具 403。

## 关键路径与后续

- 会话持久化：`DSH_SESSION_ROOT`（JSONL），断线恢复走 checkpoint 策略。
- 预算分界（规格开放问题）：DSH 管对话轮次（每轮工具调用经网关、参数校验），LangGraph 管量化预算。
- 后续：独立 Web UI 会话入口（复用构建好的 web 资产）；approval 卡在 DSH 侧的可视化（当前审批留在后端工作台，US-2.10 以 backend 审批卡满足）。
