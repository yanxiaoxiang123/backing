# dsh-quant-plugin — DeepSeek Harness 量化插件（POC）

> 固定 DSH commit：`47f9438`（`/Users/yan/Desktop/backing/deepseek-harness/`，不修改克隆本体）
> 状态：**POC 骨架 + HTTP 直连验证通过**；DSH 运行时构建与插件装配列为后续切片（见 `docs/POC-REPORT.md`）

## 边界（规格 §3）

- 插件只调用 FastAPI Tool Gateway / agent-runs API，**不直连数据库**。
- 默认移除 Bash、编辑器与宿主文件工具；研究代码实验只能在隔离 Sandbox 执行。
- `session_id ↔ run_id` 映射由后端保存；run 事件可在后端 SSE 重放。

## 目录

```text
dsh-quant-plugin/
  profile/quant.cordis.yml   # 固定 profile（草案：禁 Bash/FS 编辑，预留工具装配）
  skills/astock-research.md  # A 股研究 skill（上下文）
  scripts/gateway_probe.py   # HTTP 直连探针：创建 run + 回放事件（已通过）
  docs/POC-REPORT.md         # POC 结论与后续步骤
```

## 启动路径（完整版，待运行时构建后）

1. 构建 DSH runtime（`deepseek-harness/`：`pnpm install && pnpm run build`，产出
   `dsh-jsonrpc-agent-pkg-macos-arm64`）。
2. `pip install -e deepseek-harness/python/sdk -e deepseek-harness/python/sdk-runtime`。
3. 启动后端：`cd backend && python main.py`（端口 8808，`X-API-Key` 认证）。
4. 用 SDK 加载本 profile 运行对话任务；quant 工具经网关装配。

## 当前可验证路径（HTTP 直连）

```sh
cd backend && python main.py &        # 启动后端
python dsh-quant-plugin/scripts/gateway_probe.py   # 创建 run → 回放事件
```

验证命令与输出记录在 `docs/POC-REPORT.md`。
