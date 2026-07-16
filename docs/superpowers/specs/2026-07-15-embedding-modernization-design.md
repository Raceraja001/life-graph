# Embedding Modernization — bge-m3, Config-Driven Dimension (Track 4, Increment 1)

> **Date:** 2026-07-15
> **Status:** Approved — ready for implementation planning
> **Backlog:** `docs/design/09_operational_hardening_backlog.md` Track 4
> **Strategic basis:** `docs/design/07_strategic_direction_2026-07.md` §D6 (modernization)

## Problem

The local embedder is `all-mpnet-base-v2` (2021, 768-dim). Beyond being dated, the
model is effectively **hardcoded in three places** and the config is barely wired:

- `config.embedding_model = "all-mpnet-base-v2"` exists but is **not used to generate
  vectors**.
- `EmbeddingService.__init__` defaults to the literal `all-mpnet-base-v2`, and
  `api/dependencies.py:141` instantiates it **without** passing `settings.embedding_model`.
- `core/memory_manager.py:363` hardcodes `SentenceTransformer("all-mpnet-base-v2")`.

The pgvector column is the literal `Vector(768)` across **8 tables** (memories, sessions,
intentions, knowledge_gaps, preferences, evidence, shared_context, decisions), so any
dimension change is a code edit + migration.

## Goal

Replace the embedder with **`BAAI/bge-m3`** (1024-dim, multilingual — matters for the
developer's Tamil/Hindi content), make the vector dimension **config-driven** so future
swaps are config + one migration (never a code edit), provide a **versioned batch
re-embed job**, and a **self-consistency verification harness**. The zero-API-cost /
local-first principle is preserved (no budget gate — local inference is free).

## Design

### 1. Config = source of truth
```
embedding_model: str = "BAAI/bge-m3"
embedding_dimension: int = 1024
```
Everything derives from these two settings.

### 2. Wire config through (fix the disconnect)
- `EmbeddingService.__init__` takes `model_name` defaulting to `settings.embedding_model`
  and seeds `_dimension` from `settings.embedding_dimension`; the lazy loader still reads
  the true dimension after load (authoritative). `api/dependencies.py` passes
  `settings.embedding_model`.
- `core/memory_manager.py` uses the configured model, not the hardcoded literal.
- `Memory.embedding_model` column default → `settings.embedding_model`.

### 3. Config-driven pgvector columns
All 8 `Vector(768)` defs in `models/db.py` → `Vector(settings.embedding_dimension)`.
`models/db.py` may safely `from life_graph.config import settings` — verified no import
cycle (config imports no models).

### 4. Migration `025_embedding_dim` (null-and-rebuild, in place)
Dimension read from `settings.embedding_dimension` so migration and ORM never diverge.
1. **Drop** the pgvector indexes on the embedding columns (a dimension change invalidates
   them). Known: HNSW on memories/sessions/intentions (migration 001), ivfflat on decisions
   (020); the implementation audits all 8 tables and drops whatever exists.
2. For each of the 8 tables: `UPDATE … SET embedding = NULL` (and `embedding_model = NULL`
   where that column exists), then
   `ALTER COLUMN embedding TYPE vector(<settings.embedding_dimension>)`.
3. **Recreate** the vector indexes at the new dimension.

This clears old vectors — search is degraded until the re-embed job runs, so the job runs
immediately after (acceptable for a solo one-time migration; dual-column zero-downtime is
out of scope). `downgrade()` reverses the dimension to 768 (data stays NULL).

### 5. Versioned re-embed job — `life_graph/workers/reembed.py` (+ CLI)
- A small registry of `(model_class, text_attr)` covering the 8 embedded tables.
- Batch-iterates rows needing embedding — `embedding IS NULL`, plus (for `memories`)
  `embedding_model != settings.embedding_model` — regenerates with
  `EmbeddingService.embed_batch` (chunk 64), writes `embedding` + `embedding_model`.
- **Idempotent & resumable**: re-running only touches un-embedded/stale rows. Progress
  logged per batch. No Governor gate (local inference is free — preserves local-first).
- Registered in `workers/settings.py`; exposed as `life-graph reembed` CLI.

### 6. Verification harness — `scripts/verify_embeddings.py`
No labelled gold set exists, so verification is **self-consistency**, the "at least as good
as before" gate:
- **Dimension**: every re-embedded vector is exactly `embedding_dimension`.
- **Coverage**: no `embedding IS NULL` rows remain after the job.
- **Semantic sanity**: a fixed set of related vs unrelated text pairs — related pairs must
  score higher cosine than unrelated, and the dedup threshold (0.92) still separates known
  duplicate from non-duplicate pairs.
Run against the live DB when it is up.

### 7. Testing (unit now; live re-embed + verification deferred to the DB pass)

`tests/unit/test_embedding_config.py`:
1. `EmbeddingService` uses `settings.embedding_model` / dimension (sentence-transformers
   mocked); `get_model_info` reflects config.
2. Config-driven `Vector` dimension is reflected in the ORM column metadata
   (`Memory.__table__.c.embedding.type` dimension == `settings.embedding_dimension`).

`tests/unit/test_reembed.py`:
3. Re-embed **selection**: rows with `embedding IS NULL` or stale `embedding_model` qualify;
   fresh rows are skipped (fake session).
4. Batch chunking calls `embed_batch` with the configured chunk size.

`tests/unit/test_verify_embeddings.py`:
5. The pure ranking check: related cosine > unrelated; dedup threshold separates synthetic
   dup/non-dup vectors.

## Files touched (estimate)

- New: `life_graph/workers/reembed.py`, `scripts/verify_embeddings.py`,
  `alembic/versions/025_embedding_dim.py`, 3 test files.
- Edited: `config.py` (2 settings), `services/embeddings.py` (config-driven),
  `api/dependencies.py` (pass model), `core/memory_manager.py` (use config),
  `models/db.py` (8 Vector defs + embedding_model default + settings import),
  `workers/settings.py` (register job), `cli.py` (reembed command).

## Out of scope (later increments)

Dual-column zero-downtime swap; automatic quality gate that blocks; GPU/NPU acceleration
(Snapdragon X NPU via ONNX/QNN — a D6 "not urgent" note); re-embedding secondary tables'
history beyond what the generic job covers; benchmarking against a labelled retrieval set.
