<!-- kb:source=life-graph kb:sha=c43bb96 kb:branch=docs/knowledge-base-design kb:analysed=2026-07-21 -->
# Life Graph — Codebase Study Notes

Personal notes on **Life Graph** (repo: `Raceraja001/life-graph`).

- **Analysed:** 2026-07-21, at commit `c43bb96` (branch `docs/knowledge-base-design`)
- **Source repo:** `d:/DevTools/Projects/life-graph`
- **Related repos:** `uzhavu.race` (multi-tenant SaaS platform; its FastAPI AI engine calls Life Graph
  over HTTP as a client) — none of Life Graph's own code lives in that repo.

> File references below are relative to the repo root.

---

## The 60-second version

Life Graph is a personal "AI operating system": a brain-inspired memory service that gives AI
agents persistent, evolving memory (facts, decisions, beliefs, importance-scored and decaying
over time), plus a growing stack of "OS" layers on top — an agent kernel (personas, router,
scheduler, tasks), autonomous action-taking with approvals and trust scoring, watchers, a
judgment/calibration engine, and agent drivers that can actually execute work. It is solo-built,
self-hosted, for one developer's own use, not a multi-customer product today (though it is built
multi-tenant throughout).

Technically it's a single **FastAPI (Python 3.11+, async) monolith** (`life_graph/`) backed by
**PostgreSQL + pgvector** (relational rows + 768-dim embeddings in one DB) with **Apache AGE** for
graph/Cypher queries as a Postgres extension (no separate graph DB), **Redis** for rate limiting,
pub/sub event fan-out and the ARQ job queue, and **MinIO** for object storage (voice/image/doc
uploads). LLM calls are routed through **LiteLLM** to a mix of a local **LM Studio** endpoint and
cloud models (Gemini Flash/Pro, OpenRouter/DeepSeek) — `config.py:50-102` — biased toward the
cheapest model that will do, per the "LLM as advisor" design rule. A companion **Next.js 16 /
React 19 dashboard** (`dashboard/`) is a separate deployable that talks to the API. Auth is
service-to-service only: one `Authorization: Bearer <key>` checked against
`LIFE_GRAPH_SERVICE_API_KEYS` (`life_graph/api/auth.py`) — there is no end-user login, the caller
(e.g. a SaaS backend, or the dashboard itself) is trusted to assert `X-Tenant-ID`. Deployment is
`docker compose` (`app`, `worker`, `mcp`, `postgres`, `redis`, `minio` services) onto a self-hosted
VPS; locally, `.\start.ps1` drives the same stack via Docker + `uvicorn --reload` + `next dev`.
Background work runs as ARQ workers/cron (nightly consolidation, decay, trust decay, daily brief,
hourly watchers), plus outbound webhook delivery (HMAC-SHA256 signed, circuit-breaker after 10
consecutive failures per `KNOWLEDGE.md`). As of this commit there are **26 Alembic migrations**
(`alembic/versions/001`…`026`) — several eras newer than what `START_HERE.md`/`KNOWLEDGE.md`
describe as current (see Risks & gotchas).

```
                    Next.js dashboard (dashboard/, :3000)
                                  │ REST/WS
   ┌──────────────────────────────┼───────────────────────────────┐
   │              FastAPI app (life_graph/main.py, :8080)          │
   │  Middleware: RequestID → Auth → Tenant → RateLimit → Logging  │
   │  api/*.py routers → services/*.py → core/memory_manager.py    │
   │  kernel/ (personas, router, scheduler, tasks, projects)       │
   │  autonomy/ (safety, trust, approvals, audit, pipeline)        │
   │  extraction/ (rules → spaCy → LLM)  scoring/  drivers/        │
   └───────────────┬─────────────────┬──────────────────┬─────────┘
                    │                 │                  │
        PostgreSQL + pgvector    Redis (rate-limit,   MinIO (voice/
        + Apache AGE graph        pub/sub, ARQ jobs)   image/doc blobs)
                    │
        ARQ worker (workers/) — nightly consolidation 03:00 UTC,
        decay 04:00, trust decay 05:00, daily brief 02:00, hourly watchers
```

## Three things that will bite you first

1. **`tenant_id` isolation is a convention, not a guard rail.** `TenantMiddleware` reads the
   `X-Tenant-ID` header and sets a contextvar (`life_graph/core/tenant.py`,
   `get_current_tenant_id()` / `set_tenant_context()`); every query is *supposed* to filter by it.
   Nothing in SQLAlchemy or the DB enforces this — there's no row-level security, no base-query
   mixin that injects the filter automatically. A hand-written query that forgets
   `.where(Model.tenant_id == tenant_id)` compiles fine, returns data, and silently leaks across
   tenants. Nothing catches it short of a diligent reviewer.
2. **`metadata` is a reserved attribute on every SQLAlchemy declarative model** — `Base.metadata`
   (from `DeclarativeBase`, `life_graph/models/db.py:45`) already owns that name, so you cannot
   name a mapped column `metadata` directly. The codebase already hit this: `Project.scan_metadata`
   works fine, but `AgentPersona`'s equivalent column is declared as
   `extra_metadata: Mapped[dict] = mapped_column("metadata", ...)` (`models/db.py:1226-1227`) —
   Python attribute `extra_metadata`, real DB column `metadata`. If you add a new model and reach
   for `metadata` as the field name, it fails at import time, not obviously.
3. **Era-8 autonomy status/result values are locked in DB `CHECK` constraints that don't match
   intuition.** `alembic/versions/018_autonomous_ai.py` defines `ck_aq_status` (approval_queue:
   `pending/approved/rejected/expired/stale/batch_approved`), `ck_aa_status` (auto_actions:
   `pending/executing/success/failure/timeout/rolled_back/skipped` — **no** `pending_approval`),
   and `ck_al_result` (audit_log: `success/failure/timeout/rejected/expired/rolled_back`). The
   service code has to route around the gaps — `autonomy/pipeline/service.py:302,344` comments
   `# ck_aa_status has no 'pending_approval'` and falls back to `"pending"`;
   `autonomy/approvals/service.py:271` comments `# ck_aq_status has no 'auto_approved'` and uses
   `"approved"` instead. Writing an intuitively-named status yourself fails only at `INSERT` time,
   with a Postgres constraint-violation error, never at review time.

## Data model

Schema-less-by-design core: `memories.properties` is JSONB with dynamic `tags` arrays — no
hardcoded type/domain enums for facts. On top of that, 39 mapped classes in
`life_graph/models/db.py` alone (plus more in `life_graph/self_improving/models.py`), spanning
memory (`memories`, `sessions`, `intentions`, `knowledge_gaps`, `memory_sessions`), SaaS/tenant
plumbing (`tenant_configs`, `tenant_webhooks`, `tenant_usage`, `job_runs`), the OS kernel
(`agent_tasks`, `agent_sessions`, `agent_personas`, `scheduled_jobs`, `projects`,
`notifications`), and the newer eras (autonomy's `approval_queue`/`auto_actions`/`trust_scores`/
`audit_log`, capture, judgment, drivers). `KNOWLEDGE.md`'s "13 Tables" figure is from the pre-Era-4
snapshot and is stale — treat any in-repo count as a lower bound. Every table carries `tenant_id`;
migrations are owned centrally in `alembic/versions/`, one file per era, applied via
`python -m alembic upgrade head` (26 revisions as of this commit, `001` through `026`, the last
five — `022_trust_tiers`, `023_budget_spend`, `024_shadow_mode`, `025_embedding_dim`,
`026_approvals` — postdating what `START_HERE.md` describes).

## Core flows

- **Memory ingestion**: `life_graph/core/memory_manager.py` is the orchestrator. Content goes
  through `extraction/` (tiered: `rules.py` regex → `nlp.py` spaCy → `llm.py` fallback only when
  the first two score low), then dedup (SHA-256 exact match, then pgvector cosine ≥
  `settings.dedup_threshold` = 0.92 for near-duplicates, `config.py:67`), then
  `scoring/importance.py`, then storage.
- **Recall**: `services/recall.py` + `storage/hybrid.py` combine vector similarity and the AGE
  graph for hybrid search; proactive recall pushes relevant memories rather than waiting on a
  query, per the "no collector's fallacy" design principle in `KNOWLEDGE.md`.
- **Agent task routing**: `kernel/chief_router.py` does zero-LLM regex intent classification into
  8 intents, resolves an `agent_personas` row, and `kernel/process_manager.py` spawns an
  `agent_tasks` row; `api/kernel.py` exposes 25 endpoints across the six kernel phases.
  `kernel/scheduler.py` has its own built-in cron parser (no croniter/APScheduler dependency).
- **Autonomous action pipeline**: `autonomy/pipeline/service.py` classifies risk
  (`autonomy/*/safety` classifier), checks `trust_scores`, and either executes, queues an
  `approval_queue` row, or shadow-records to `auto_actions` with `status="skipped"` — every
  outcome writes to `audit_log`.
- **Background cycle**: ARQ (`workers/`) runs nightly consolidation (03:00 UTC, a 7-step
  cluster→dedup→distill→decay pipeline), decay sweep (04:00), trust decay (05:00, Era 8), a daily
  brief (02:00, configurable via `LIFE_GRAPH_BRIEF_HOUR_UTC`), and hourly watchers (Era 6). Jobs
  are registered in `workers/settings.py`.

## Patterns & conventions

Async everywhere (FastAPI + SQLAlchemy 2.0 `mapped_column` style), type hints and docstrings
expected on public APIs. New DB models go in `models/db.py` plus a matching Alembic migration
(`alembic revision --autogenerate -m "..."`), and always carry `tenant_id`. New cross-cutting
behavior should fire an event on the async `EventBus` (`core/events.py`, `EventType` enum —
confirmed to still be a plain `str, Enum` with dotted names like `memory:created`) and have
something subscribe, rather than services calling each other directly. Config is
`pydantic-settings` with `env_prefix = "LIFE_GRAPH_"` (`config.py:271`). Every response follows a
fixed envelope (`life_graph/api/responses.py`): success is `{"data": ..., "meta": {...}}`, errors
are `{"error": {"code", "message", "details"}}` — the global exception handler in `main.py` builds
the latter, so a handwritten error response that skips it will look inconsistent next to the rest
of the API. Tests use `httpx.AsyncClient` + `ASGITransport` (in-process, no server),
`@pytest_asyncio.fixture` with tenant headers, and are deliberately defensive — a 500 when
Postgres is unreachable is acceptable,
a 422 for valid input is not. `tests/conftest.py` mocks the `pgvector` SQLAlchemy type so unit
tests run without a real Postgres/pgvector install. The test suite is far larger than the docs
claim: roughly **900 test functions** across `tests/unit/` (33 files) and `tests/integration/`
(31 files), against `KNOWLEDGE.md`'s "213+ total integration tests" figure.

## Where to look for X

| I want to… | Look at |
|---|---|
| Trace a memory's full lifecycle | `life_graph/core/memory_manager.py` |
| Change extraction rules/thresholds | `life_graph/extraction/rules.py`, `nlp.py`, `llm.py` |
| Add an API endpoint | `life_graph/api/` — follow `memories.py`; register router in `main.py` |
| Add a DB model | `life_graph/models/db.py` + new file in `alembic/versions/` |
| Add a background job | `life_graph/workers/tasks.py` + register in `workers/settings.py` |
| Add an event type | `life_graph/core/events.py` — `EventType` enum |
| Understand middleware order | `life_graph/main.py:234-248` (RequestID→Auth→Tenant→RateLimit→Logging, then CORS added last/outermost) |
| Kernel/persona/router/scheduler work | `life_graph/kernel/`, API surface in `api/kernel.py` |
| Autonomy status vocab / CHECK constraints | `alembic/versions/018_autonomous_ai.py` |
| Run locally (full stack, Windows) | `.\start.ps1` (Postgres+Redis in Docker, uvicorn :8080, Next.js :3000) |
| Run just backend | `python -m uvicorn life_graph.main:app --reload --port 8080` |
| Lint/format | `ruff check life_graph/`, `ruff format life_graph/` |

## Where the project's own docs live

Unusually thorough for a solo project: `START_HERE.md` (onboarding + build-state table),
`KNOWLEDGE.md` (architecture/schema/decisions reference, last stamped "2026-07-07"), `AGENTS.md`
(agent conventions + inter-agent `.comms/` protocol), and 20 Kiro-style specs in `docs/specs/`
(one per era/feature, each with schemas/API contracts/code/task checklists), plus
`docs/design/01`–`09` (strategic decisions) and `docs/ARCHITECTURE.md`/`FEATURES.md`/
`QUICKSTART.md`/`OPERATIONS.md`. These docs are well-maintained relative to most codebases, but
this analysis already caught two concrete drifts — the migration count (docs describe up to `021`;
repo has 26, through `026_approvals`) and the test count (docs say 213+; repo has ~900 test
functions) — so treat them as a map, not as truth — verify against source before relying on a
detail.

## Risks & gotchas

- The three traps above (tenant filtering, `metadata` reserved name, Era-8 CHECK vocab) are the
  sharpest edges for someone extending the DB layer.
- Docs drift is real and measurable here (migration count, test count above) — this repo is
  actively worked by multiple agent sessions per `AGENTS.md`'s `.comms/` protocol, so state moves
  faster than the narrative docs get updated.
- `START_HERE.md` itself flags one already-fixed but instructive class of bug: `AgentTask.tags`
  was `nullable=True` with no ORM default while migration 017 made the column `NOT NULL DEFAULT
  '{}'` at the DB level — the ORM emitted explicit `NULL` and every `ProcessManager.spawn` failed
  against a migrated database. Worth remembering as a pattern (model default vs. migration default
  disagreement) when adding new NOT NULL columns with server defaults.
