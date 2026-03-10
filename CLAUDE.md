# CLAUDE.md

This file provides guidance to Claude when working with code in this repository.

## Project Layout

```
aws-cost-dashboard/
├── .env.example             ← Template for all environment variables (copy → .env)
├── .env.production          ← Production config (single source of truth — DO NOT commit secrets)
├── docker-compose.yml       ← Dev stack (postgres + redis + backend + hot-reload)
├── docker-compose.prod.yml  ← Production stack (reads .env.production)
├── docker-compose.test.yml  ← Ephemeral test stack (CI)
├── backend/                 ← FastAPI application
│   └── app/
│       ├── api/v1/          ← Route handlers
│       ├── services/        ← Business logic
│       ├── models/          ← SQLAlchemy ORM models
│       ├── schemas/         ← Pydantic request/response schemas
│       └── config.py        ← Settings (all values sourced from env vars)
├── frontend/                ← React + Vite application
│   └── src/
├── tests/                   ← Standalone test project (separate from application code)
│   ├── pytest.ini           ← Test config (pythonpath points to ../backend)
│   ├── conftest.py          ← Shared fixtures
│   ├── requirements-test.txt
│   ├── test_api/
│   ├── test_aws/
│   ├── test_core/
│   ├── test_schemas/
│   └── test_services/
└── scripts/
    └── build-prod.sh        ← Builds both Docker images from .env.production
```

---

## Common Commands

### Development

| Task | Command | Notes |
|------|---------|-------|
| **Start dev stack** | `docker-compose up --build` | Postgres + Redis + backend (hot-reload). Copy `.env.example` → `.env` first. |
| **Backend only** | `cd backend && uvicorn app.main:app --reload --port 8000` | Requires local Postgres & Redis. |
| **Frontend only** | `cd frontend && npm install && npm run dev` | Vite dev server on port 5173. |
| **Lint** | `cd backend && flake8 .` | Python linting. |
| **Type check** | `cd backend && mypy .` | Static type checking. |

### Testing (from `tests/` directory)

| Task | Command | Notes |
|------|---------|-------|
| **Run all tests** | `cd tests && python -m pytest` | Requires Postgres & Redis running (or use Docker below). |
| **Run single file** | `cd tests && python -m pytest test_api/test_health.py` | |
| **Run by marker** | `cd tests && python -m pytest -m unit` | `unit`, `integration`, `slow`, `aws` |
| **Skip slow tests** | `cd tests && python -m pytest -m "not slow and not aws"` | Fast feedback loop. |
| **Docker test run** | `docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit` | Fully isolated — no local deps needed. |
| **Frontend tests** | `cd frontend && npm test` | Vitest unit tests. |

### Production

| Task | Command | Notes |
|------|---------|-------|
| **Build images** | `./scripts/build-prod.sh` | Reads all config from `.env.production`. |
| **Build + push** | `./scripts/build-prod.sh --push` | Builds and pushes to `$DOCKER_REGISTRY`. |
| **Deploy** | `docker-compose -f docker-compose.prod.yml --env-file .env.production up -d` | |
| **DB migrations** | `cd backend && DATABASE_URL=<url> alembic upgrade head` | |

---

## Configuration — Single Source of Truth

**All environment-specific values live in `.env.production`** (or `.env` for development).
Nothing else needs to be edited before deploying.

| File | Purpose |
|------|---------|
| `.env.example` | Template with every supported variable and documentation |
| `.env.production` | Production values — fill before first deploy |
| `.env` (gitignored) | Local development override — copy from `.env.example` |
| `backend/app/config.py` | Pydantic `Settings` class — maps env vars to typed fields |
| `frontend/.env.production` | Fallback for `npm run build` outside Docker; Docker uses build args |

### Adding a new config variable
1. Add it to `.env.example` with a comment.
2. Add it to `.env.production` with the production value.
3. Add the field to `backend/app/config.py` (`Settings` class) with a safe default.
4. If it's a frontend (Vite) variable, prefix it `VITE_` and add `ARG`/`ENV` to `frontend/Dockerfile.prod`.

---

## High-Level Architecture

**Backend** — FastAPI (`backend/app/`)
- Routes in `app/api/v1/` grouped by domain: `aws_accounts`, `budgets`, `costs`, `export`, `finops`, `kpi`, `rightsizing`, etc.
- Services in `app/services/` handle business logic, AWS SDK calls, forecasting, audit, scheduler.
- SQLAlchemy + PostgreSQL for persistence; Redis for response caching.
- Background jobs via APScheduler (`app/services/scheduler_service.py`).
- JWT authentication via Python-Jose; secrets loaded from env.

**Frontend** — React + TypeScript + Vite (`frontend/src/`)
- Tailwind CSS, TanStack Query, Recharts, Zustand.
- Axios client in `src/api/axios.ts` — base URL from `VITE_API_BASE_URL`.

**Tests** — Standalone project at `tests/`
- pytest with `pythonpath = ../backend` so `app.*` imports resolve without installing the package.
- In-memory SQLite + fakeredis for unit tests; real Postgres/Redis for integration tests.
- Coverage reports written to `coverage/` at the project root.

**Docker**
- `docker-compose.yml` — dev (hot-reload, mounts source code).
- `docker-compose.prod.yml` — production (pre-built images, `env_file: .env.production`).
- `docker-compose.test.yml` — ephemeral CI test environment (no persistent volumes).

---

## Quick Navigation

- `backend/app/main.py` — FastAPI entry point
- `backend/app/api/v1/router.py` — Main router
- `backend/app/config.py` — All settings (env-var driven)
- `backend/app/services/` — Business logic
- `frontend/src/` — UI source
- `tests/conftest.py` — Shared test fixtures
- `scripts/build-prod.sh` — Production image builder
- `.env.production` — **Start here when deploying**

---

*Update this file whenever the project structure or build process changes.*
