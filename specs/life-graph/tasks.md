# Life Graph — Implementation Tasks

> Every task traces back to a requirement (US-X) and maps to a file.
> Tasks are ordered by dependency — each phase unlocks the next.

---

## Phase 1: Foundation (Week 1-2)

### 1.1 Project Setup

- [ ] **T-001**: Initialize Python project with pyproject.toml (US-9)
  - Create `pyproject.toml` with project metadata, dependencies, ruff, pytest config
  - Dependencies: fastapi, uvicorn, sqlalchemy, asyncpg, pgvector, pydantic, spacy
  - Dev dependencies: pytest, pytest-asyncio, httpx, ruff
  - Files: `pyproject.toml`

- [ ] **T-002**: Create project directory structure (US-9)
  - ```
    life_graph/
    ├── api/            # FastAPI routes
    ├── core/           # Core engine (memory manager, extractors)
    ├── models/         # SQLAlchemy models + Pydantic schemas
    ├── services/       # Business logic (recall, intentions, identity)
    ├── storage/        # Storage interface + PostgreSQL implementation
    ├── extraction/     # Fact extraction pipeline (rules, spacy, llm)
    ├── scoring/        # Importance, decay, ranking
    ├── jobs/           # Background jobs (consolidation, decay)
    ├── cold_start/     # Cold start bootstrap modules
    ├── config.py       # Settings (Pydantic BaseSettings)
    └── main.py         # FastAPI app entry point
    tests/
    ├── unit/
    ├── integration/
    └── fixtures/
    ```
  - Files: directory structure + `__init__.py` files

- [ ] **T-003**: Create Docker Compose for development (US-10)
  - PostgreSQL 16 with pgvector extension
  - MinIO for object storage
  - API server with hot reload
  - Files: `docker-compose.yml`, `Dockerfile`, `.env.example`

- [ ] **T-004**: Create database migration system (US-5)
  - Use Alembic for schema migrations
  - Initial migration creates core tables
  - Files: `alembic.ini`, `alembic/env.py`, `alembic/versions/001_initial.py`

---

### 1.2 Storage Layer

- [ ] **T-005**: Define MemoryStore Protocol interface (US-5, US-10)
  - Abstract Protocol class with: store, retrieve, update, delete, search_similar, graph_query
  - All implementations must satisfy this interface
  - Files: `life_graph/storage/protocol.py`

- [ ] **T-006**: Create SQLAlchemy models for core tables (US-5)
  - `Memory` model with all columns from design spec (JSONB properties, vector embedding, tags array)
  - `Session` model
  - `Intention` model
  - `KnowledgeGap` model
  - `MemorySession` junction model
  - Files: `life_graph/models/db.py`

- [ ] **T-007**: Create Pydantic schemas for API request/response (US-5)
  - `MemoryCreate`, `MemoryUpdate`, `MemoryResponse`
  - `SessionCreate`, `SessionResponse`
  - `IntentionCreate`, `IntentionResponse`
  - `SearchQuery`, `SearchResult`
  - `RecallContext` (for proactive recall responses)
  - Files: `life_graph/models/schemas.py`

- [ ] **T-008**: Implement PostgresMemoryStore (US-5, US-10)
  - CRUD operations for memories with JSONB property support
  - Tag-based filtering with array containment
  - Status filtering (active, superseded, etc.)
  - Bitemporal queries (valid_from, valid_until)
  - Supersession chain queries
  - Files: `life_graph/storage/postgres.py`

- [ ] **T-009**: Implement vector search with pgvector (US-1, US-3)
  - search_similar() using halfvec(768) cosine distance
  - Combined vector + relational filtering
  - Configurable ef_search for speed/recall tradeoff
  - Files: `life_graph/storage/postgres.py` (extend)

- [ ] **T-010**: Create database indexes (US-3, NFR-1)
  - HNSW index on memories.embedding (m=16, ef_construction=64)
  - GIN indexes on tags and properties
  - BTREE indexes on temporal columns, status, importance
  - Intentions indexes (status, trigger_time)
  - Files: `alembic/versions/001_initial.py` (extend)

- [ ] **T-011**: Write unit tests for storage layer (US-5)
  - Test CRUD operations
  - Test tag-based filtering
  - Test JSONB property queries
  - Test vector similarity search
  - Test supersession chains
  - Files: `tests/unit/test_storage.py`

---

### 1.3 Extraction Pipeline

- [ ] **T-012**: Implement Tier 1 regex-based extractor (US-1, US-9)
  - Patterns for: preferences, decisions, anti-preferences, explicit saves, intentions
  - Returns extracted facts with confidence scores
  - Files: `life_graph/extraction/rules.py`

- [ ] **T-013**: Implement Tier 2 spaCy NER extractor (US-1, US-9)
  - Entity recognition (technologies, frameworks, people)
  - Dependency parsing for relations ("switched from X to Y")
  - Negation detection
  - Files: `life_graph/extraction/nlp.py`

- [ ] **T-014**: Implement Tier 3 LLM fallback extractor (US-1, US-9)
  - LiteLLM integration for complex extraction
  - Only called when Tier 1+2 confidence < 0.5
  - Structured output format (JSON schema)
  - Cost tracking per call
  - Files: `life_graph/extraction/llm.py`

- [ ] **T-015**: Implement extraction orchestrator (US-1, US-9)
  - Runs Tier 1 → Tier 2 → Tier 3 with confidence thresholds
  - Combines results from all tiers
  - Deduplicates extracted facts
  - Returns list of Memory objects ready for storage
  - Files: `life_graph/extraction/pipeline.py`

- [ ] **T-016**: Write tests for extraction pipeline (US-1)
  - Test regex patterns against 20+ example sentences
  - Test spaCy extraction accuracy
  - Test tier escalation logic
  - Test deduplication
  - Files: `tests/unit/test_extraction.py`

---

### 1.4 Importance & Scoring

- [ ] **T-017**: Implement signal-based importance tagger (US-1, US-9)
  - Detect: explicit emphasis, failure/bug context, architecture decisions, repeated mentions, cost impact, explicit save requests, hedging language
  - Return importance score [0.0-1.0] and importance_tier
  - Files: `life_graph/scoring/importance.py`

- [ ] **T-018**: Implement decay score calculator (US-6)
  - Formula: `importance × (access_count^0.3) × e^(-λ × days_since_access)`
  - Configurable lambda per importance tier
  - Batch update function for nightly job
  - Files: `life_graph/scoring/decay.py`

- [ ] **T-019**: Implement retrieval ranking function (US-3)
  - Multi-signal scoring: semantic (0.25), context (0.25), importance (0.20), recency (0.15), frequency (0.10), trust (0.05)
  - Configurable weights
  - Files: `life_graph/scoring/ranking.py`

- [ ] **T-020**: Write tests for scoring modules (US-1, US-6)
  - Test importance scoring against labeled examples
  - Test decay formula correctness
  - Test ranking order with known inputs
  - Files: `tests/unit/test_scoring.py`

---

## Phase 2: Core Features (Week 3-4)

### 2.1 Proactive Recall Engine

- [ ] **T-021**: Implement context fingerprint builder (US-3)
  - Build context from: current project (Git repo), open files, active tools, current topic
  - Context similarity function (structured set overlap)
  - Files: `life_graph/services/context.py`

- [ ] **T-022**: Implement three-stage recall pipeline (US-3)
  - Stage 1 (Retrieve): SQL WHERE + pgvector ANN, top-50 candidates
  - Stage 2 (Rank): apply ranking function from T-019
  - Stage 3 (Rerank): diversity enforcement (max 2 per topic), dedup, cooldown (7 days), max per session
  - Files: `life_graph/services/recall.py`

- [ ] **T-023**: Implement trigger matcher (US-3)
  - Check time-based triggers (cron: intentions due today)
  - Check context-based triggers (project/file match against intentions)
  - Check stale memory triggers (importance >= 0.7, last accessed > 180 days)
  - Files: `life_graph/services/triggers.py`

- [ ] **T-024**: Implement anti-annoyance logic (US-3)
  - Cooldown tracker (per-memory, 7-day default)
  - Session surface counter (max 5 at start, max 2 during)
  - Category dismissal tracker (auto-suppress after 3 dismissals)
  - Confidence threshold (>0.7 only)
  - Files: `life_graph/services/recall.py` (extend)

- [ ] **T-025**: Write tests for proactive recall (US-3)
  - Test context fingerprint building
  - Test three-stage pipeline with known memories
  - Test cooldown enforcement
  - Test diversity enforcement
  - Test trigger matching (time and event-based)
  - Files: `tests/unit/test_recall.py`

---

### 2.2 Contradiction Detection

- [ ] **T-026**: Implement contradiction detector (US-1)
  - Find semantically similar existing memories (embedding search)
  - Negation flip detection (regex)
  - Entity swap detection (spaCy NER: same relation, different object)
  - Scope detection (different project/context = both valid)
  - Return conflict type: SUPERSEDE, SCOPE, ASK_USER
  - Files: `life_graph/services/contradiction.py`

- [ ] **T-027**: Implement memory supersession logic (US-1)
  - Mark old memory as superseded with reason
  - Link new memory via supersedes/superseded_by
  - Preserve full decision history
  - Files: `life_graph/core/memory_manager.py`

- [ ] **T-028**: Write tests for contradiction detection (US-1)
  - Test negation detection ("I use X" vs "I don't use X")
  - Test preference change ("I prefer Flask" vs "I prefer FastAPI")
  - Test scope handling (both valid in different contexts)
  - Files: `tests/unit/test_contradiction.py`

---

### 2.3 Intention Tracking

- [ ] **T-029**: Implement intention service (US-4)
  - Create intentions from extracted facts (type='intention')
  - Match triggers: event (context match), time (date comparison)
  - Status transitions: pending → triggered → completed/expired/dismissed
  - Files: `life_graph/services/intentions.py`

- [ ] **T-030**: Implement intention extraction from conversation (US-4)
  - Detect future-oriented language: "I should", "I will", "I need to", "remind me to", "later"
  - Extract trigger conditions (file/project references, dates)
  - Files: `life_graph/extraction/intentions.py`

- [ ] **T-031**: Write tests for intentions (US-4)
  - Test creation from various phrasings
  - Test time-based trigger matching
  - Test event-based trigger matching
  - Test status transitions
  - Files: `tests/unit/test_intentions.py`

---

### 2.4 Metamemory

- [ ] **T-032**: Implement knowledge gap tracker (US-7)
  - Track queries with low/no results
  - Increment query_count per topic
  - Detect repeated gaps (3+ queries on same topic)
  - Surface "want to teach me?" suggestions
  - Files: `life_graph/services/metamemory.py`

- [ ] **T-033**: Implement confidence-aware responses (US-7)
  - Assess result confidence based on: number of results, max confidence score, freshness
  - Return confidence tier: high (>0.7), partial (0.3-0.7), unknown (<0.3)
  - Add appropriate caveats to responses
  - Files: `life_graph/services/metamemory.py` (extend)

- [ ] **T-034**: Write tests for metamemory (US-7)
  - Test gap detection and counting
  - Test confidence assessment
  - Test "teach me" threshold
  - Files: `tests/unit/test_metamemory.py`

---

### 2.5 Query Router

- [ ] **T-035**: Implement pattern-based query router (US-9)
  - Regex patterns for graph queries ("what do I prefer/use")
  - Regex patterns for relational queries ("when/last time/history")
  - Regex patterns for reasoning queries ("why did I")
  - Regex patterns for vector queries ("similar to/like/related")
  - Regex patterns for intention queries ("todo/remind/plan")
  - Default: hybrid (fan-out to all, merge with RRF)
  - Files: `life_graph/core/router.py`

- [ ] **T-036**: Write tests for query router (US-9)
  - Test 30+ query patterns against expected routes
  - Test hybrid fallback
  - Files: `tests/unit/test_router.py`

---

## Phase 3: Cold Start & API (Week 5-6)

### 3.1 Cold Start Bootstrap

- [ ] **T-037**: Implement Git repo analyzer (US-2)
  - PyDriller-based commit analysis (conventions, time patterns, languages)
  - Dependency preference extraction (requirements.txt, pyproject.toml, package.json)
  - Files: `life_graph/cold_start/git_analyzer.py`

- [ ] **T-038**: Implement config file parser (US-2)
  - Parse pyproject.toml (ruff, black, pytest, mypy settings)
  - Parse tsconfig.json (strict, target, jsx)
  - Parse .editorconfig (indent style/size)
  - Parse Dockerfile (multi-stage, base images, alpine/slim)
  - Parse CI/CD workflows (GitHub Actions, GitLab CI)
  - Files: `life_graph/cold_start/config_parser.py`

- [ ] **T-039**: Implement code pattern analyzer (US-2)
  - Python AST visitor: naming conventions, docstring rate, type hint rate, error handling, test framework, async usage, pydantic/dataclass, top imports
  - Architecture detector: monorepo, Docker, CI, frontend/backend framework, structure pattern
  - Files: `life_graph/cold_start/code_analyzer.py`

- [ ] **T-040**: Implement Obsidian vault importer (US-2)
  - Markdown parser with frontmatter, wikilink, tag extraction
  - Decision/lesson signal detection
  - Filter: only well-connected notes with decision language
  - Files: `life_graph/cold_start/obsidian_importer.py`

- [ ] **T-041**: Implement cold start orchestrator (US-2)
  - Single entry point accepting config (repos, vault path, author filter)
  - Runs all analyzers sequentially
  - Deduplicates results
  - Generates embeddings (local sentence-transformers)
  - Stores all memories in PostgreSQL
  - Reports summary (count, time, categories)
  - Files: `life_graph/cold_start/bootstrap.py`

- [ ] **T-042**: Write tests for cold start (US-2)
  - Test Git analysis against a known fixture repo
  - Test config parsing against sample files
  - Test AST analysis against sample Python files
  - Test Obsidian import against a sample vault
  - Test full orchestrator end-to-end
  - Files: `tests/unit/test_cold_start.py`, `tests/fixtures/`

---

### 3.2 FastAPI Routes

- [ ] **T-043**: Implement memory CRUD routes (US-1)
  - `POST /memories` — create memory
  - `GET /memories/{id}` — get by ID
  - `PATCH /memories/{id}` — update memory
  - `DELETE /memories/{id}` — cascade delete
  - `GET /memories` — list with filters (tags, status, domain, date range)
  - Files: `life_graph/api/memories.py`

- [ ] **T-044**: Implement search routes (US-1, US-3)
  - `POST /search` — semantic search with optional filters
  - `POST /recall` — proactive recall for current context
  - `GET /recall/session-start` — session start context load
  - Files: `life_graph/api/search.py`

- [ ] **T-045**: Implement intention routes (US-4)
  - `POST /intentions` — create intention
  - `GET /intentions` — list pending intentions
  - `PATCH /intentions/{id}` — update status (complete, dismiss)
  - `GET /intentions/triggered` — get currently triggered intentions
  - Files: `life_graph/api/intentions.py`

- [ ] **T-046**: Implement identity routes (US-8)
  - `GET /identity` — get current identity layer
  - `GET /identity/timeline` — get identity evolution history
  - `POST /identity/challenge` — trigger challenge check
  - Files: `life_graph/api/identity.py`

- [ ] **T-047**: Implement import/export routes (US-2, US-10)
  - `POST /import/cold-start` — trigger cold start bootstrap
  - `POST /import/obsidian` — import Obsidian vault
  - `GET /export/full` — full export (Markdown + JSON)
  - `GET /export/memories` — export memories as JSON
  - Files: `life_graph/api/io.py`

- [ ] **T-048**: Implement admin/stats routes (US-10, NFR-4)
  - `GET /health` — health check
  - `GET /stats` — memory count, API cost, gap count
  - `GET /stats/cost` — daily LLM cost breakdown
  - `GET /gaps` — knowledge gaps list
  - Files: `life_graph/api/admin.py`

- [ ] **T-049**: Implement API middleware (US-10)
  - Request logging
  - Error handling with structured responses
  - CORS configuration
  - Rate limiting (optional)
  - Files: `life_graph/api/middleware.py`

- [ ] **T-050**: Write API integration tests (US-1)
  - Test all CRUD endpoints
  - Test search with various queries
  - Test recall context building
  - Test import/export round-trip
  - Files: `tests/integration/test_api.py`

---

### 3.3 Agent Bridge

- [ ] **T-051**: Implement LifeGraphBridge (US-11)
  - `build_agent_context(task_description)` → returns AgentContext
  - `learn_from_task(task_result)` → extracts and stores new memories
  - Configurable context injection (which layers to include)
  - Files: `life_graph/services/agent_bridge.py`

- [ ] **T-052**: Implement CrewAI integration (US-11)
  - Custom CrewAI Tool wrapping LifeGraphBridge
  - Callback hooks for task start (inject context) and task end (extract knowledge)
  - LiteLLM configuration for cost-optimized routing
  - Files: `life_graph/integrations/crewai.py`

- [ ] **T-053**: Write tests for agent bridge (US-11)
  - Test context building with known memories
  - Test knowledge extraction from sample conversations
  - Files: `tests/unit/test_agent_bridge.py`

---

## Phase 4: Background Jobs & Polish (Week 7-8)

### 4.1 Consolidation Pipeline

- [ ] **T-054**: Implement session buffer collector (US-6)
  - Gather all memories created in current day's sessions
  - Files: `life_graph/jobs/consolidation.py`

- [ ] **T-055**: Implement memory clustering (US-6)
  - Group memories by embedding similarity (threshold 0.75)
  - Uses sentence-transformers locally
  - Files: `life_graph/jobs/consolidation.py` (extend)

- [ ] **T-056**: Implement deduplication (US-6)
  - Remove near-identical entries (cosine > 0.95)
  - Keep most detailed version
  - Files: `life_graph/jobs/consolidation.py` (extend)

- [ ] **T-057**: Implement LLM distillation step (US-6)
  - For clusters with 3+ memories: distill into 1 principle
  - Uses cheap model (Gemini Flash / GPT-4o-mini via LiteLLM)
  - Track API cost
  - Files: `life_graph/jobs/consolidation.py` (extend)

- [ ] **T-058**: Implement decay batch update (US-6)
  - Update decay scores for all active memories
  - Archive memories below threshold (except critical tier)
  - Files: `life_graph/jobs/decay.py`

- [ ] **T-059**: Implement consolidation scheduler (US-6)
  - APScheduler or cron-based nightly execution
  - Configurable schedule
  - Logging and error handling
  - Files: `life_graph/jobs/scheduler.py`

- [ ] **T-060**: Write tests for consolidation pipeline (US-6)
  - Test clustering correctness
  - Test dedup threshold
  - Test decay formula at various ages
  - Test archival logic (critical tier exempt)
  - Files: `tests/unit/test_consolidation.py`

---

### 4.2 Identity Management

- [ ] **T-061**: Implement identity service (US-8)
  - Identity timeline storage (chapters with periods, beliefs, triggers)
  - Current chapter retrieval
  - Challenge interval checking (6 months default)
  - Belief state transitions
  - Files: `life_graph/services/identity.py`

- [ ] **T-062**: Implement challenge generator (US-8)
  - Find identity memories past challenge interval
  - Generate challenge prompts
  - Track challenge responses
  - Files: `life_graph/services/identity.py` (extend)

- [ ] **T-063**: Write tests for identity management (US-8)
  - Test chapter creation and transitions
  - Test challenge interval detection
  - Test belief state changes
  - Files: `tests/unit/test_identity.py`

---

### 4.3 Embedding Management

- [ ] **T-064**: Implement local embedding service (US-9)
  - sentence-transformers integration (all-mpnet-base-v2)
  - Batch embedding support
  - Model version tracking
  - Files: `life_graph/services/embeddings.py`

- [ ] **T-065**: Implement embedding migration support (US-9)
  - Version-tagged embeddings per memory
  - Lazy re-embedding on access
  - Background batch re-indexing job
  - Files: `life_graph/services/embeddings.py` (extend)

- [ ] **T-066**: Write tests for embedding service (US-9)
  - Test embedding generation
  - Test batch processing
  - Test model version tracking
  - Files: `tests/unit/test_embeddings.py`

---

### 4.4 Reconsolidation

- [ ] **T-067**: Implement memory-on-access updates (US-6)
  - On retrieval: increment access_count, update last_accessed
  - Enrich with current context (append to related_contexts)
  - Check for contradictions with current context
  - Optionally re-embed with accumulated context
  - Files: `life_graph/core/memory_manager.py` (extend)

---

### 4.5 Documentation & DevOps

- [ ] **T-068**: Write API documentation (NFR)
  - OpenAPI spec auto-generated from FastAPI
  - README with setup instructions
  - Environment variable documentation
  - Files: `README.md`, `docs/api.md`

- [ ] **T-069**: Create backup automation (NFR-3)
  - pg_dump script (daily)
  - Restic encrypted off-site backup
  - Restore verification script
  - Files: `scripts/backup.sh`, `scripts/restore.sh`

- [ ] **T-070**: Create CI pipeline (NFR)
  - GitHub Actions: lint, test, build
  - PostgreSQL service container for integration tests
  - Files: `.github/workflows/ci.yml`

---

## Phase 5: Enhancements (Month 3+)

### 5.1 Apache AGE Graph Layer

- [ ] **T-071**: Install and configure Apache AGE (US-1)
  - Add AGE extension to PostgreSQL
  - Create life_graph graph schema
  - Create vertex labels: Entity, Person, Project, Technology, Decision, Concept
  - Create edge labels: prefers, uses, decided, related_to, supersedes, knows, part_of, based_on, conflicts_with
  - Files: `alembic/versions/xxx_add_age_graph.py`

- [ ] **T-072**: Implement graph query support (US-1)
  - Cypher query execution via AGE
  - Entity CRUD (create/update/delete vertices and edges)
  - Graph traversal queries (multi-hop relationships)
  - Files: `life_graph/storage/graph.py`

- [ ] **T-073**: Implement hybrid queries (US-1, US-3)
  - Graph narrows scope → vector search within scope
  - Combined CTE queries (graph + vector + relational)
  - Files: `life_graph/storage/hybrid.py`

- [ ] **T-074**: Migrate existing data to graph (US-1)
  - Extract entities from existing memories' tags and properties
  - Create graph vertices and edges
  - Link graph nodes to memories via UUID
  - Files: `life_graph/jobs/graph_migration.py`

---

### 5.2 Web UI

- [ ] **T-075**: Design web UI for memory browsing (US-5)
  - Memory list with search, filter, sort
  - Memory detail view with edit capability
  - Intention list with complete/dismiss actions
  - Knowledge gap list
  - Identity timeline visualization
  - Stats dashboard (memory count, cost, gaps)

- [ ] **T-076**: Implement web UI (US-5)
  - Next.js frontend
  - FastAPI backend API consumed via fetch
  - Files: `frontend/`

---

### 5.3 Multi-Modal (Phase 2)

- [ ] **T-077**: Implement voice note processing (US-12)
  - Whisper STT transcription (local)
  - Store transcript + audio in MinIO
  - Embed transcript as regular memory
  - Files: `life_graph/services/multimodal.py`

- [ ] **T-078**: Implement screenshot/image processing (US-12)
  - OCR via Tesseract/PaddleOCR
  - CLIP embedding for visual similarity
  - Store original in MinIO, embedding in PostgreSQL
  - Files: `life_graph/services/multimodal.py` (extend)

---

### 5.4 Plugin Architecture (Phase 2)

- [ ] **T-079**: Implement EventBus (US-13)
  - Event types: memory:created, memory:retrieved, memory:updated, memory:deleted, session:start, session:end
  - Subscribe/unsubscribe API
  - Async event dispatch
  - Files: `life_graph/core/events.py`

- [ ] **T-080**: Implement plugin loader (US-13)
  - Discover plugins from plugins/ directory
  - Load and register event handlers
  - Plugin configuration support
  - Files: `life_graph/core/plugins.py`

---

## Summary

| Phase | Tasks | Duration | Deliverable |
|---|---|---|---|
| Phase 1: Foundation | T-001 → T-020 | Week 1-2 | Storage, extraction, scoring working |
| Phase 2: Core Features | T-021 → T-036 | Week 3-4 | Recall, contradictions, intentions, metamemory, router |
| Phase 3: Cold Start & API | T-037 → T-053 | Week 5-6 | Full API, cold start, agent bridge |
| Phase 4: Jobs & Polish | T-054 → T-070 | Week 7-8 | Consolidation, identity, backup, CI |
| Phase 5: Enhancements | T-071 → T-080 | Month 3+ | Graph layer, web UI, multi-modal, plugins |

**Total: 80 tasks across 5 phases.**
**MVP (Phases 1-3): 53 tasks in 6 weeks → usable system.**
**Full system (Phases 1-4): 70 tasks in 8 weeks → production-ready.**
