# Life Graph — New Agent Start Here

> **READ THIS FIRST.** This file tells you everything you need to know to start working on Life Graph.

## What Is This Project?

Life Graph is an **AI Operating System** — an always-running personal AI assistant built with FastAPI + PostgreSQL. It's not just a memory service. It manages agents, tools, watchers, and learns from every interaction.

## Current State (Updated: July 11, 2026)

### ✅ What's Built
- **Memory System** — 45 endpoints, pgvector, Apache AGE knowledge graph, events, dedup, decay
- **Agent Orchestrator** — LLM tool-calling loop with SSE streaming, retry, fallback model
- **10 Agent Tools** — calculator, datetime, web_search, terminal, git (status/log/diff/branch), browser (httpx + browser-use)
- **Tool Registry** — `@tool` decorator, OpenAI function-calling format
- **Event Bus** — pub/sub with Redis bridge
- **Plugin System** — PluginManager, hot-loadable
- **MCP Server** — IDE integration
- **CLI** — `life-graph` command
- **WebSocket** — real-time streaming
- **Multi-tenant** — `tenant_id` on every query
- **OS Kernel (Phase A)** — 25 endpoints, 126 tests, 6 DB tables. See details below.
- **Era 4 — Personal AI** — migration `014`; advisor, evidence, research, preferences, transcript-ingest APIs (`api/advisor.py`, `api/evidence.py`, `api/research.py`, `api/preferences.py`, `api/ingest_transcript.py`) + integration tests
- **Era 5 — Self-Improving** — migration `015`; `life_graph/self_improving/` (prompt versions, eval scorer/service, optimizer, nightly cron, dashboard service) + tests
- **Era 6 — Ambient AI** — migration `016`; `life_graph/watchers/` (server health, dependency, code quality, tech radar watchers; digest; notification channels; scrapers) + tests
- **Era 7 — Agent Networks** — migration `017`; agent workflows/tasks/messages/context/internal-sync APIs + `test_agent_networks.py`
- **Era 8 — Autonomous AI** — migration `018`; `life_graph/autonomy/` (levels, safety classifier, trust calculator, approvals, audit, pipeline executor) + `test_autonomy.py`
- **Capture Spine (Phase G)** — migration `019`; `services/capture.py`, `services/capture_processors.py`, `api/capture.py`, corrections + interview_questions tables + `test_capture_processors.py`
- **Judgment Engine (Phase H)** — migration `020`; `services/judgment.py`, `services/outcome_resolver.py`, `services/adversarial_advisor.py`, `services/multi_model_advisor.py`, `scoring/calibration.py`, `api/judgment.py` + `test_calibration.py`
- **Agent Drivers (Phase I)** — migration `021`; `life_graph/drivers/` (base protocol, registry, local driver, dispatcher with WIP limits + bounce-once, context packets), `services/verifiers.py`, `services/results_loop.py`, `api/drivers.py`
- **Dashboard** — Next.js 16 / React 19 app (`dashboard/`) with memories, tasks, decisions, calibration, drivers, activity, settings pages

### ✅ OS Kernel — COMPLETE (All 7 Phases)

Built from `docs/specs/os-kernel.md`. **Do not rebuild these.** All code is in `life_graph/kernel/`.

| Phase | Module | Endpoints | Tests |
|:------|:-------|:---------:|:-----:|
| 1. Process Manager | `kernel/process_manager.py` | 4 | 15 |
| 2. Agent Personas | `kernel/personas.py` | 5 | 23 |
| 3. Chief Router | `kernel/chief_router.py` | 3 | 25 |
| 4. Scheduler | `kernel/scheduler.py` | 5 | 25 |
| 5. Project Registry | `kernel/project_registry.py` | 5 | 22 |
| 6. Notification Engine | `kernel/notification_engine.py` | 3 | 16 |
| 7. Integration & Polish | KNOWLEDGE.md, .env.example | — | — |

**Key kernel files:**
- API: `life_graph/api/kernel.py` (25 endpoints)
- DI: `life_graph/api/dependencies.py` (6 kernel providers)
- Models: `life_graph/models/db.py` (AgentTask, AgentSession, AgentPersona, ScheduledJob, Project, Notification)
- Migrations: `011_os_kernel.py`, `012_scheduled_jobs.py`, `013_projects_notifications.py`
- Tests: `tests/integration/test_kernel_*.py` (6 files, 73 pass / 53 skip without DB)

**Design decisions:**
- Zero-LLM regex intent classification (ChiefRouter) — 8 intents
- Built-in cron parser (no APScheduler/croniter dependency)
- Built-in project scanner (os.walk + subprocess git)
- Auto-disable scheduler after 3 consecutive failures

### 🗺️ Roadmap Status (verified against code, July 11, 2026)

All major phases are **implemented** (migrations 014–021, routers registered in `main.py`, tests in `tests/`):

| Phase | Spec | Status |
|:------|:-----|:-------|
| A | OS Kernel (`os-kernel.md`) | ✅ Done |
| B | Era 4 Personal AI (`era4-personal-ai.md`) | ✅ Done (migration 014) |
| C | Era 6 Ambient AI (`era6-ambient-ai.md`) | ✅ Done (migration 016) |
| D | Era 5 Self-Improving (`era5-self-improving.md`) | ✅ Done (migration 015) |
| E | Era 7 Agent Networks (`era7-agent-networks.md`) | ✅ Done (migration 017) |
| F | Era 8 Autonomous AI (`era8-autonomous-ai.md`) | ✅ Done (migration 018) |
| F0 | The Lifeline (backups + restore drills) | ✅ Done — `scripts/backup.sh`, `scripts/restore.sh`, `scripts/verify_restore.sh`, `docs/OPERATIONS.md` |
| G | Capture Spine (`capture-spine.md`) | ✅ Done (migration 019) — see remaining gaps below |
| H | Judgment Engine (`judgment-engine.md`) | ✅ Done (migration 020) — see remaining gaps below |
| I | Agent Drivers (`agent-drivers.md`) | ✅ Done (migration 021) — see remaining gaps below |

### ✅ Remaining Gaps — ALL CLOSED (July 12, 2026)

The seven "real TODO" gaps against the G/H/I specs are now implemented, each
test-first and verified against the live DB.

**Agent Drivers (Phase I):**
- ✅ **Seed personas** — `uzhavu-ops` + `dependency-updater` in `_BUILTIN_PERSONAS` (`kernel/personas.py`) with pinned `driver`, `task_types`, `verifier_chain`. Fixed `_persona_to_dict` to serialize the driver columns. Tests: `tests/unit/test_builtin_personas.py`.
- ✅ **Watcher→task origination** — `watchers/origination.py` (`TaskOriginationService`): actionable findings → kernel tasks, per-tenant/per-project WIP limits + dedup; wired into `workers/tasks.py::run_watchers` (called directly — the Redis bridge is publish-only). Tests: `tests/unit/test_task_origination.py`.
- ✅ **Second-opinion reviewer** — `services/second_opinion.py` (`SecondOpinionReviewer`): dissenting cheap-model pass after verifiers, before landing; dissent → approval queue. Wired into `drivers/dispatcher.py`, gated by `LIFE_GRAPH_DRIVER_SECOND_OPINION_ENABLED` (**off by default** — LLM overhead). Tests: `tests/unit/test_second_opinion.py`.

**Capture Spine (Phase G):**
- ✅ **Tool-observation hook** — `tools/registry.py` post-exec hook + `services/tool_observation.py`: writes `surface="tool_exhaust"` observations with secret redaction (`core/redaction.py`) and daily-cap sampling. Wired in `main.py`. Tests: `test_redaction.py`, `test_tool_registry_hooks.py`, `test_tool_observation.py`.
- ✅ **Correction-triple NDJSON export** — `GET /capture/corrections/export` streams `(original, corrected, context)` triples; honors `context.exportable=false` opt-out. Tests: `tests/unit/test_correction_export.py`.

**Judgment Engine (Phase H):**
- ✅ **Big-decision detection** — `detect_big_decision()` heuristic (money / >2-week commitment / irreversibility) in `services/judgment.py`; big candidates tagged and surfaced once in the daily brief (`services/brief.py`). Tests: `tests/unit/test_big_decision.py`.
- ✅ **Monthly failure-pattern mining** — `services/failure_mining.py` (`FailurePatternMiner`): 1 LLM pass over failed decisions, **instances-cited-or-dropped** rule (≥3 cited decision ids), stores `failure_pattern` memories. Monthly cron `failure_pattern_mining` in `workers/`. Tests: `tests/unit/test_failure_mining.py`.

- 🐛 Fixed pre-existing model drift: `AgentTask.tags` was `nullable=True` (no default) while migration 017 made the column `NOT NULL DEFAULT '{}'`, so the ORM emitted explicit `NULL` and **every** `ProcessManager.spawn` failed on a migrated DB. Now `nullable=False, server_default="{}", default=list`.

> **Strategy note:** the reasoning behind G/H/I (agent-OS identity, rent-vs-build, frontend, business sequencing) is recorded in `docs/design/07_strategic_direction_2026-07.md`. Read it before proposing new directions.

### Each spec contains:
- User stories with GIVEN/WHEN/THEN acceptance criteria
- Complete SQL schemas (copy-paste ready)
- API endpoint contracts with request/response JSON
- Mermaid architecture diagrams
- Core Python implementation code
- Task checklists with effort estimates

## How to Build

### Step 1: Read the spec
```
Open docs/specs/<spec-name>.md
Read the Requirements section (user stories)
Read the Design section (schemas, APIs, code)
Read the Tasks section (checklist)
```

### Step 2: Create the migration
```bash
# Each spec defines SQL tables. Create an Alembic migration:
cd d:\DevTools\Projects\agents
alembic revision --autogenerate -m "add <feature> tables"
```

### Step 3: Create the models
```
Follow existing pattern in life_graph/models/db.py
Use SQLAlchemy 2.0 mapped_column style
Always include tenant_id
```

### Step 4: Create the service
```
Follow existing pattern in life_graph/services/
Inject via FastAPI Depends()
Use async everywhere
Fire events via EventBus
```

### Step 5: Create the API endpoints
```
Follow existing pattern in life_graph/api/
Register router in life_graph/main.py
Include OpenAPI examples
```

### Step 6: Create tests
```
Follow pattern in tests/integration/
Use httpx.AsyncClient + ASGITransport
pytest tests/ -v
```

## Key Files Map

| You want to... | Look at... |
|----------------|-----------|
| Understand the architecture | `KNOWLEDGE.md` |
| See what to build vs install | `.comms/context/strategic-decision.md` |
| See all specs | `docs/specs/` |
| Add an endpoint | `life_graph/api/` — follow `memories.py` |
| Add a service | `life_graph/services/` — inject via `Depends()` |
| Add a model | `life_graph/models/db.py` + Alembic migration |
| Add a tool | `life_graph/tools/` — use `@tool` decorator |
| Add an agent | `life_graph/agents/` — see `orchestrator.py` |
| Add a kernel service | `life_graph/kernel/` — follow `scheduler.py` pattern |
| Add a kernel endpoint | `life_graph/api/kernel.py` — 25 endpoints already there |
| Add a background job | `life_graph/workers/` — register in ARQ |
| Run tests | `pytest tests/ -v` |
| Run kernel tests only | `pytest tests/integration/test_kernel_*.py -v` |
| Check config | `life_graph/config.py` — env prefix: `LIFE_GRAPH_` |

## Code Conventions
- **Python 3.11+**, async everywhere
- **Ruff** for linting (line-length=100, see `pyproject.toml`)
- **Type hints** on all function signatures
- **Docstrings** on all public classes and functions
- **No hardcoded enums** — use JSONB properties + dynamic tags
- **Tenant-scoped** — every query must filter by `tenant_id`
- **Event-driven** — fire events via EventBus, don't call services directly

## Developer Context
- Solo developer, Windows 11 ARM (Snapdragon X), 16GB RAM, no GPU
- Self-hosted VPS for deployment
- Prefers Python (FastAPI) for backend, Next.js for frontend
- No vendor lock-in — own the toolchain
- Cost-conscious — use cheap models (Gemini Flash, DeepSeek) where possible

## Related Projects
- **Uzhavu** (`\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race`) — multi-tenant SaaS (NestJS + Next.js + FastAPI AI engine)
- Life Graph agents can operate Uzhavu (deploy, monitor, fix)
- Uzhavu AI Engine already connects to Life Graph via HTTP client
