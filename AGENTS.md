# Agent Guidelines

> Rules for any AI agent working in this repository.
>
> This file is **workflow and conventions**. For *why* the project exists and what must not
> be broken, read [CHARTER.md](CHARTER.md). For *what exists right now* — endpoints, tables,
> events, personas, tools, jobs, config — read [docs/STATE.md](docs/STATE.md), which is
> generated from the code by `scripts/gen_state.py`.
>
> Deliberately **no counts here.** Any number in this file would be stale within weeks.

## About the Developer

- Solo developer; values self-hosted solutions and cost efficiency.
- Python (FastAPI) on the backend, Next.js on the frontend.
- Dual-boots Linux (primary) and Windows; the repo lives on ext4 at `~/projects/life-graph`.
  The `*.ps1` scripts are kept for the Windows side.
- Deploys to a self-hosted VPS. Wants to own the toolchain — no vendor lock-in.
- Cost-conscious: prefers cheap models (Gemini Flash, DeepSeek) wherever quality allows.
- **Ask for approval before starting an implementation plan.**
- Never ask the developer to re-explain a preference that is already documented.

## Project: Life Graph — AI Operating System

An always-running personal AI system: **brain** (memory) + **body** (agents) +
**senses** (watchers) + **growth** (self-improvement). The memory core, OS kernel, autonomy
gate, drivers, judgment engine, and ambient layers are all built; see
[docs/STATE.md](docs/STATE.md) for the exact inventory and
[CHARTER.md](CHARTER.md#current-frontier) for what genuinely remains.

### Before You Write Code

1. **Read [CHARTER.md](CHARTER.md)** — intent, the five design invariants, non-goals, and
   the current frontier.
2. **Skim [docs/STATE.md](docs/STATE.md)** — the generated inventory. If something already
   exists, it is listed there. Do not rebuild it.
3. **Check `docs/specs/`** for the feature you are touching. Each spec now carries a
   one-line status header (`Built` / `Spec'd, not built` / `Not this product`).
4. **Check `.comms/inbox/`** for a task assigned to you.

If a number in any prose document disagrees with `docs/STATE.md`, `docs/STATE.md` is right
and the prose is stale — fix the prose or delete the number.

### Spec-Driven Development

Features are specified in `docs/specs/` before they are built. A spec contains user stories
with GIVEN/WHEN/THEN acceptance criteria, copy-paste-ready SQL schemas, API contracts with
request/response JSON, mermaid diagrams, core Python code, and a task checklist with effort
estimates.

The build loop:

1. **Read the spec** — Requirements (user stories), then Design (schemas, APIs, code), then
   Tasks (the checklist you will work through).
2. **Create the migration** — `python -m alembic revision --autogenerate -m "add <feature> tables"`,
   run from the repo root with the venv active.
3. **Create the models** — `life_graph/models/db.py`, SQLAlchemy 2.0 `mapped_column` style.
   Always include `tenant_id`.
4. **Create the service** — `life_graph/services/`, injected via `Depends()`, async
   throughout, firing events on the EventBus rather than calling other services.
5. **Create the API endpoints** — `life_graph/api/`, router registered in `life_graph/main.py`,
   with OpenAPI examples.
6. **Create the tests** — `tests/integration/`, `httpx.AsyncClient` + `ASGITransport`.
7. **Regenerate the state doc** — `python scripts/gen_state.py --html`. New tables,
   endpoints, events, and jobs must show up in the diff.

### Code Conventions

- **Python 3.11+**, async everywhere (FastAPI + SQLAlchemy async).
- **Ruff** for linting and formatting (line-length 100, double quotes — see `pyproject.toml`).
- **Type hints** on all function signatures; **docstrings** on all public classes and functions.
- **No hardcoded enums** for types or domains — use the JSONB `properties` column and dynamic tags.
- **Tenant-scoped** — every query filters by `tenant_id`.
- **Test pattern**: `httpx.AsyncClient` + `ASGITransport` + `@pytest_asyncio.fixture`, with
  tenant headers.
- **Defensive tests**: accept 500 when the DB is unreachable, but never accept 422 for valid input.

### Design Rules

The five invariants are stated in full, with their reasoning, in
[CHARTER.md](CHARTER.md#design-invariants). In short:

- **LLM as advisor, not authority** — prefer rule-based and local approaches; consult a model
  only when deterministic tiers score low.
- **Schema-less** — no hardcoded types; JSONB `properties` plus dynamic tags.
- **Event-driven** — fire an event and subscribe; do not reach into the producing service.
- **Tenant-scoped** — a query that forgets `tenant_id` is a cross-tenant data leak.
- **Fail-closed autonomy** — an unmatched action is `DANGEROUS` and gets queued, never run.

Plus: new memories go through the dedup pipeline, and consolidation/decay/proactive-recall
patterns are how memory is expected to behave.

### Key Files

| You want to... | Look at... |
|----------------|-----------|
| Add an endpoint | `life_graph/api/` — follow `memories.py`, register in `main.py` |
| Add a service | `life_graph/services/` — inject via FastAPI `Depends()` |
| Add a model | `life_graph/models/db.py` + a new Alembic migration |
| Add a kernel service | `life_graph/kernel/` — follow the `scheduler.py` pattern |
| Add a tool | `life_graph/tools/` — use the `@tool` decorator, see `calculator.py` |
| Add an agent | `life_graph/agents/` — see `orchestrator.py` |
| Add extraction rules | `life_graph/extraction/rules.py` (regex tier) |
| Add a background job | `life_graph/workers/tasks.py` + register in `workers/settings.py` |
| Add an event | `life_graph/core/events.py` — add to the `EventType` enum |
| Add OpenAPI docs | `life_graph/api/openapi_examples.py` + wire `responses=` |
| Read a spec | `docs/specs/` — check its status header first |
| Check config | `life_graph/config.py` — env prefix `LIFE_GRAPH_` |
| Run tests | `pytest tests/ -v` (`tests/unit/ -v` needs no database) |
| Refresh the inventory | `python scripts/gen_state.py --html` |

### Related Projects

- **Uzhavu** (`~/projects/uzhavu.race`) — multi-tenant SaaS (NestJS + Next.js + FastAPI AI
  engine), being converted into a product factory: one codebase, multiple branded standalone
  apps. Life Graph agents can operate it (deploy, monitor, fix), and its AI engine already
  calls Life Graph over HTTP.

## Inter-Agent Communication

Multiple agent instances coordinate via the `.comms/` directory:

```
.comms/
├── README.md        ← Protocol documentation
├── inbox/           ← Pending tasks — pick one, claim it, do it
├── active/          ← Tasks currently being worked on
├── outbox/          ← Completed task reports
└── context/         ← Shared knowledge — READ THIS FIRST
```

These four directories plus the README are the whole protocol. Anything else that appears
under `.comms/` is accretion and does not belong there.

### Rules for Agents

1. **Read [CHARTER.md](CHARTER.md) and [docs/STATE.md](docs/STATE.md)** at session start.
2. **Check `.comms/inbox/`** for pending tasks assigned to you.
3. **Claim before starting**: move the task from `inbox/` to `active/`, set `status: claimed`.
4. **Report when done**: move the task from `active/` to `outbox/`, set `status: done`.
5. **Update shared context** if you make a decision that affects other agents.
6. **Never hand-edit `docs/STATE.md`** — regenerate it.
