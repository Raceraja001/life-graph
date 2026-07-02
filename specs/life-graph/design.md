# Life Graph — Design Specification

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│                                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ CLI      │  │ Web UI       │  │ IDE Extension (VS Code)   │ │
│  │ (Phase 1)│  │ (Phase 2)    │  │ (Phase 2)                 │ │
│  └─────┬────┘  └──────┬───────┘  └────────────┬──────────────┘ │
│        └───────────────┼──────────────────────┘                 │
│                        ▼                                         │
├─────────────────────────────────────────────────────────────────┤
│                    API GATEWAY (FastAPI)                          │
│                                                                  │
│  /memories  /sessions  /intentions  /recall  /import  /export   │
│  /identity  /gaps      /search      /health  /stats             │
├─────────────────────────────────────────────────────────────────┤
│                     CORE ENGINE                                  │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐  │
│  │ Memory       │ │ Extraction   │ │ Proactive Recall       │  │
│  │ Manager      │ │ Pipeline     │ │ Engine                 │  │
│  │              │ │              │ │                        │  │
│  │ CRUD ops     │ │ Tier 1: Rules│ │ Three-stage funnel:    │  │
│  │ Decay calc   │ │ Tier 2: spaCy│ │  Retrieve → Rank →    │  │
│  │ Reconsolid.  │ │ Tier 3: LLM  │ │  Rerank                │  │
│  └──────────────┘ └──────────────┘ └────────────────────────┘  │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐  │
│  │ Importance   │ │ Contradiction│ │ Intention              │  │
│  │ Tagger       │ │ Detector     │ │ Tracker                │  │
│  │              │ │              │ │                        │  │
│  │ Signal-based │ │ Embedding +  │ │ Event & time triggers  │  │
│  │ (no LLM)     │ │ regex + NER  │ │ Context matching       │  │
│  └──────────────┘ └──────────────┘ └────────────────────────┘  │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐  │
│  │ Cold Start   │ │ Consolidation│ │ Identity               │  │
│  │ Bootstrap    │ │ Pipeline     │ │ Manager                │  │
│  │              │ │              │ │                        │  │
│  │ Git analysis │ │ Nightly job: │ │ Versioned chapters     │  │
│  │ AST parsing  │ │ cluster,     │ │ Challenge intervals    │  │
│  │ Config parse │ │ dedup,       │ │ Belief states          │  │
│  │ Note import  │ │ distill,     │ │                        │  │
│  │              │ │ integrate    │ │                        │  │
│  └──────────────┘ └──────────────┘ └────────────────────────┘  │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐                              │
│  │ Query Router │ │ Metamemory   │                              │
│  │              │ │ Tracker      │                              │
│  │ Pattern-based│ │              │                              │
│  │ (no LLM)     │ │ Confidence   │                              │
│  │              │ │ Gap tracking │                              │
│  └──────────────┘ └──────────────┘                              │
├─────────────────────────────────────────────────────────────────┤
│                  STORAGE INTERFACE (Protocol)                    │
│                                                                  │
│  class MemoryStore(Protocol):                                   │
│      store() / retrieve() / update() / delete()                 │
│      search_similar() / graph_query()                           │
├─────────────────────────────────────────────────────────────────┤
│                    STORAGE LAYER                                 │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  PostgreSQL 16+                                          │   │
│  │  ├── pgvector (HNSW, halfvec(768), cosine distance)     │   │
│  │  ├── Apache AGE (Phase 2: Cypher graph queries)         │   │
│  │  ├── Core tables: memories, sessions, intentions, gaps  │   │
│  │  └── JSONB flexible properties on every table           │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐                             │
│  │ MinIO (S3)   │  │ Restic       │                             │
│  │ Multi-modal  │  │ Encrypted    │                             │
│  │ file storage │  │ backups      │                             │
│  └──────────────┘  └──────────────┘                             │
├─────────────────────────────────────────────────────────────────┤
│                   EXTERNAL INTEGRATIONS                          │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐  │
│  │ LiteLLM      │ │ CrewAI       │ │ sentence-transformers  │  │
│  │ (LLM proxy)  │ │ (agents)     │ │ (local embeddings)     │  │
│  └──────────────┘ └──────────────┘ └────────────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐                              │
│  │ spaCy        │ │ PyDriller    │                              │
│  │ (local NLP)  │ │ (Git mining) │                              │
│  └──────────────┘ └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### Core Table: `memories`

| Column | Type | Purpose |
|---|---|---|
| id | UUID (PK) | Unique identifier |
| content | TEXT | The memory content |
| reasoning | TEXT | WHY this memory exists |
| tags | TEXT[] | Open-ended tags (GIN indexed) |
| properties | JSONB | Flexible key-value metadata |
| importance | REAL [0-1] | Importance score |
| confidence | REAL [0-1] | How sure the system is |
| source_type | TEXT | inferred / mentioned / stated / explicit |
| created_at | TIMESTAMPTZ | When created |
| valid_from | TIMESTAMPTZ | When this became true |
| valid_until | TIMESTAMPTZ | When this stopped being true (NULL = current) |
| access_count | INTEGER | Times retrieved |
| last_accessed | TIMESTAMPTZ | Last retrieval time |
| decay_rate | REAL | Lambda for forgetting curve |
| source | TEXT | Provenance (session ID, import source) |
| trust_score | REAL | Source reliability |
| supersedes | UUID (FK) | Memory this replaces |
| superseded_by | UUID (FK) | Memory that replaced this |
| status | TEXT | active / superseded / uncertain / exploring / retired |
| embedding | halfvec(768) | Semantic embedding (HNSW indexed) |
| embedding_model | TEXT | Which model generated the embedding |
| owner | TEXT | User ownership |

### Supporting Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `sessions` | Track conversations/sessions | id, context (JSONB), summary, embedding |
| `intentions` | Future tasks/TODOs | id, content, trigger_type, trigger_condition, status, expires_at |
| `knowledge_gaps` | Topics the system doesn't know | id, topic, query_count, resolved |
| `memory_sessions` | Link memories to source sessions | memory_id, session_id |

---

## Component Design

### 1. Extraction Pipeline (US-1, US-9)

```
User Input → Tier 1 (Regex) → Tier 2 (spaCy NER) → Tier 3 (LLM fallback)

Tier 1: Regex patterns for explicit statements
  "I prefer X" / "I always use X" / "never use X" / "I decided X"
  → ~40% of extractions, 100% reliable, 0ms, $0

Tier 2: spaCy NER + dependency parsing
  Entity recognition, relation extraction, negation detection
  → ~40% of extractions, ~90% accurate, <50ms, $0

Tier 3: LLM (only when Tier 1+2 confidence < 0.5)
  Complex reasoning, nuanced preferences
  → ~20% of extractions, ~95% accurate, ~1s, ~$0.001/call
```

### 2. Importance Tagger (US-1, US-9)

Signal-based scoring with zero LLM dependency:

| Signal | Weight | Detection Method |
|---|---|---|
| Explicit emphasis ("IMPORTANT", "NEVER", "ALWAYS") | +0.3 | Regex |
| From failure/bug discussion | +0.2 | Keyword matching |
| Architecture decision | +0.15 | Keyword matching |
| Repeated mention (3+ times) | +0.2 | Counter |
| Cost/financial implications | +0.15 | Keyword matching |
| User said "remember this" | +0.45 | Regex |
| Hedging language ("maybe", "perhaps") | -0.2 | Regex |

### 3. Proactive Recall Engine (US-3)

Three-stage funnel adapted from Netflix/Spotify recommendation architecture:

**Stage 1 — Retrieve** (<10ms):
```sql
-- SQL WHERE for structured context match
-- pgvector ANN for semantic similarity
-- Merge + dedup → ~100 candidates
```

**Stage 2 — Rank** (multi-signal scoring):
```
final_score = 0.25 × semantic
            + 0.25 × context_match
            + 0.20 × importance
            + 0.15 × recency
            + 0.10 × frequency
            + 0.05 × trust
```

**Stage 3 — Rerank** (UX/diversity):
- Max 2 memories per topic cluster
- Mix of types (decisions + experiences + intentions)
- 7-day cooldown per memory
- Max 5 surfaces per session

### 4. Contradiction Detector (US-1)

```
New Memory → Find Similar (embedding search)
  → For each similar:
    → Negation flip? (regex)         → SUPERSEDE
    → Same slot, different value?    → PREFERENCE_CHANGE
      (spaCy NER)
    → Different scope?               → SCOPE (both valid)
    → Ambiguous?                     → ASK_USER
```

### 5. Cold Start Bootstrap (US-2)

```
Git Repos → PyDriller
  ├── Commit patterns (conventions, frequency, time-of-day)
  ├── Language/framework usage
  └── Dependency choices

Config Files → Direct parsing
  ├── pyproject.toml (ruff/black/pytest/mypy settings)
  ├── tsconfig.json (strict mode, target, jsx)
  ├── Dockerfile (multi-stage, base images)
  └── CI/CD workflows (platform, stages)

Code AST → Python ast + tree-sitter
  ├── Naming conventions
  ├── Type hint rate, docstring rate
  ├── Error handling style
  ├── Architecture pattern (MVC, clean arch, flat)
  └── Top imports and decorators

Obsidian → Markdown parser
  ├── Frontmatter extraction
  ├── Wikilink graph analysis
  ├── Decision/lesson signal detection
  └── Filter: only well-connected, decision-heavy notes
```

### 6. Consolidation Pipeline (US-6)

Runs nightly via cron. 9 steps:

| Step | Action | Uses LLM? |
|---|---|---|
| 1 | Gather: collect session buffer entries | No |
| 2 | Cluster: group by topic (embedding similarity) | No |
| 3 | Dedup: remove near-identical (cosine > 0.95) | No |
| 4 | Score: calculate importance for new entries | No |
| 5 | **Distill**: summarize clusters into principles | **Yes (1 call)** |
| 6 | Integrate: link new knowledge to graph | No |
| 7 | Decay: update forgetting curve scores | No |
| 8 | Audit: check for contradictions | No |
| 9 | Report: optional daily digest | No |

### 7. Query Router (US-9)

Pattern-based, zero LLM:

| Query Pattern | Route | Example |
|---|---|---|
| "what do I prefer/use" | Graph | "What framework do I use for APIs?" |
| "when/last time/history" | Relational | "When did I decide on PostgreSQL?" |
| "why did I" | Graph (reasoning field) | "Why did I choose JWT?" |
| "similar to/like/related" | Vector | "Find similar auth patterns" |
| "todo/remind/plan" | Intentions table | "What are my pending tasks?" |
| Default | Hybrid (all, merge with RRF) | Ambiguous queries |

### 8. Agent Bridge (US-11)

```python
class LifeGraphBridge:
    def build_agent_context(self, task: str) -> AgentContext:
        return AgentContext(
            identity=self.get_identity(),
            decisions=self.get_relevant_decisions(task),
            experience=self.get_similar_experience(task),
            intentions=self.get_triggered_intentions(task),
            warnings=self.get_anti_patterns(task),
        )

    def learn_from_task(self, result: TaskResult):
        memories = self.extract(result.conversation)
        for memory in memories:
            self.store(memory)
```

---

## Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| API Server | FastAPI | Type safety, async, auto-docs, user preference |
| Database | PostgreSQL 16+ | Unified vector + graph + relational |
| Vector Search | pgvector (halfvec, HNSW) | In-process, no sync, ACID |
| Graph (Phase 2) | Apache AGE | Cypher queries, same PostgreSQL |
| Object Storage | MinIO | S3-compatible, self-hosted |
| NLP | spaCy (en_core_web_lg) | NER, parsing, local, free |
| Embeddings | sentence-transformers (all-mpnet-base-v2) | 768d, local, free |
| LLM Routing | LiteLLM | Cheap models for grunt work |
| Agent Framework | CrewAI | Multi-agent orchestration |
| Git Analysis | PyDriller | Git mining, wraps GitPython |
| Backup | Restic | Encrypted, incremental, off-site |
| Containerization | Docker Compose | Single deploy unit |

---

## Deployment Architecture

```yaml
# docker-compose.yml structure
services:
  postgres:
    image: pgvector/pgvector:pg16
    volumes: [pg_data:/var/lib/postgresql/data]

  api:
    build: ./backend
    depends_on: [postgres]
    ports: [8000:8000]

  minio:
    image: minio/minio
    volumes: [minio_data:/data]

  consolidation:
    build: ./backend
    command: python -m life_graph.jobs.consolidation
    # Runs nightly via cron inside container
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| LLM API unavailable | Fall back to rule-based extraction only. Queue for retry. |
| Database connection lost | Return cached results. Queue writes for retry. |
| Embedding model fails | Log error, store memory without embedding, re-embed later. |
| Cold start parse error | Skip unparseable file, log warning, continue with others. |
| Contradiction resolution timeout | Default to "ask user", store with flag. |

---

## Testing Strategy

| Layer | Approach | Tools |
|---|---|---|
| Unit tests | Test extractors, scorers, routers individually | pytest |
| Integration tests | Test full pipeline (extract → store → retrieve) | pytest + testcontainers (PostgreSQL) |
| Performance tests | Measure vector search at 10K/100K/1M scale | pytest-benchmark |
| Cold start tests | Run against known Git repos, verify extraction counts | pytest + fixture repos |
| Recall quality | Ground truth dataset of memories + expected retrievals | Custom evaluation script |

---

## Security Considerations

| Threat | Mitigation |
|---|---|
| Memory poisoning | Source provenance, confidence scoring, fact audit agent |
| Data breach | Encryption at rest (TDE), TLS in transit, VPN access |
| LLM data leakage | Local models default, LiteLLM proxy controls |
| Hallucinated facts stored | `confidence: inferred` flag, requires promotion to `verified` |
| Backup theft | Restic encryption with separate key storage |
