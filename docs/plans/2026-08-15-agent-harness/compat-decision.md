# 依赖兼容性结论（任务 01）

> 日期：2026-08-15
> 结论：**单环境对齐可行**，无需隔离进程。统一运行时与 `TradingAgents-astock` 可在同一 conda `backing` 环境共存。

## 版本矩阵（已固定）

| 包 | 版本 | 说明 |
|---|---|---|
| langchain-core | 1.5.4 | 保持既有锁定版本不变 |
| langchain-openai | 1.5.1 | DeepSeek 经 base_url 接入 |
| langgraph | 1.2.11 | 量化运行时 |
| langgraph-checkpoint-sqlite | 3.1.1 | SQLite checkpointer |
| openai / tiktoken | 3.1.0 / 0.13.0 | 传递依赖 |
| websockets | 15.0.1 | pip 自动从 17.0.1 降级（uvicorn[standard] 兼容） |

## 兼容性证据

1. `TradingAgents-astock` 0.2.4 在 langgraph 1.2.11 / langchain-core 1.5.4 下 `tests/test_checkpoint_resume.py`：**3 passed**（图构建 + SQLite checkpoint resume 全通过）。
2. 主后端全量 pytest：**195 passed**（含新增 domain 测试；websockets 降级无破坏）。
3. 主后端依赖经 `pip install -e TradingAgents-astock --no-deps` + 补齐图链路运行时依赖（yfinance/stockstats/backtrader/typer/rich/questionary/parsel/python-dotenv/tqdm）后，`import tradingagents.graph.trading_graph` 成功。

## 期间修复

- `TradingAgents-astock/pyproject.toml` 打包元数据缺陷：`dependencies` 列表错误地放在 `[project.urls]` 段内（`project.urls.dependencies must be string` 构建失败），已移回 `[project]` 段并恢复 `[project.urls]` 四行 URL 元数据。
- `backend/requirements.txt` 增加 langgraph 栈三直依赖；`requirements.lock` 已按 `pip freeze --exclude-editable` 重新生成（editable 包不进 lock，避免机器相关路径）。

## 已知边界（记录在案）

- 嵌套套件 `tests/test_google_api_key.py` 收集期需要 `langchain_google_genai`（及其余可选 provider：anthropic/experimental）。这些是**可选 LLM 客户端**，统一运行时只用 DeepSeek（langchain-openai），不安装以免与 langchain-core 1.5.4 冲突。嵌套套件全绿不是统一运行时验收项；如需验证可选 provider，应在独立环境进行。
- TradingAgents 的 streamlit/fpdf2 等仅 web/CLI 使用，统一运行时不需要，未安装。
- 深度回迁（v0.3.1 决策日志、前视过滤等）仍按任务 09 之后的独立切片处理，需先写差异测试。

## 对后续任务的影响

- 任务 05（Runtime 核心）与任务 09（Supervisor 图）：TradingAgents 图可在同一进程经统一 facade 注入 checkpointer 与事件发射器。
- 任务 07（旧端点 adapter）：无需隔离进程。
- 若未来升级 langchain-core 大版本，必须先重跑 `test_checkpoint_resume.py` 与后端全量 pytest。
