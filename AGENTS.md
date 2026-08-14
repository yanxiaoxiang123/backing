# Repository Guidelines

## Project Structure & Module Organization

The primary application is split into `backend/` and `frontend/`. FastAPI routes live in `backend/app/api/`, business logic in `backend/app/services/`, database code in `models/` and `schemas/`, migrations in `backend/migrations/`, and tests in `backend/tests/`.

The React/Vite client uses `frontend/src/pages/` for screens, `components/` for reusable UI, `services/api.ts` for API access, and `types/` and `utils/` for shared code. `TradingAgents-astock/` is a separate Python package with its own tests, CLI, and web app. Design notes are under `docs/`; deployment files are under `deploy/`. Do not edit generated `logs/`.

## Build, Test, and Development Commands

- `cd backend && pip install -r requirements.txt` installs backend dependencies (pinned; requires Python >=3.11, verified on 3.12; `mootdx` is installed from the vendored `vendor/mootdx` patch — keep that pin, never add the PyPI `mootdx` back).
- `cd backend && pip install -r requirements.lock` installs the fully pinned environment (transitive closure); regenerate it with `pip freeze > requirements.lock` after dependency changes.
- `cd backend && alembic upgrade head` applies database migrations.
- `cd backend && python main.py` starts the API on port 8808.
- `cd backend && pytest` runs backend tests; add `-v` or a test path to focus.
- `cd backend && ruff check .` checks Python style.
- `cd frontend && npm ci` installs the locked frontend dependency set.
- `cd frontend && npm run dev` starts Vite; `npm run build` type-checks and bundles.
- `cd frontend && npm test` runs the Vitest + Testing Library unit/component tests; add `npm run test:watch` for watch mode.
- `cd TradingAgents-astock && pytest` runs the nested package suite.

## Coding Style & Naming Conventions

Use four spaces in Python, type hints for public interfaces, `snake_case` for modules/functions, and `PascalCase` for classes. Keep handlers thin and domain behavior in services. TypeScript follows the existing two-space, semicolon-free style: components use `PascalCase.tsx`, hooks use `useCamelCase.ts`, and utilities use `camelCase`. Reuse shared API types.

## Testing Guidelines

Pytest is the primary framework. Name files `test_*.py` and tests `test_<behavior>`. Add regression tests alongside backend changes and reuse `backend/tests/conftest.py`. The nested package defines `unit`, `integration`, and `smoke` markers; mark external-service tests appropriately. No coverage threshold is configured, so cover affected branches and failure paths. Frontend changes must pass `npm run build`; manually verify changed UI behavior.

## Commit & Pull Request Guidelines

History uses Conventional Commit-style subjects, such as `feat: add screener agent API` and `fix: add polling timeout`. Keep commits focused with imperative summaries. PRs should explain the change, list verification commands, link issues, call out migrations or configuration changes, and include screenshots for UI changes.

## Security & Configuration

Copy `backend/.env.example` to `.env`; never commit keys, credentials, databases, or logs. Document new variables in the example and README. Review authentication and rate limiting for new HTTP or WebSocket endpoints.
