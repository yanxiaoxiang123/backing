# Repository Guidelines

## Project Structure & Module Organization

The primary application is split into `backend/` and `frontend/`. FastAPI routes live in `backend/app/api/`, business logic in `backend/app/services/`, database code in `models/` and `schemas/`, migrations in `backend/migrations/`, and tests in `backend/tests/`.

The React/Vite client uses `frontend/src/pages/` for screens, `components/` for reusable UI, `services/api.ts` for API access, and `types/` and `utils/` for shared code.

Agent 工作台聊天（2026-08-18 规格 `docs/specs/2026-08-18-agent-workspace-chat.md`）：后端 `backend/app/agent_chat/`（`seam.py` Harness 接缝 + fake、`service.py` 单 worker FIFO、`stores.py` chat 仓库、`api.py` `/api/v1/agent-chats` 路由），前端 `frontend/src/components/chat/` 聊天 UI 与 `frontend/src/hooks/useAgentChat.ts`。数据表 `agent_chat_threads/turns/events`（迁移 `20260818_01`），run 经 `agent_runs.thread_id` 关联会话。 `TradingAgents-astock/` is a separate Python package with its own tests, CLI, and web app. Design notes are under `docs/`; deployment files are under `deploy/`. Do not edit generated `logs/`.

## Build, Test, and Development Commands

- `cd backend && pip install -r requirements.txt` installs backend dependencies (pinned; requires Python >=3.11, verified on 3.12; `mootdx` is installed from the vendored `vendor/mootdx` patch — keep that pin, never add the PyPI `mootdx` back).
- `cd backend && pip install -e ../TradingAgents-astock` installs the nested TradingAgents package required by the TA gateway bridge and its tests.
- `cd backend && pip install -r requirements.lock` installs the fully pinned environment (transitive closure); regenerate it with `pip freeze > requirements.lock` after dependency changes.
- `cd backend && alembic upgrade head` applies database migrations.
- `cd backend && python main.py` starts the API on port 8808.
- `cd backend && python task_worker.py` runs the Arq worker for background tasks (production multi-instance; requires `TASK_BACKEND=arq`, `REDIS_URL`, and `pip install -r requirements-arq.txt`). The default `TASK_BACKEND=threads` runs tasks in-process with the same DB-persisted lifecycle (idempotency keys, leases, retries, metrics).
- `cd backend && pytest` runs backend tests; add `-v` or a test path to focus.
- `cd backend && ruff check .` checks Python style.
- `cd frontend && npm ci` installs the locked frontend dependency set.
- `cd frontend && npm run dev` starts Vite; `npm run build` type-checks and bundles.
- `cd frontend && npm test` runs the Vitest + Testing Library unit/component tests; add `npm run test:watch` for watch mode.
- `cd TradingAgents-astock && pytest` runs the nested package suite.

## Agent 聊天与 DeepSeek Harness

- 聊天以 **seam-first** 构建：抽象 `HarnessChatSeam` + 确定性 `FakeHarnessChatSeam`（经 `agent_runtime` stores 真实创建 run 并发布 `run.linked`）；真实 `DeepSeekHarness` 适配器为后续切片（需运行时 + SDK + 密钥）。
- 后端单 worker FIFO 串行执行 turn（`HarnessChatService`，lifespan 启停）；重启将 running 标 `interrupted`、queued 继续；`Idempotency-Key` 去重。
- SSE `/api/v1/agent-chats/{thread_id}/events` 支持 `Last-Event-ID` 重放，空闲约 1.5s 自动关闭（前端自动重连）。
- 会话写入目录由 `DSH_SESSION_ROOT` 配置（默认 `backend/data/dsh_sessions`，见 `.env.example`）。
- DSH 运行时装配（固定 commit、Cordis profile、editable SDK/runtime 安装命令、`DEEPSEEK_API_KEY`/`QUANT_API_KEY`）：见 `dsh-quant-plugin/README.md`。不修改 `deepseek-harness/` 上游源码。

## Coding Style & Naming Conventions

Use four spaces in Python, type hints for public interfaces, `snake_case` for modules/functions, and `PascalCase` for classes. Keep handlers thin and domain behavior in services. TypeScript follows the existing two-space, semicolon-free style: components use `PascalCase.tsx`, hooks use `useCamelCase.ts`, and utilities use `camelCase`. Reuse shared API types.

## Testing Guidelines

Pytest is the primary framework. Name files `test_*.py` and tests `test_<behavior>`. Add regression tests alongside backend changes and reuse `backend/tests/conftest.py`. The nested package defines `unit`, `integration`, and `smoke` markers; mark external-service tests appropriately. No coverage threshold is configured, so cover affected branches and failure paths. Frontend changes must pass `npm run build`; manually verify changed UI behavior.

## Commit & Pull Request Guidelines

History uses Conventional Commit-style subjects, such as `feat: add screener agent API` and `fix: add polling timeout`. Keep commits focused with imperative summaries. PRs should explain the change, list verification commands, link issues, call out migrations or configuration changes, and include screenshots for UI changes.

## CI & Code Quality Gates

`.github/workflows/ci.yml` runs on every push/PR: backend (`ruff check` + `pytest`), nested TradingAgents tests, and frontend (`npm ci` → `npm run typecheck` → `npm run lint` → `npm run format:check` → `npm run build` → `npm test`). Treat these as PR-mandatory checks (enable the corresponding required status checks in branch protection). Run the same commands locally before pushing.

## Security Notes

- Never add `VITE_*` secret variables: they are statically inlined into the browser bundle. The frontend authenticates via the login page (one-time API key exchange for a short-lived HttpOnly session cookie + double-submit CSRF token).
- In production (`APP_ENV=production`) the server refuses to start unless `SESSION_SECRET` is set and `SESSION_HTTPS_ONLY=true`.

## Security & Configuration

Copy `backend/.env.example` to `.env`; never commit keys, credentials, databases, or logs. Document new variables in the example and README. Review authentication and rate limiting for new HTTP or WebSocket endpoints.
