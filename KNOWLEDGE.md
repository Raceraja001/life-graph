# 🧠 Project Knowledge Base

> **Last updated:** 2026-07-07 | **Version:** 1.1.0

This is the single source of truth for AI agents and developers working on Life Graph.
Read this FIRST before touching any code.

---

## Who You Are
- Solo developer building personal tools and infrastructure
- Previous projects: Universal Deployment Platform, Hugging Face model integration, Uzhavu (multi-tenant SaaS)
- OS: Windows, deploys on self-hosted VPS
- Values: self-hosted, cost-efficient, no vendor lock-in, own your toolchain
- Backend preference: Python (FastAPI)
- Frontend preference: Next.js (not started yet for this project)

## What Life Graph Is

**A brain-inspired memory microservice that gives AI agents persistent, evolving memory.**

Multi-tenant SaaS backend — 70 API endpoints, 13 database tables, 20 service modules.

### The Elevator Pitch
> Instead of every AI conversation starting from zero, Life Graph remembers users permanently — their preferences, decisions, beliefs, and context. It extracts facts from conversations, scores their importance, detects contradictions, and proactively surfaces relevant memories at the right time.

### Status: Backend v1.0 Complete ✅
- Full API implemented and hardened (11-item spec complete)
- 87 integration tests for memory layer (7 test files)
- Documentation complete (README, ARCHITECTURE, FEATURES, QUICKSTART, CHANGELOG)

### OS Kernel Layer: Complete ✅
- 25 API endpoints across 6 phases
- 126 integration tests across 6 test files (73 pass, 53 skip without DB)
- Phases: Process Manager, Agent Personas, Chief Router, Scheduler, Project Registry, Notification Engine
- Frontend: NOT STARTED (planned: Next.js dashboard)

---

## Architecture Summary

```
API Layer (FastAPI, 45 endpoints)
  ↓
Middleware (RequestID → Auth → Tenant → RateLimit → Logging)
  ↓
Services (12 modules: MemoryManager, RecallEngine, ContradictionDetector, etc.)
  ↓
AI Pipeline (3-tier extraction → importance scoring → dedup → contradiction)
  ↓
Storage (PostgreSQL+pgvector, Apache AGE graph, Redis, MinIO)
  ↓
Background (ARQ: consolidation@3AM, decay@4AM, async embeddings)
```

### Key Files Map
| You want to... | Look at... |
|----------------|-----------|
| Understand the full pipeline | `core/memory_manager.py` — primary ingestion orchestrator |
| Add a new API endpoint | `api/` — follow the pattern in `memories.py` |
| Change extraction logic | `extraction/pipeline.py` (orchestrator), `rules.py` (regex), `nlp.py` (spaCy) |
| Modify scoring | `scoring/importance.py` (importance), `ranking.py` (recall ranking), `decay.py` (forgetting) |
| Add a database model | `models/db.py` + create migration in `alembic/versions/` |
| Change middleware behavior | `api/middleware.py` — 5 layers, order matters |
| Add a background job | `workers/tasks.py` + register in `workers/settings.py` |
| Modify tenant behavior | `core/tenant.py` (contextvars) + `api/middleware.py` (TenantMiddleware) |
| Add an event type | `core/events.py` — add to `EventType` enum |
| Understand test patterns | `tests/conftest.py` (fixtures), `tests/integration/` (87 tests) |

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| API | FastAPI + Uvicorn | Async, auto OpenAPI docs, Pydantic validation |
| Database | PostgreSQL + pgvector | Relational + 768-dim vector search in one DB |
| Graph | Apache AGE | Graph/Cypher queries as Postgres extension (no separate DB) |
| Cache/Queue | Redis | Rate limiting (ZSET), pub/sub events, ARQ job queue |
| Object Storage | MinIO | S3-compatible, for voice/image/document files |
| NLP | spaCy + sentence-transformers | Local, no API cost, handles 80% of extraction |
| LLM | LiteLLM → LM Studio or Gemini/OpenRouter | Routed: cheap for extraction, expensive for reasoning |
| Background Jobs | ARQ | Redis-backed, cron support, max 3 retries |
| Metrics | Prometheus | Request counts, LLM tokens, memory stats |

---

## Key Design Decisions

### 1. LLM as Advisor, Not Authority (85% Rule-Based)
| Operation | Method | LLM? |
|-----------|--------|------|
| Fact extraction | Regex (40+ patterns) + spaCy NER + dep parsing | Only if Tiers 1-2 score < 0.5 |
| Importance scoring | Additive/subtractive signal rules | Never |
| Contradiction detection | Cosine similarity finds candidates | LLM judges only ambiguous cases |
| Query routing | Pattern-based regex router | Never |
| Tagging | Rule-based from extraction metadata | Never |
| Consolidation | Clustering + dedup rule-based | LLM for distillation step only, 1x/night |

### 2. Schema-Less Core
- `properties` column is JSONB — no hardcoded types or domains
- Tags are dynamic arrays — no enum constraints
- Works for coding memories, health decisions, career notes, anything

### 3. Brain-Inspired Cycles
| Brain Process | Life Graph Equivalent |
|--------------|----------------------|
| Sleep consolidation | Nightly 7-step consolidation pipeline (cluster, dedup, distill) |
| Forgetting curve | Exponential decay: `importance × access^0.3 × e^(-λ × days)` |
| Priming | Proactive recall at session start |
| Reconsolidation | Memories update importance/tags on each access |
| Prospective memory | Intentions with time/event/context triggers |
| Metacognition | MetamemoryTracker tracks what the system doesn't know |

### 4. Multi-Tenant Isolation
- Every SQL query scoped by `tenant_id`
- Middleware extracts `X-Tenant-ID` header → sets contextvar
- Deactivated tenants: reads OK, writes blocked (403)
- Plan-based rate limiting: free (60/min), pro (300/min), enterprise (unlimited)

### 5. Deduplication Strategy
1. **Exact match**: SHA-256 content hash — O(1) lookup
2. **Near match**: pgvector cosine ≥ 0.92 — catches paraphrases
3. **Merge rules**: `max(importance)`, `union(tags)`, `{**old, **new}` properties
4. **Skip**: `skip_dedup=true` on MemoryCreate for explicit overrides

---

## API Structure

### Public Endpoints (`/api/v1/`)
| Domain | Prefix | Endpoints | Key Operations |
|--------|--------|-----------|---------------|
| Memories | `/memories` | 6 | CRUD + list with filters + unarchive |
| Sessions | `/sessions` | 5 | Start/end + heartbeat + list |
| Search | `/search` | 4 | Semantic search, proactive recall, event recall, Q&A |
| Intentions | `/intentions` | 5 | CRUD + trigger check |
| Identity | `/identity` | 4 | Timeline, beliefs, stale detection, challenge |
| Graph | `/graph` | 5 | Entities, Cypher query, path finding, hybrid search |
| Agent | `/agent` | 2 | Context building, learning from conversations |
| Multimodal | `/ingest` | 3 | Voice (Whisper), image (OCR), document (PDF) |

### Admin Endpoints (`/admin/`)
| Domain | Endpoints | Key Operations |
|--------|-----------|---------------|
| Stats | 2 | System stats, knowledge gaps |
| Webhooks | 4 | CRUD + test ping (HMAC-SHA256 signed) |
| Tenants | 5 | Provision, summary, deactivate, reactivate, delete |
| Bulk Ops | 2 | Delete with dry-run, import (max 500) |
| Jobs | 3 | Manual consolidation, job listing, async enqueue |
| Export | 1 | NDJSON streaming export |

### Kernel Endpoints (`/api/v1/kernel/`)
| Domain | Prefix | Endpoints | Key Operations |
|--------|--------|-----------|---------------|
| Tasks | `/kernel/tasks` | 4 | CRUD + cancel (ProcessManager) |
| Personas | `/kernel/personas` | 5 | CRUD + tool permission filtering |
| Routing | `/kernel/route` | 3 | Intent classify + task spawn + sessions |
| Schedules | `/kernel/schedules` | 5 | CRUD for cron-based jobs |
| Projects | `/kernel/projects` | 5 | Register + scan + CRUD |
| Notifications | `/kernel/notifications` | 3 | List + mark read + mark-all-read |

### Infrastructure
| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Deep health check (DB + Redis latency, HTTP 503 if critical) |
| `WS /ws` | Real-time event streaming via Redis pub/sub |
| `GET /docs` | Swagger UI (OpenAPI with response examples) |

---

## Database Schema (13 Tables)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `memories` | Core storage | content, embedding (768-dim), importance, tags, status, content_hash, supersedes/superseded_by, decay_rate |
| `sessions` | Conversation tracking | context (JSONB), summary, embedding |
| `intentions` | Prospective memory | trigger_type (time/event/context), trigger_condition, expires_at |
| `knowledge_gaps` | What we don't know | topic, query_count, resolved_by FK→memories |
| `memory_sessions` | M:N join | memory_id + session_id |
| `job_runs` | Background job log | job_name, status, result (JSONB), attempt |
| `tenant_usage` | Usage metering | api_calls, memories_created, llm_tokens_used, llm_cost_usd |
| `tenant_configs` | Tenant settings | plan, status, cold_start_config (JSONB) |
| `tenant_webhooks` | Webhook registry | url, secret, events, active, failure_count |
| `agent_tasks` | OS Kernel tasks | agent_name, status, input/output (JSONB), priority, timeout, retries |
| `agent_sessions` | Routing sessions | intent, confidence, agent_chain (JSONB) |
| `agent_personas` | Agent configuration | system_prompt, tools (JSONB), intent_pattern |
| `scheduled_jobs` | Cron job config | cron_expression, agent_name, run_count, consecutive_failures |
| `projects` | Registered codebases | path, language, framework, git_branch, file_count |
| `notifications` | Priority-routed alerts | priority, channel, title, is_read, source_type |

### Migrations
| # | File | What It Does |
|---|------|-------------|
| 001 | Initial schema | Base tables |
| 002 | Intentions | Intentions + knowledge_gaps tables |
| 003 | Sessions | Sessions + memory_sessions tables |
| 004 | SaaS hardening | TenantConfig, TenantWebhook tables + content_hash column |
| 005 | Cold start config | cold_start_config JSONB on tenant_configs |
| 011 | OS Kernel | agent_tasks, agent_sessions, agent_personas tables |
| 012 | Scheduled jobs | scheduled_jobs table |
| 013 | Projects + Notifications | projects + notifications tables |

---

## Event System

18 event types fired via async EventBus:

**Memory Events:** `MEMORY_CREATED` · `MEMORY_RETRIEVED` · `MEMORY_UPDATED` · `MEMORY_DELETED` · `SESSION_START` · `SESSION_END` · `INTENTION_TRIGGERED` · `CONTRADICTION_DETECTED` · `VOICE_TRANSCRIBED` · `IMAGE_PROCESSED` · `DOCUMENT_IMPORTED`

**Kernel Events:** `TASK_SPAWNED` · `TASK_COMPLETED` · `TASK_FAILED` · `TASK_CANCELLED` · `TASK_TIMEOUT` · `SCHEDULE_FIRED` · `SCHEDULE_DISABLED` · `PROJECT_REGISTERED` · `PROJECT_SCANNED` · `NOTIFICATION_CREATED`

Events → RedisBridge (cross-instance) → WebhookEventHandler (HMAC delivery) + WebSocket relay.

---

## Background Jobs

| Job | Schedule | What |
|-----|----------|------|
| Consolidation | 03:00 UTC nightly | 7-step "sleep cycle": gather → cluster → dedup → score → distill → decay → audit |
| Nightly self-heal | 03:30 UTC nightly | Era 5 self-improving loop (eval + prompt optimization) |
| Decay sweep | 04:00 UTC nightly | Archive memories below threshold via bulk SQL |
| Trust decay | 05:00 UTC nightly | Era 8: decay trust scores for inactive agents |
| Daily brief | 02:00 UTC daily (`LIFE_GRAPH_BRIEF_HOUR_UTC`) | Interview expire sweep + generation, held notifications, capture summary, watcher digest → one notification (`run_daily_brief`) |
| Watchers | Hourly | Era 6 ambient watchers (server health, deps, code quality, tech radar) |
| Watcher digest | 08:00 UTC daily | Compile digest-pending watch events into one notification |
| Approval timeouts | Every 5 min | Era 8: expire unapproved actions |
| Approval escalations | Every 30 min | Era 8: escalate pending approvals |
| Research refresh | Sunday 02:00 UTC | Era 4: refresh stale research topics |
| Embedding gen | On-demand | Batch embeddings for bulk import (chunks of 32) |
| Webhook delivery | On-demand | HMAC-signed HTTP POST with circuit breaker (10 failures → deactivate) |

**Lifeline (backup sidecar container, not ARQ — see `docs/OPERATIONS.md`):**

| Job | Schedule | What |
|-----|----------|------|
| Nightly backup | 02:00 UTC | `pg_dump` + optional restic off-site; logged to `job_runs` |
| Restore drill | Sunday 06:00 UTC | Restore latest dump into scratch DB, verify row counts + embeddings; logged to `job_runs` |

---

## Testing

- **107 Python files** pass syntax check
- **213+ total integration tests** (87 memory + 126 kernel) across 13 files in `tests/integration/`
- Test pattern: `httpx.AsyncClient` + `ASGITransport` (in-process, no running server needed)
- Defensive: accept 500 if DB unreachable, assert no 422 for valid inputs
- Fixtures: `@pytest_asyncio.fixture` with tenant headers

### Kernel Test Files
| File | Tests | What |
|------|-------|------|
| `test_kernel_tasks.py` | 15 | Task CRUD + cancellation |
| `test_kernel_personas.py` | 23 | Persona CRUD + tool permissions |
| `test_kernel_router.py` | 25 | Intent classification + routing |
| `test_kernel_scheduler.py` | 25 | Cron parser + schedule CRUD |
| `test_kernel_projects.py` | 22 | Detection helpers + project CRUD |
| `test_kernel_notifications.py` | 16 | Notification CRUD + mark read |

---

## Configuration

All env vars prefixed `LIFE_GRAPH_`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Postgres connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `ENVIRONMENT` | `development` | dev/staging/production |
| `LOG_FORMAT` | `text` | `text` (dev) or `json` (prod) |
| `LOG_LEVEL` | `INFO` | DEBUG/INFO/WARNING/ERROR |
| `SERVICE_API_KEYS` | — | Comma-separated auth keys |
| `DEDUP_ENABLED` | `true` | Enable/disable deduplication |
| `DEDUP_THRESHOLD` | `0.92` | Cosine similarity for near-match |
| `EMBEDDING_MODEL` | `all-mpnet-base-v2` | Sentence-transformers model |
| `LM_STUDIO_URL` | — | Local LLM endpoint |

---

## Documentation Index

| File | What |
|------|------|
| [README.md](README.md) | Project overview, quickstart, feature tables |
| [CHANGELOG.md](CHANGELOG.md) | v1.0.0 release notes, versioning policy |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full architecture with mermaid diagrams |
| [docs/FEATURES.md](docs/FEATURES.md) | Exhaustive catalog of 45+ endpoints |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Docker + local setup guide |
| [docs/research/](docs/research/) | 5 research documents (build-vs-buy, open source eval, memory mechanisms) |
| [docs/design/](docs/design/) | 7 design documents (scope, architecture, cold start, recall, strategic direction) |
| [docs/design/07_strategic_direction_2026-07.md](docs/design/07_strategic_direction_2026-07.md) | **Decisions record** — agent-OS identity, rent-vs-build agents, frontend, business sequencing, priority order |

---

## Anti-Patterns to Avoid

1. **No maintenance tax** — AI handles ALL organization, user never manually files things
2. **No collector's fallacy** — store decisions/lessons, not bookmarks
3. **Proactive recall** — don't wait for user to search, push relevant memories
4. **Cold start solved** — bootstrap from Git/config/code analysis (50+ memories, zero LLM)
5. **Zero capture friction** — observe work, don't ask user to categorize
6. **No proprietary lock-in** — PostgreSQL, standard APIs, fully exportable NDJSON
7. **No hardcoded schemas** — JSONB properties, dynamic tags, works across any domain

---

## What's Next

Eras 4–8, Capture Spine (incl. interview + daily brief), Judgment Engine,
Agent Drivers (incl. `claude_code`), the dashboard, and the Lifeline are
**built** — see START_HERE.md for the verified status table. Remaining gaps:

- [ ] **Tool-observation hook** — tool registry post-execution → capture spine (secret redaction, daily cap)
- [ ] **Correction-triple NDJSON export** — capture spine export endpoint
- [ ] **Monthly failure-pattern mining** — judgment engine cron (instances-cited-or-dropped rule)
- [ ] **Big-decision detection** — heuristic → brief suggestion (once, never nagging)
- [ ] **Second-opinion reviewer** — dissenting cheap-model pass in the verifier chain
- [ ] **Seed personas** — `uzhavu-ops` + `dependency-updater` rows (agent-drivers Story 5)
- [ ] **Watcher→task origination** — watcher findings + scheduler originate kernel tasks
- [ ] **SDK documentation** — Python + TypeScript SDK usage examples

---

## Kernel File Map

| File | Purpose |
|------|---------|
| `life_graph/kernel/__init__.py` | Package exports: ProcessManager, PersonaService, ChiefRouter, SchedulerService, ProjectRegistry, NotificationEngine |
| `life_graph/kernel/process_manager.py` | Task lifecycle: spawn, execute, cancel, list |
| `life_graph/kernel/personas.py` | Agent persona CRUD + tool permission filtering |
| `life_graph/kernel/chief_router.py` | Regex-based intent classification, persona resolution, session tracking |
| `life_graph/kernel/scheduler.py` | Built-in cron parser + scheduled job CRUD, fire/record, auto-disable |
| `life_graph/kernel/project_registry.py` | Project CRUD, auto-scan (language/framework/git/deps), context builder |
| `life_graph/kernel/notification_engine.py` | Notification CRUD, mark-read, priority routing |
| `life_graph/api/kernel.py` | 25 kernel API endpoints across 6 phases |
| `life_graph/api/dependencies.py` | DI providers for all kernel services |
