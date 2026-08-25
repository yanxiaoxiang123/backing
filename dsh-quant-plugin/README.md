# dsh-quant-plugin — DeepSeek Harness 量化插件（历史 POC）

> 当前 backend Agent 工作台不再使用本目录。生产聊天 runtime 已迁移到
> `backend/app/agent_chat/runtime.py`，不会导入、复制或启动 `deepseek-harness/`
> 及本插件；以下内容仅用于历史 POC 复现。

> 固定 DSH commit：`47f9438`（由 `scripts/bootstrap_deepseek_harness.sh` 拉取到本地 `../deepseek-harness/`，不修改克隆本体，
> 仅构建产物落克隆内 gitignored 目录）。状态：**运行时装配完成并 E2E 验证**（见 `docs/DSH-ASSEMBLY-REPORT.md`）。

## 边界（规格决策 2、26）

- 插件只调用 FastAPI Tool Gateway / agent-runs API，**不直连数据库**。
- 默认移除 Bash、编辑器与宿主文件工具；只暴露只读量化工具（approval 下单留在后端工作台审批）。
- `session_id ↔ run_id` 映射由后端保存；run 事件可在后端 SSE 重放。

## 目录

```text
dsh-quant-plugin/
  cordis/quant.cordis.yml            # 运行时 profile（对话 + 会话持久化 + quant.gateway）
  cordis/plugins/quant-gateway/      # 量化工具消费者（相对路径 Cordis 插件，HTTP → 网关）
  skills/astock-research.md          # A 股研究 skill（上下文）
  scripts/gateway_probe.py           # HTTP 直连探针（回归）
  scripts/sdk_demo.py                # SDK 对话演示（K 线查询 + 发起分析 run）
  docs/POC-REPORT.md                 # 早期 POC 结论（HTTP 直连路径）
  docs/DSH-ASSEMBLY-REPORT.md        # 装配报告与 E2E 证据
```

## 历史 POC 启动路径（不用于当前 backend）

1. 准备并构建 DSH runtime：

```bash
./scripts/bootstrap_deepseek_harness.sh
cd ../deepseek-harness
pnpm install --frozen-lockfile
pnpm run build
```

   再
   `pnpm exec tsx scripts/build-exe-for-python-sdk.ts --skip-build --targets=node24-<平台>-<arch>`，
   产出 `dsh-jsonrpc-agent-pkg-*` 并同步进 `python/sdk-runtime/.../runtime/`）。
2. `pip install -e ../deepseek-harness/python/sdk -e ../deepseek-harness/python/sdk-runtime`。
3. 启动旧 POC 后端：`cd backend && python main.py`（端口 8808，`X-API-Key` 认证；含 `POST /api/v1/tools/invoke`）。
   当前生产 Agent 聊天不使用本 POC；请使用 `AGENT_CHAT_BACKEND=native`，上下文由 `agent_chat_threads/turns/events` 管理。
4. 运行对话演示（环境变量注入密钥，不入库）：

```bash
cd dsh-quant-plugin
export QUANT_API_KEY=<后端 API_KEY>
export DEEPSEEK_API_KEY=<模型 API_KEY>
python scripts/sdk_demo.py "查询 sh.600000 最近 5 个交易日的日 K 线，并说明数据来源。"
python scripts/sdk_demo.py "用 quant_run_analysis 发起：生成 ma_cross 策略并回测验证 sh.600000"
```

5. dev 模式可用 `DSH_RUNTIME_MODE=node`（node carrier）代替 exe。

## 演示工具

| 工具 | 后端 | 说明 |
|---|---|---|
| `quant_kline` | `market.kline` | 日 K 线（证据五元组） |
| `quant_financials` | `fundamental.financials` | 财报摘要 |
| `quant_run_analysis` | `POST /agent-runs` | 自然语言 → Supervisor run（session↔run 映射） |
