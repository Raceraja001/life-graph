# 🧠 Life Graph

> **A brain-inspired memory microservice that gives AI agents persistent, evolving memory.**

Life Graph is a multi-tenant SaaS backend that stores, scores, searches, and evolves memories — so every AI agent you build can remember users permanently across conversations.

---

## ✨ What Makes This Different

| Feature | Life Graph | Typical RAG |
|---------|-----------|-------------|
| **Extraction** | 3-tier pipeline (regex → spaCy → LLM fallback). 85% of operations need zero LLM calls | Stuff everything in a vector DB |
| **Scoring** | Rule-based importance tiers (critical/high/normal/low) with additive/subtractive signals | Everything treated equally |
| **Recall** | Proactive 6-signal ranking with anti-annoyance (cooldowns, caps, dismissal tracking) | Naive top-k similarity |
| **Decay** | Exponential forgetting curve. Low-value memories archive automatically | Never forgets anything |
| **Consolidation** | Nightly 7-step "sleep cycle" — cluster, dedup, re-score, distill, audit | No maintenance |
| **Contradiction** | Detects conflicting memories, auto-supersedes or asks user | Stores duplicates forever |
| **Identity** | Tracks belief evolution over time with challenge system | No concept of identity |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                  │
│  memories · sessions · search · intentions · identity   │
│  graph · agent · multimodal · admin · websocket         │
├─────────────────────────────────────────────────────────┤
│               Middleware Stack (5 layers)                │
│  RequestID → Auth → Tenant → RateLimit → Logging        │
├─────────────────────────────────────────────────────────┤
│                   Service Layer (12)                     │
│  MemoryManager · RecallEngine · ContradictionDetector    │
│  IdentityService · IntentionService · EmbeddingService   │
│  SynthesisService · MultiModalService · LMStudioClient   │
├──────────────┬──────────────┬───────────────────────────┤
│  Extraction  │   Scoring    │     Background Jobs       │
│  3-tier      │  Importance  │  Consolidation (3AM)      │
│  pipeline    │  Ranking     │  Decay sweep (4AM)        │
│              │  Decay       │  Async embeddings         │
├──────────────┴──────────────┴───────────────────────────┤
│                    Storage Layer                         │
│  PostgreSQL+pgvector · Apache AGE · Redis · MinIO       │
└─────────────────────────────────────────────────────────┘
```

**Tech Stack:** Python 3.11+ · FastAPI · PostgreSQL + pgvector · Apache AGE · Redis · ARQ · spaCy · MinIO · Prometheus

---

## 🚀 Quick Start

```bash
# Clone & start with Docker
git clone <repo-url> && cd agents
cp .env.example .env
docker compose up -d

# Run migrations
docker compose exec app alembic upgrade head

# Verify
curl http://localhost:8000/health
```

```bash
# Create your first memory
curl -X POST http://localhost:8000/api/v1/memories/ \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: demo' \
  -d '{"content": "I prefer dark mode and use Vim keybindings", "source_type": "manual"}'

# Search it
curl -X POST http://localhost:8000/api/v1/search/ \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: demo' \
  -d '{"query": "what editor does the user prefer?"}'
```

📖 **Full setup guide:** [docs/QUICKSTART.md](docs/QUICKSTART.md)

---

## 📊 Feature Overview

### Core Memory System
| Feature | Description |
|---------|-------------|
| **Memory CRUD** | Create, read, update, delete, list with filters |
| **Semantic Search** | pgvector cosine similarity with status/date/tag filters |
| **Proactive Recall** | AI pushes relevant memories at session start |
| **Natural Language Q&A** | "What does the user think about X?" → synthesized answer |
| **Sessions** | Conversation tracking with memory linking |

### Intelligence Pipeline
| Feature | Description |
|---------|-------------|
| **3-Tier Extraction** | Regex (40+ patterns) → spaCy NLP → LLM fallback |
| **Importance Scoring** | Rule-based with 4 tiers: critical/high/normal/low |
| **Deduplication** | SHA-256 exact + cosine near-match (≥0.92) with smart merge |
| **Contradiction Detection** | Finds conflicts, auto-supersedes or asks user |
| **Memory Decay** | Exponential forgetting curve, nightly sweep at 04:00 UTC |
| **Nightly Consolidation** | 7-step "sleep cycle" for memory maintenance |

### Advanced Features
| Feature | Description |
|---------|-------------|
| **Intentions** | Prospective memory with time/event/context triggers |
| **Identity & Beliefs** | Timeline tracking, stale belief detection, challenge system |
| **Knowledge Graph** | Apache AGE Cypher queries, hybrid graph+vector search |
| **Multi-Modal** | Voice (Whisper), image (OCR), document (PDF/MD/TXT) ingestion |
| **Agent Integration** | Context building + learning endpoints for AI agents |
| **WebSocket** | Real-time event streaming via Redis pub/sub |

### SaaS Infrastructure
| Feature | Description |
|---------|-------------|
| **Multi-Tenancy** | Full data isolation, plan-based limits, lifecycle management |
| **Webhooks** | HMAC-SHA256 signed, circuit breaker, 11 event types |
| **Rate Limiting** | Redis sliding window, per-tenant, plan-aware |
| **Bulk Operations** | Import (500 max), delete with dry-run |
| **Streaming Export** | NDJSON streaming, no OOM at 100K+ memories |
| **Cold Start** | Zero-LLM bootstrap from Git/config/code analysis → 50+ memories |

---

## 📁 Project Structure

```
life_graph/
├── api/              # 45 API endpoints (9 route files + WebSocket)
│   ├── memories.py   # Memory CRUD
│   ├── sessions.py   # Session management
│   ├── search.py     # Semantic search + recall + Q&A
│   ├── intentions.py # Prospective memory
│   ├── identity.py   # Belief tracking
│   ├── graph.py      # Knowledge graph queries
│   ├── agent.py      # Agent integration
│   ├── multimodal.py # Voice/image/document ingestion
│   ├── admin.py      # Operations, webhooks, tenants, bulk ops
│   ├── websocket.py  # Real-time event streaming
│   └── middleware.py  # 5-layer middleware stack
├── core/             # Business logic
│   ├── memory_manager.py  # Primary ingestion orchestrator
│   ├── events.py     # Async EventBus (11 event types)
│   ├── rate_limit.py # Redis sliding window
│   ├── metrics.py    # Prometheus counters/histograms
│   └── tenant.py     # Multi-tenant context
├── extraction/       # 3-tier extraction pipeline
│   ├── pipeline.py   # Orchestrator
│   ├── rules.py      # Tier 1: 40+ regex patterns
│   ├── nlp.py        # Tier 2: spaCy NER + dependency parsing
│   ├── llm.py        # Tier 3: LLM fallback
│   └── intentions.py # Intention extraction
├── scoring/          # Importance + ranking + decay
├── services/         # 12 service modules
├── storage/          # Postgres, AGE, Redis, MinIO, Hybrid
├── workers/          # ARQ background tasks + cron jobs
├── jobs/             # Nightly consolidation pipeline
├── cold_start/       # Zero-LLM project bootstrapping
├── integrations/     # Webhook delivery
└── models/           # SQLAlchemy models + Pydantic schemas
```

---

## 🧪 Testing

```bash
# All tests (107 files, 87 integration tests)
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](docs/QUICKSTART.md) | Setup guide with Docker and local dev instructions |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture with data flow diagrams |
| [CHANGELOG.md](CHANGELOG.md) | Version history and API versioning policy |
| [FEATURES.md](docs/FEATURES.md) | Exhaustive feature catalog (45+ endpoints) |

### Research & Design
| Document | Description |
|----------|-------------|
| [Build vs Buy Analysis](docs/research/01_build_vs_buy_analysis.md) | Should we build or use existing tools? |
| [Open Source Evaluation](docs/research/02_open_source_evaluation.md) | 7 projects evaluated for forking |
| [Memory Mechanisms](docs/research/04_memory_mechanisms.md) | Vector DB vs KG vs Relational comparison |
| [Architecture Design](docs/design/02_life_graph_v2_design.md) | 8 brain-inspired innovations |
| [Devil's Advocate Review](docs/design/03_devils_advocate_review.md) | 15 weaknesses and fixes |

---

## 🔑 Key Design Principles

1. **LLM as advisor, not authority** — 85% of operations are rule-based (regex, spaCy, heuristics)
2. **Schema-less core** — JSONB properties, no hardcoded domains or types
3. **Brain-inspired cycles** — consolidation, decay, proactive recall mirror neuroscience
4. **Multi-tenant isolation** — every query scoped, every layer tenant-aware
5. **Event-driven** — pub/sub EventBus with plugin system for extensions
6. **Cost-efficient** — local spaCy + sentence-transformers for most work, LLM only when needed
7. **Future-proof data** — versioned embeddings, standard APIs, fully exportable

---

## ⚙️ Configuration

All settings via environment variables prefixed with `LIFE_GRAPH_`:

```bash
LIFE_GRAPH_ENVIRONMENT=production
LIFE_GRAPH_LOG_FORMAT=json
LIFE_GRAPH_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
LIFE_GRAPH_REDIS_URL=redis://host:6379/0
LIFE_GRAPH_SERVICE_API_KEYS=key1,key2
LIFE_GRAPH_DEDUP_ENABLED=true
LIFE_GRAPH_DEDUP_THRESHOLD=0.92
```

---

## 📜 License

MIT

---

*Built with ❤️ as a personal project to give AI agents the memory they deserve.*
