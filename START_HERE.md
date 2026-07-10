# Life Graph — New Agent Start Here

> **READ THIS FIRST.** This file tells you everything you need to know to start working on Life Graph.

## What Is This Project?

Life Graph is an **AI Operating System** — an always-running personal AI assistant built with FastAPI + PostgreSQL. It's not just a memory service. It manages agents, tools, watchers, and learns from every interaction.

## Current State (Updated: July 7, 2026)

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

### ❌ What's NOT Built (The Roadmap)
5 specs remain in `docs/specs/`. Build them in this order:

| Phase | Spec | File | Effort | Priority |
|:------|:-----|:-----|:-------|:---------|
| ~~A~~ | ~~OS Kernel~~ | ~~`os-kernel.md`~~ | ~~12 days~~ | ✅ **DONE** |
| **B** | Personal AI (Knowledge Engine) | `docs/specs/era4-personal-ai.md` | 8 days | 🔴 **Next — the unique product value** |
| **C** | Ambient AI (Watchers) | `docs/specs/era6-ambient-ai.md` | 9 days | 🟡 After B |
| **D** | Self-Improving Agent | `docs/specs/era5-self-improving.md` | 7 days | 🟡 After B |
| **E** | Agent Networks | `docs/specs/era7-agent-networks.md` | 24 days | 🟢 Later |
| **F** | Autonomous AI | `docs/specs/era8-autonomous-ai.md` | 22 days | 🟢 Much later |
| **F0** | The Lifeline (backups + weekly restore drills) | `docs/design/07_strategic_direction_2026-07.md` §D7.1 | 1–2 days | 🔴 **Before everything** — the data is the moat |
| **G** | Capture Spine (universal input layer) | `docs/specs/capture-spine.md` | 7.5 days | 🔴 Foundation for H/I — build before or alongside |
| **H** | Judgment Engine (calibration + adversarial advisor) | `docs/specs/judgment-engine.md` | 8.5 days | 🔴 The differentiator — needs G Phases 1–2 |
| **I** | Agent Drivers (rent executors, context packets, verifiers) | `docs/specs/agent-drivers.md` | 9.5 days | 🔴 The workforce — needs G Phase 1 |

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
