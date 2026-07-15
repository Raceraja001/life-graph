# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Orientation

Life Graph is a brain-inspired memory + agent "AI operating system": a multi-tenant FastAPI
backend (`life_graph/`) with a Next.js dashboard (`dashboard/`). Before designing features, read
the deeper onboarding docs, which are kept current and authoritative:

- **START_HERE.md** — current build state, what's done vs. spec'd, verified roadmap table.
- **KNOWLEDGE.md** — full architecture, DB schema, event list, design decisions, "you want to… look at…" file map.
- **AGENTS.md** — developer preferences, code conventions, spec-driven build order, inter-agent `.comms/` protocol.
- **docs/specs/** — Kiro-style specs (SQL, API contracts, code, task checklists) for each phase/era.

Note the two names: the Python **package** is `life_graph/` (underscore); the git repo root is `life-graph/`
(hyphen). The untracked `life-graph/` subfolder is a stray `.claude` dir — ignore it.

## Common commands

Backend (Python 3.11+, run from repo root; `python` = your venv):

```bash
pip install -e ".[dev]"              # install (optional extras: ".[dev,multimodal]")
python -m alembic upgrade head       # apply migrations (21 revisions in alembic/versions/)
python -m alembic revision --autogenerate -m "add <feature> tables"
python -m uvicorn life_graph.main:app --host 0.0.0.0 --port 8080 --reload --reload-dir life_graph
ruff check life_graph/               # lint (line-length 100, double quotes)
ruff format life_graph/              # format
pytest tests/ -v                     # all tests
pytest tests/unit/ -v                # unit only (no DB needed — pgvector is mocked in conftest)
pytest tests/integration/ -v         # integration
pytest tests/integration/test_kernel_router.py::test_name -v   # single test
```

Dashboard (`dashboard/`, Next.js 16 / React 19):

```bash
npm run dev      # :3000
npm run build
npm run lint     # eslint
```

Full local stack (Windows/PowerShell — the developer's primary workflow):

```powershell
.\start.ps1          # Postgres+Redis in Docker, uvicorn on :8080, Next.js on :3000
.\start.ps1 -Infra   # only Postgres + Redis; also -Backend / -Dashboard / -All
.\stop.ps1 ; .\status.ps1
```

Docker: `docker compose up -d` runs `app`, `worker` (ARQ), `mcp`, `postgres`, `redis`, `minio`.
Health check: `curl http://localhost:8080/health` (deep — checks DB + Redis, 503 if critical).
API docs at `/docs`. Config is via env vars prefixed `LIFE_GRAPH_` (see `life_graph/config.py`, `.env.example`).

## Architecture (the big picture)

Request flow through a **5-layer middleware stack** (declared bottom-to-top in `main.py`, executes
top-to-bottom): `RequestID → Auth → Tenant → RateLimit → Logging`. `TenantMiddleware` reads the
`X-Tenant-ID` header into a contextvar (`core/tenant.py`); **every DB query must filter by `tenant_id`.**

Layered structure inside `life_graph/`:

- **`api/`** — routers grouped by domain; `main.py` wires them and runs a large `lifespan` startup
  that registers tools, seeds personas, and *subscribes* services to the EventBus. `api/dependencies.py`
  holds DI providers (`Depends()`).
- **`core/memory_manager.py`** — the primary ingestion orchestrator; trace a memory's life through here.
- **`extraction/`** — the 3-tier pipeline (`rules.py` regex → `nlp.py` spaCy → `llm.py` fallback).
  The guiding rule is **LLM as advisor, not authority**: ~85% of operations are rule-based/local; an
  LLM call happens only when tiers 1–2 score low. Prefer this pattern when adding logic.
- **`scoring/`** — importance tiers, recall ranking, exponential decay.
- **`services/`** — business logic injected via `Depends()`.
- **`storage/`** — PostgreSQL + pgvector (relational + 768-dim vectors), Apache AGE (Cypher graph as
  a Postgres extension), Redis, MinIO. `storage/hybrid.py` combines graph + vector search.
- **`workers/`** — ARQ background jobs & cron (nightly consolidation 03:00 UTC, decay 04:00, daily
  brief, hourly watchers, etc.). Register new jobs in `workers/settings.py`.
- **`core/events.py`** — async `EventBus` (pub/sub, `EventType` enum). Events bridge to Redis for
  cross-instance fan-out, then to webhook delivery (HMAC-signed) and WebSocket relay.

Built on top of the memory core are the "OS" layers, each backed by its own Alembic migration and
spec — `kernel/` (process manager, personas, router, scheduler, projects, notifications),
`agents/` + `tools/` (`@tool` decorator, OpenAI function-calling), plus eras: `self_improving/`,
`watchers/`, `autonomy/`, `drivers/` (agent execution), capture (`services/capture*.py`), and
judgment (`services/judgment.py`). START_HERE.md maps each migration (014–021) to its module.

Two design invariants worth internalizing: the core is **schema-less** (facts live in a JSONB
`properties` column with dynamic tag arrays — no hardcoded type/domain enums), and behavior is
**event-driven** — for new cross-cutting features, fire an event and subscribe, rather than calling
services directly.

## Conventions

- Async everywhere (FastAPI + SQLAlchemy 2.0 `mapped_column` style); type hints and docstrings on public APIs.
- Adding a model: edit `models/db.py` **and** create an Alembic migration; always include `tenant_id`.
- New memories should flow through the dedup pipeline (SHA-256 exact + pgvector cosine ≥ 0.92, threshold `LIFE_GRAPH_DEDUP_THRESHOLD`).
- Test pattern: `httpx.AsyncClient` + `ASGITransport` (in-process, no running server) with
  `@pytest_asyncio.fixture` and tenant headers. Tests are defensive — they accept 500 when the DB is
  unreachable but must not accept 422 for valid input. `conftest.py` mocks pgvector so unit tests run without Postgres.
- The developer works solo on Windows, self-hosts, is cost-conscious (favors cheap models like Gemini
  Flash/DeepSeek), and asks to **approve implementation plans before you start building**.
