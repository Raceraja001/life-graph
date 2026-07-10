# Agent Guidelines

> Rules for any AI agent working in this repository.

## About the Developer
- Solo developer, values self-hosted solutions and cost efficiency
- Prefers Python (FastAPI) for backend, Next.js for frontend
- Uses Windows, deploys on self-hosted VPS
- Wants to own their toolchain — no vendor lock-in
- Ask for approval before starting implementation plans

## Project: Life Graph — AI Operating System

An always-running personal AI system. Brain (memory) + Body (agents) + Senses (watchers) + Growth (self-improvement). **Memory backend is complete** (45 endpoints, 87 tests). Agent system merged from Uzhavu (orchestrator + 10 tools). OS kernel, personal AI, and higher layers are spec'd but not built yet.

### Before You Write Code
1. **Read [START_HERE.md](START_HERE.md)** — complete onboarding with current state and build instructions
2. **Read [KNOWLEDGE.md](KNOWLEDGE.md)** — full architecture, decisions, and file map
3. **Check `docs/specs/`** — 6 Kiro-style specs with user stories, schemas, APIs, and code
4. **Never ask the developer to re-explain preferences already documented**

### Spec-Driven Development
All new features have detailed specs in `docs/specs/`. Build in this order:
1. ~~`os-kernel.md`~~ — ✅ **DONE** (25 endpoints, 126 tests, 6 tables)
2. `era4-personal-ai.md` — **NEXT** — Preference store, multi-model advisor (8 days)
3. `era6-ambient-ai.md` — Watchers: deps, server, tech radar (9 days)
4. `era5-self-improving.md` — Eval + DSPy optimization loop (7 days)
5. `era7-agent-networks.md` — Agent delegation, workflows (24 days)
6. `era8-autonomous-ai.md` — Safety framework, auto-fix, trust (22 days)

**Each spec contains everything you need**: SQL schemas, API contracts, Python code, mermaid diagrams, task checklists. Read the spec → follow the tasks → build it.

### Code Conventions
- **Python 3.11+**, async everywhere (FastAPI + SQLAlchemy async)
- **Ruff** for linting/formatting (line-length=100, see `pyproject.toml`)
- **Type hints** on all function signatures
- **Docstrings** on all public classes and functions
- **No hardcoded enums** for types or domains — use JSONB properties + dynamic tags
- **Tenant-scoped** — every query must filter by `tenant_id`
- **Test pattern**: `httpx.AsyncClient` + `ASGITransport` + `@pytest_asyncio.fixture`
- **Defensive tests**: accept 500 if DB unreachable, assert no 422 for valid inputs

### Design Rules
- **LLM as advisor, not authority** — prefer rule-based/local approaches over LLM calls
- **Schema-less** — no hardcoded types, use JSONB `properties` column
- **Event-driven** — fire events via EventBus for new features, don't call services directly
- **Brain-inspired** — consolidation, decay, proactive recall patterns
- **Dedup-aware** — new memories should go through the dedup pipeline

### Key Files
| You want to... | Look at... |
|----------------|-----------|
| Add an endpoint | `life_graph/api/` — follow `memories.py` pattern |
| Add a service | `life_graph/services/` — inject via FastAPI `Depends()` |
| Add a model | `life_graph/models/db.py` + new Alembic migration |
| Add a tool | `life_graph/tools/` — use `@tool` decorator, see `calculator.py` |
| Add an agent | `life_graph/agents/` — see `orchestrator.py` |
| Add extraction rules | `life_graph/extraction/rules.py` (regex patterns) |
| Add a background job | `life_graph/workers/tasks.py` + register in `settings.py` |
| Add an event | `life_graph/core/events.py` — add to `EventType` enum |
| Add OpenAPI docs | `life_graph/api/openapi_examples.py` + wire `responses=` |
| Read a spec | `docs/specs/` — Kiro-style specs with schemas, APIs, code |
| Run tests | `pytest tests/ -v` |

### Related Projects

#### Uzhavu (`\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race`)
- Multi-tenant SaaS platform (NestJS + Next.js + FastAPI AI engine)
- Being converted to a **product factory** — one codebase, multiple branded standalone apps

## Inter-Agent Communication

Multiple Antigravity instances coordinate via `.comms/` directory:

```
.comms/
├── README.md        ← Protocol documentation
├── inbox/           ← Pending tasks — pick one, claim it, do it
├── active/          ← Tasks currently being worked on
├── outbox/          ← Completed task reports
└── context/         ← Shared knowledge — READ THIS FIRST
```

### Rules for Agents:
1. **Always read `KNOWLEDGE.md`** at session start
2. **Check `.comms/inbox/`** for pending tasks assigned to you
3. **Claim before starting**: Move task from `inbox/` to `active/`, set `status: claimed`
4. **Report when done**: Move task from `active/` to `outbox/`, set `status: done`
5. **Update shared context** if you make decisions that affect other agents
