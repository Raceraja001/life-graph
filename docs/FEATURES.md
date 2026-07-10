# Life Graph — Complete Feature Catalog

> **What is Life Graph?** A memory layer for AI agents. It gives any LLM persistent, searchable, evolving memory — like giving an AI a brain that remembers across conversations.

---

## 📊 By The Numbers

| Metric | Count |
|--------|-------|
| API Endpoints | **45 + 1 WebSocket** |
| Database Models | **9 tables** |
| Services | **12 modules** |
| Background Workers | **6 tasks + 2 cron jobs** |
| Middleware Layers | **5** |
| Storage Backends | **4** (Postgres+pgvector, Apache AGE, Redis, MinIO) |
| Alembic Migrations | **5** |
| Integration Tests | **87** |
| Python Files | **107** |

---

## 🧠 Core: Memory CRUD

The foundation — creating, reading, updating, and deleting memories.

| Endpoint | What It Does |
|----------|-------------|
| `POST /api/v1/memories/` | Create memories from text. Runs the full pipeline: extract → score → embed → dedup → contradiction check → store |
| `GET /api/v1/memories/{id}` | Get a single memory by ID |
| `PATCH /api/v1/memories/{id}` | Partial update (content, tags, importance, properties) |
| `DELETE /api/v1/memories/{id}` | Soft delete a memory |
| `GET /api/v1/memories/` | List memories with filters (status, tags, min_importance, source_type, date range) |
| `POST /api/v1/memories/{id}/unarchive` | Restore an archived memory back to active |

**Key files:** [memories.py](file:///D:/DevTools/Projects/agents/life_graph/api/memories.py), [memory_manager.py](file:///D:/DevTools/Projects/agents/life_graph/core/memory_manager.py)

---

## 🔍 Search & Recall

The intelligence layer — finding and surfacing relevant memories.

| Endpoint | What It Does |
|----------|-------------|
| `POST /api/v1/search/` | Semantic vector search (pgvector cosine similarity) with filters |
| `POST /api/v1/search/recall` | **Proactive recall** — at session start, retrieves and ranks memories across 4 categories: identity, decisions, intentions, warnings |
| `POST /api/v1/search/recall/event` | **Event-driven recall** — mid-conversation, triggered by context changes (lighter, max 2 results) |
| `POST /api/v1/search/ask` | **Natural language Q&A** — semantic search + LLM synthesis into a direct answer |

**Multi-signal ranking formula:**
- Semantic similarity: 25%
- Context match: 25%
- Importance: 20%
- Recency: 15%
- Access frequency: 10%
- Trust score: 5%

**Anti-annoyance system:** 7-day cooldown per memory, max 2 per topic, session caps, dismissal tracking.

**Key files:** [search.py](file:///D:/DevTools/Projects/agents/life_graph/api/search.py), [recall.py](file:///D:/DevTools/Projects/agents/life_graph/services/recall.py), [ranking.py](file:///D:/DevTools/Projects/agents/life_graph/scoring/ranking.py)

---

## 🎯 Intentions (Prospective Memory)

"Remind me to..." — time, event, or context-triggered future actions.

| Endpoint | What It Does |
|----------|-------------|
| `POST /api/v1/intentions/` | Create an intention with trigger type (time/event/context) |
| `GET /api/v1/intentions/` | List pending intentions |
| `POST /api/v1/intentions/triggered` | Check which intentions fire against current context |
| `PATCH /api/v1/intentions/{id}/complete` | Mark as completed |
| `PATCH /api/v1/intentions/{id}/dismiss` | Dismiss without completing |

**Trigger types:** Time-based (specific datetime), Event-based ("when I open project X"), Context-based (pattern matching against conversation).

**Key files:** [intentions.py](file:///D:/DevTools/Projects/agents/life_graph/api/intentions.py), [triggers.py](file:///D:/DevTools/Projects/agents/life_graph/services/triggers.py)

---

## 🪪 Identity & Beliefs

Track how a person's preferences, beliefs, and decisions evolve over time.

| Endpoint | What It Does |
|----------|-------------|
| `GET /api/v1/identity/timeline` | Identity timeline grouped by month — shows belief evolution |
| `GET /api/v1/identity/beliefs` | Current active beliefs/preferences |
| `GET /api/v1/identity/stale` | Find stale beliefs (not accessed in N days) with challenge prompts |
| `POST /api/v1/identity/challenge` | Mark a belief as "uncertain" for review |

**Key files:** [identity.py](file:///D:/DevTools/Projects/agents/life_graph/api/identity.py), [identity.py (service)](file:///D:/DevTools/Projects/agents/life_graph/services/identity.py)

---

## 🕸️ Knowledge Graph

Entity-relationship graph powered by Apache AGE (Postgres-native graph extension).

| Endpoint | What It Does |
|----------|-------------|
| `GET /api/v1/graph/entities` | List all entities (optional label filter) |
| `GET /api/v1/graph/entity/{name}` | Entity detail + neighbors + related memories |
| `POST /api/v1/graph/query` | Execute read-only Cypher queries |
| `GET /api/v1/graph/path` | Find shortest path between two entities |
| `POST /api/v1/graph/search` | **Hybrid search** — graph narrows scope, vector refines by similarity |

**Key files:** [graph.py](file:///D:/DevTools/Projects/agents/life_graph/api/graph.py), [graph.py (storage)](file:///D:/DevTools/Projects/agents/life_graph/storage/graph.py), [hybrid.py](file:///D:/DevTools/Projects/agents/life_graph/storage/hybrid.py)

---

## 🤖 Agent Integration

First-class support for AI agents that need persistent memory.

| Endpoint | What It Does |
|----------|-------------|
| `POST /api/v1/agent/context` | Build rich context for an agent starting a task (proactive recall → system prompt injection) |
| `POST /api/v1/agent/learn` | Extract and store memories from a completed agent conversation |

**Key files:** [agent.py](file:///D:/DevTools/Projects/agents/life_graph/api/agent.py), [agent_bridge.py](file:///D:/DevTools/Projects/agents/life_graph/services/agent_bridge.py)

---

## 📹 Multi-Modal Ingestion

Not just text — learn from voice, images, and documents.

| Endpoint | What It Does |
|----------|-------------|
| `POST /api/v1/ingest/voice` | Upload audio → Whisper transcription → extraction pipeline (max 50MB) |
| `POST /api/v1/ingest/image` | Upload image → OCR (pytesseract) → extraction pipeline |
| `POST /api/v1/ingest/document` | Upload PDF/MD/TXT → chunk → extraction pipeline |

Files stored in MinIO object storage. Extraction pipeline runs on transcribed/extracted text.

**Key files:** [multimodal.py](file:///D:/DevTools/Projects/agents/life_graph/api/multimodal.py), [multimodal.py (service)](file:///D:/DevTools/Projects/agents/life_graph/services/multimodal.py), [minio_client.py](file:///D:/DevTools/Projects/agents/life_graph/storage/minio_client.py)

---

## 💬 Sessions

Conversation session management with memory linking.

| Endpoint | What It Does |
|----------|-------------|
| `POST /api/v1/sessions/start` | Start a new session |
| `POST /api/v1/sessions/{id}/end` | End session → LLM summary → count linked memories |
| `GET /api/v1/sessions/{id}` | Get session with linked memory count |
| `GET /api/v1/sessions/` | List recent sessions (cursor pagination) |
| `POST /api/v1/sessions/{id}/heartbeat` | Merge new context into session mid-conversation |

**Key files:** [sessions.py](file:///D:/DevTools/Projects/agents/life_graph/api/sessions.py)

---

## ⚙️ Admin & Operations

Operational endpoints for managing the system.

| Endpoint | What It Does |
|----------|-------------|
| `GET /admin/stats` | Memory/session/intention/gap counts |
| `GET /admin/gaps` | Unresolved knowledge gaps |
| `POST /admin/ingest` | Raw text ingestion shortcut |
| `GET /admin/export` | **Stream** all memories as NDJSON (no OOM) |
| `POST /admin/consolidate` | Trigger consolidation manually |
| `GET /admin/jobs` | List recent background job runs |
| `POST /admin/jobs/consolidate` | Enqueue consolidation via ARQ |

---

## 🔗 Webhooks

Event-driven integrations via HTTP callbacks.

| Endpoint | What It Does |
|----------|-------------|
| `POST /admin/webhooks` | Register webhook (HMAC-SHA256 signed payloads) |
| `GET /admin/webhooks` | List tenant webhooks |
| `DELETE /admin/webhooks/{id}` | Remove webhook |
| `POST /admin/webhooks/{id}/test` | Send test ping |

**Circuit breaker:** Auto-deactivates after 10 consecutive delivery failures.

**11 event types:** MEMORY_CREATED, MEMORY_RETRIEVED, MEMORY_UPDATED, MEMORY_DELETED, SESSION_START, SESSION_END, INTENTION_TRIGGERED, CONTRADICTION_DETECTED, VOICE_TRANSCRIBED, IMAGE_PROCESSED, DOCUMENT_IMPORTED.

---

## 👥 Multi-Tenancy

Full SaaS multi-tenant isolation.

| Endpoint | What It Does |
|----------|-------------|
| `POST /admin/tenants/provision` | Create tenant (plan: free/pro/enterprise) |
| `GET /admin/tenants/{id}` | Summary: counts, usage, plan |
| `POST /admin/tenants/{id}/deactivate` | Read-only mode (403 on writes) |
| `POST /admin/tenants/{id}/reactivate` | Restore write access |
| `DELETE /admin/tenants/{id}` | Permanent deletion (requires deactivated first) |

**Plan limits:**

| | Free | Pro | Enterprise |
|-|------|-----|------------|
| Requests/min | 60 | 300 | Unlimited |
| Max memories | 1,000 | 100,000 | Unlimited |
| Ask queries/day | 50 | 500 | Unlimited |

---

## 📦 Bulk Operations

| Endpoint | What It Does |
|----------|-------------|
| `POST /admin/bulk/delete` | Bulk delete with filters + dry-run preview |
| `POST /admin/bulk/import` | Import up to 500 memories + async embedding generation |

---

## 🔌 Real-time WebSocket

| Endpoint | What It Does |
|----------|-------------|
| `WS /ws` | Real-time event streaming. API key auth via query param. Tenant-scoped via Redis pub/sub relay |

---

## 🧬 AI/ML Pipeline (Internal)

### 3-Tier Extraction Pipeline
| Tier | Method | LLM? | Confidence |
|------|--------|-------|------------|
| 1 | **Regex** — 40+ patterns (preferences, decisions, intentions, facts) | No | 0.80–0.95 |
| 2 | **spaCy NLP** — NER + 60 tech terms + dependency parsing + negation | No | 0.55–0.70 |
| 3 | **LLM fallback** — only if Tiers 1-2 are low confidence AND text ≥ 20 words | Yes | Varies |

### Importance Scoring (Rule-based)
Additive: emphasis keywords (+0.3), ALL_CAPS (+0.3), failure (+0.2), architecture (+0.15), explicit save (+0.45)
Subtractive: hedging (-0.2), questions (-0.1)
Tiers: critical ≥0.85, high ≥0.7, normal ≥0.4, low <0.4

### Memory Decay (Exponential Forgetting Curve)
Formula: `importance × access_count^0.3 × e^(-decay_rate × days_since_activity)`
Critical memories exempt. Nightly sweep at 04:00 UTC.

### Deduplication
1. **Exact:** SHA-256 content hash — O(1) lookup
2. **Near-match:** pgvector cosine similarity ≥ 0.92
3. **Merge rules:** max(importance), union(tags), {**old, **new} properties

### Contradiction Detection
Cosine similarity finds candidates → LLM judges conflict → resolution: supersede, ask_user, or scope-limit.

### Nightly Consolidation (7-step "sleep cycle")
1. Gather (24h memories) → 2. Cluster (cosine >0.75) → 3. Dedup (cosine >0.95) → 4. Re-score → 5. Distill (LLM summarizes clusters) → 6. Decay sweep → 7. Contradiction audit

---

## 🏗️ Infrastructure (Internal)

| System | Implementation |
|--------|---------------|
| **Event Bus** | Async pub/sub with Redis bridge for cross-instance relay |
| **Plugin System** | Directory-based discovery with config.yaml per plugin |
| **Metrics** | Prometheus counters/histograms (requests, LLM tokens, memory counts) |
| **Rate Limiting** | Redis ZSET sliding window, plan-aware |
| **Logging** | Structured JSON (prod) / text (dev) with request_id + tenant_id correlation |
| **Auth** | Service-to-service Bearer tokens, configurable exempt paths |
| **Cold Start** | Zero-LLM bootstrap: Git analyzer + config parser + code AST analyzer → 50+ memories |

---

## 📁 Database Schema (9 Tables)

| Table | Purpose | Key Features |
|-------|---------|-------------|
| `memories` | Core memory storage | 768-dim embedding, supersession chain, decay rate, content hash |
| `sessions` | Conversation tracking | JSONB context, LLM summary, session embedding |
| `intentions` | Prospective memory | Time/event/context triggers, expiry |
| `knowledge_gaps` | What we don't know | Query tracking, resolution linking |
| `memory_sessions` | M:N link | Which memories surfaced in which sessions |
| `job_runs` | Background job log | Status tracking, retry count, result/error JSONB |
| `tenant_usage` | Usage metering | Per-period API calls, LLM tokens, cost |
| `tenant_configs` | Tenant settings | Plan, status, cold_start_config |
| `tenant_webhooks` | Webhook registry | HMAC secret, event filter, failure count |
