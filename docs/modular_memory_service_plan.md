# Architecture Plan: Modular Memory Core & Domain Decoupling

## 1. Executive Summary

Life Graph is designed as a brain-inspired memory engine for AI agents with biological decay, 3-tier extraction, contradiction detection, and consolidation. 

Over time, extended domains (Jarvis assistant, Financial tracking, Spaced repetition study, Autonomous kernel drivers, and Web watchers) were integrated into the same monolithic FastAPI startup, introducing 105 database tables, MinIO object storage, Redis, and multi-service startup fragility.

This plan details how to **decouple the Core Memory Engine** into an isolated, sub-50ms service while **keeping 100% of the extended domain code intact** in modular tiers.

---

## 2. Target Architecture: Two-Tier Modular System

```
                      [ External Clients ]
          (DevBot / Dify, PandaCode, Aider, Claude Code, CLI)
                               │
                ┌──────────────┴──────────────┐
                │ REST API (/api/v1/)         │ Model Context Protocol (MCP)
                │ (FastAPI Port 8080)         │ (life_graph/mcp_server.py)
                └──────────────┬──────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                   TIER 1: CORE MEMORY ENGINE                          │
│                                                                       │
│  [API Routers]                                                        │
│  • api/memories.py      -> Store, approve, update, delete memories    │
│  • api/search.py        -> Hybrid vector (pgvector) + lexical recall  │
│  • api/preferences.py   -> Explicit user preferences                  │
│  • api/identity.py      -> Belief evolution & identity timeline       │
│  • api/capture.py       -> Fast capture event intake                  │
│  • api/graph.py         -> Entity relationship queries                │
│                                                                       │
│  [Core Services]                                                      │
│  • services/embeddings.py     -> Fast local/remote embedding          │
│  • services/recall.py         -> 6-signal ranking & decay scoring     │
│  • services/contradiction.py  -> Auto-supersedes conflicting facts    │
│  • services/distillation.py   -> Memory consolidation                 │
│                                                                       │
│  [Storage Requirement]                                                │
│  • PostgreSQL 16 with pgvector only (Zero MinIO / Zero Redis needed)  │
└──────────────────────────────┬────────────────────────────────────────┘
                               │
               (Clean Internal Python API / Events)
                               │
┌──────────────────────────────▼────────────────────────────────────────┐
│                  TIER 2: EXTENDED DOMAIN MODULES                      │
│               (Pluggable • Optional • Load on Demand)                 │
├───────────────────────────────────────────────────────────────────────┤
│  • Jarvis Domain     -> api/jarvis.py, services/jarvis_*              │
│  • Finance Domain    -> api/invoices.py, services/money.py            │
│  • Study Domain      -> services/study.py, api/study                  │
│  • Kernel / Tasks    -> api/kernel.py, api/drivers.py, kernel/        │
│  • Watchers Domain   -> api/watchers.py, watchers/                    │
│                                                                       │
│  [Storage Requirement]                                                │
│  • Optional: MinIO (document uploads), Redis (job queues)             │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 3. Implementation Phases

### Phase 1: Profile-Based Router Loading in `life_graph/config.py` & `main.py`
Add a configuration flag `LIFE_GRAPH_PROFILE` (values: `memory_core` | `full`, default: `memory_core`):
* In `memory_core` mode:
  * Only registers the core memory routers: `memories`, `search`, `preferences`, `identity`, `capture`, `graph`, and `health`.
  * Skips loading heavy external dependencies like MinIO clients, S3 buckets, and Celery/ARQ workers on boot.
* In `full` mode:
  * Boots all 40+ routers as currently configured.

### Phase 2: Memory Service Enhancements

#### A. Fast-Path Ingestion Pipeline
* In `api/memories.py`:
  * Fast verbatim write: store content + tags immediately in PostgreSQL table (`capture_events` / `memories`).
  * Return `201 Created` with memory ID in `<15ms`.
  * Asynchronously schedule vector embedding generation in the background so callers (like DevBot) never wait for embedding models.

#### B. Standalone Model Context Protocol (MCP) Server
* Enhance `life_graph/mcp_server.py`:
  * Support both stdio (`python -m life_graph.mcp_server`) and SSE transports.
  * Standardize MCP tools:
    * `remember(content: str, importance: float, tags: list[str])`
    * `recall(query: str, limit: int)`
    * `get_profile(category: str)`
  * Enables zero-glue integration into PandaCode, Claude Code, Aider, and Cursor.

#### C. Dedicated Memory Health & Telemetry
* Add `/api/v1/health/memory` endpoint:
  * Checks: Postgres connectivity, pgvector extension status, embedding backend responsiveness, active memory count, and last consolidation run.

#### D. Active Contradiction Resolution
* Wire `services/contradiction.py` into the ingestion pipeline:
  * When a new preference or factual belief is stored, compare against existing memories in the same category.
  * If a conflict is detected with high confidence (>0.85), automatically flag the older memory with `superseded_by: new_id` instead of storing contradictory duplicates.

---

## 4. Verification Checklist

1. **Boot Time & Resource Usage:**
   - Under `LIFE_GRAPH_PROFILE=memory_core`, FastAPI startup drops to `<1.5s` and memory usage drops to `<200MB`.
2. **Ingestion Latency:**
   - `POST /api/v1/memories/` returns `<30ms`.
3. **Recall Latency:**
   - `POST /api/v1/search/` with hybrid search returns `<150ms`.
4. **MCP Validation:**
   - Connect MCP server from CLI / IDE inspector and successfully call `recall` and `remember`.
