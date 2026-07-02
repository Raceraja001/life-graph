# 04 — Database Schema Design

## PostgreSQL + pgvector + Apache AGE — Unified Memory Store

> [!IMPORTANT]
> Life Graph uses a **single PostgreSQL process** running three engines simultaneously:
> 1. **Standard relational** — tables, indexes, ACID transactions
> 2. **pgvector** — HNSW approximate nearest neighbor search on embeddings
> 3. **Apache AGE** — Cypher-queryable property graph
>
> No separate databases. No network hops. One connection string.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    PostgreSQL 16+                        │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Relational   │  │   pgvector   │  │  Apache AGE   │  │
│  │              │  │              │  │               │  │
│  │  memories     │  │  HNSW index  │  │  life_graph   │  │
│  │  sessions     │  │  halfvec     │  │  (Cypher)     │  │
│  │  intentions   │  │  ANN search  │  │               │  │
│  │  knowledge_   │  │              │  │  Vertices:    │  │
│  │    gaps       │  │              │  │   Entity      │  │
│  │              │  │              │  │   Person      │  │
│  │              │  │              │  │   Project     │  │
│  │              │  │              │  │   ...         │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                 │                  │          │
│         └────── Shared UUIDs (Bridge) ───────┘          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Extension Loading

```sql
-- Enable pgvector for embedding storage and ANN search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable Apache AGE for property graph (Phase 2)
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE into search path for Cypher queries
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
```

### The Bridge Pattern

AGE stores its own internal tables — you **cannot** create formal foreign keys between AGE vertices and relational tables. Instead, we use **shared UUIDs**:

- Every relational row has a UUID primary key
- AGE vertices store that same UUID as a property (`uuid`)
- Cross-referencing is done via: query graph → extract UUIDs → join with relational tables

> [!NOTE]
> This is intentional, not a limitation. It keeps the two systems decoupled — you can run Phase 1 (relational + pgvector only) without AGE, and add the graph layer later without schema changes.

---

## 2. Phase 1: Relational + Vector Schema

### 2.1 Memories Table

The core table. Every piece of knowledge the system stores.

```sql
CREATE TABLE memories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content
    content         TEXT NOT NULL,           -- The memory itself (natural language)
    reasoning       TEXT,                    -- Why this was stored / source context

    -- Classification (schema-less — no enums)
    tags            TEXT[] DEFAULT '{}',     -- Dynamic tags: ['preference', 'python', 'fastapi']
    properties      JSONB DEFAULT '{}',      -- Escape hatch for arbitrary metadata

    -- Scoring
    importance      REAL DEFAULT 0.5,        -- 0.0 to 1.0, updated by access patterns + feedback
    confidence      REAL DEFAULT 1.0,        -- 0.0 to 1.0, decays with contradictions

    -- Bitemporal fields
    valid_from      TIMESTAMPTZ DEFAULT now(),  -- When this fact became true
    valid_until     TIMESTAMPTZ,                -- When this fact stopped being true (NULL = still valid)

    -- System timestamps
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),

    -- Access tracking (for decay/frequency scoring)
    access_count    INTEGER DEFAULT 0,

    -- Vector embedding (sentence-transformers: all-mpnet-base-v2 = 768d)
    embedding       vector(768),

    -- Lifecycle
    status          TEXT DEFAULT 'active',   -- 'active', 'dormant', 'superseded', 'archived'

    -- Supersession chain
    supersedes      UUID REFERENCES memories(id),   -- This memory replaces...
    superseded_by   UUID REFERENCES memories(id)    -- ...and was replaced by
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER memories_updated_at
    BEFORE UPDATE ON memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

> [!TIP]
> **Why TEXT instead of ENUM for `status`?** Enums require migrations to add new values. TEXT with application-level validation is more flexible for a schema-less system. New statuses can be added without touching the database.

> [!TIP]
> **Why TEXT[] for tags?** Arrays with GIN indexes give us fast containment queries (`tags @> ARRAY['python']`) without needing a separate tags table or join. Adding new tag categories requires zero schema changes.

### 2.2 Sessions Table

Tracks interaction sessions for context-dependent retrieval.

```sql
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      TIMESTAMPTZ DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    context         JSONB DEFAULT '{}',      -- {"project": "life-graph", "tools": ["vscode"], ...}
    summary         TEXT,                    -- Auto-generated session summary
    embedding       vector(768)              -- Session context embedding for similarity search
);
```

### 2.3 Intentions Table

Prospective memory — things the system should remind you about.

```sql
CREATE TABLE intentions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content             TEXT NOT NULL,            -- "Review FastAPI migration decision"
    trigger_type        TEXT NOT NULL,            -- 'time', 'context', 'event', 'cron'
    trigger_condition   TEXT,                     -- Human-readable condition description
    trigger_time        TIMESTAMPTZ,              -- For time-based triggers
    context_match       JSONB DEFAULT '{}',       -- For context-based triggers
    status              TEXT DEFAULT 'pending',   -- 'pending', 'triggered', 'completed', 'dismissed'
    embedding           vector(768),
    created_at          TIMESTAMPTZ DEFAULT now()
);
```

### 2.4 Knowledge Gaps Table

Metamemory — the system tracks what it *doesn't* know.

```sql
CREATE TABLE knowledge_gaps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic           TEXT NOT NULL,
    query_count     INTEGER DEFAULT 1,       -- How many times this gap was hit
    resolved        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);
```

### 2.5 Memory-Sessions Junction Table

Links memories to the sessions where they were created or accessed.

```sql
CREATE TABLE memory_sessions (
    memory_id       UUID REFERENCES memories(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    PRIMARY KEY (memory_id, session_id)
);
```

---

## 3. Indexes

### 3.1 HNSW Vector Indexes (halfvec Optimization)

```sql
-- Memories: HNSW on halfvec cast — 50% storage reduction, <1% recall loss
CREATE INDEX idx_memories_embedding_hnsw
    ON memories
    USING hnsw ((embedding::halfvec(768)) halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Sessions: HNSW for session context similarity
CREATE INDEX idx_sessions_embedding_hnsw
    ON sessions
    USING hnsw ((embedding::halfvec(768)) halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Intentions: HNSW for matching intentions to current context
CREATE INDEX idx_intentions_embedding_hnsw
    ON intentions
    USING hnsw ((embedding::halfvec(768)) halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

### 3.2 GIN Indexes (Tags + JSONB)

```sql
-- Fast tag containment queries: WHERE tags @> ARRAY['python', 'preference']
CREATE INDEX idx_memories_tags_gin ON memories USING gin (tags);

-- Fast JSONB path queries: WHERE properties @> '{"domain": "coding"}'
CREATE INDEX idx_memories_properties_gin ON memories USING gin (properties jsonb_path_ops);

-- Session context queries
CREATE INDEX idx_sessions_context_gin ON sessions USING gin (context jsonb_path_ops);

-- Intention context matching
CREATE INDEX idx_intentions_context_gin ON intentions USING gin (context_match jsonb_path_ops);
```

### 3.3 B-Tree Indexes (Temporal, Status, Scoring)

```sql
-- Temporal queries
CREATE INDEX idx_memories_created_at ON memories (created_at DESC);
CREATE INDEX idx_memories_valid_from ON memories (valid_from DESC);
CREATE INDEX idx_memories_valid_until ON memories (valid_until)
    WHERE valid_until IS NOT NULL;

-- Status filtering (most queries filter by status='active')
CREATE INDEX idx_memories_status ON memories (status);

-- Importance scoring (for proactive recall candidate generation)
CREATE INDEX idx_memories_importance ON memories (importance DESC)
    WHERE status = 'active';

-- Intentions: due triggers
CREATE INDEX idx_intentions_trigger_time ON intentions (trigger_time)
    WHERE status = 'pending' AND trigger_time IS NOT NULL;

-- Intentions: status filtering
CREATE INDEX idx_intentions_status ON intentions (status);

-- Knowledge gaps: unresolved
CREATE INDEX idx_knowledge_gaps_unresolved ON knowledge_gaps (query_count DESC)
    WHERE resolved = FALSE;

-- Sessions: temporal range
CREATE INDEX idx_sessions_started_at ON sessions (started_at DESC);
```

---

## 4. Phase 2: Apache AGE Graph Schema

> [!IMPORTANT]
> Phase 2 is additive — it does NOT modify any Phase 1 tables. All existing queries continue to work unchanged. The graph layer provides relationship traversal capabilities on top of the existing relational + vector store.

### 4.1 Create the Graph

```sql
-- Load AGE extension (if not already done)
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create the Life Graph
SELECT create_graph('life_graph');
```

### 4.2 Vertex Labels

```sql
-- Core entity types (these are labels, not enums — any vertex can have any properties)
SELECT create_vlabel('life_graph', 'Entity');
SELECT create_vlabel('life_graph', 'Person');
SELECT create_vlabel('life_graph', 'Project');
SELECT create_vlabel('life_graph', 'Technology');
SELECT create_vlabel('life_graph', 'Decision');
SELECT create_vlabel('life_graph', 'Concept');
SELECT create_vlabel('life_graph', 'Memory');
```

Each vertex stores properties including the **bridge UUID** that links back to the relational tables:

```sql
-- Example: creating a vertex linked to a relational memory
SELECT * FROM cypher('life_graph', $$
    CREATE (m:Memory {
        uuid: 'a1b2c3d4-...',
        content: 'Prefers FastAPI over Django for new projects',
        created_at: '2024-01-15T10:30:00Z'
    })
    RETURN m
$$) AS (v agtype);
```

### 4.3 Edge Labels

```sql
-- Relationship types
SELECT create_elabel('life_graph', 'prefers');        -- Person -[:prefers]-> Technology
SELECT create_elabel('life_graph', 'uses');            -- Project -[:uses]-> Technology
SELECT create_elabel('life_graph', 'decided');         -- Person -[:decided]-> Decision
SELECT create_elabel('life_graph', 'related_to');      -- Memory -[:related_to]-> Memory
SELECT create_elabel('life_graph', 'supersedes');      -- Memory -[:supersedes]-> Memory
SELECT create_elabel('life_graph', 'knows');           -- Person -[:knows]-> Concept
SELECT create_elabel('life_graph', 'part_of');         -- Technology -[:part_of]-> Project
SELECT create_elabel('life_graph', 'based_on');        -- Decision -[:based_on]-> Memory
SELECT create_elabel('life_graph', 'conflicts_with');  -- Memory -[:conflicts_with]-> Memory
```

### 4.4 Graph Indexes

AGE stores vertices and edges in internal PostgreSQL tables. We can index them for performance:

```sql
-- Index vertex properties for fast lookup by UUID (the bridge key)
CREATE INDEX idx_memory_vertex_uuid
    ON life_graph."Memory" USING btree ((properties->>'uuid'));

CREATE INDEX idx_person_vertex_uuid
    ON life_graph."Person" USING btree ((properties->>'uuid'));

CREATE INDEX idx_project_vertex_uuid
    ON life_graph."Project" USING btree ((properties->>'uuid'));

CREATE INDEX idx_technology_vertex_uuid
    ON life_graph."Technology" USING btree ((properties->>'uuid'));

CREATE INDEX idx_decision_vertex_uuid
    ON life_graph."Decision" USING btree ((properties->>'uuid'));

CREATE INDEX idx_concept_vertex_uuid
    ON life_graph."Concept" USING btree ((properties->>'uuid'));

-- Index edge labels for traversal performance
CREATE INDEX idx_edge_prefers ON life_graph.prefers USING btree (start_id, end_id);
CREATE INDEX idx_edge_uses ON life_graph.uses USING btree (start_id, end_id);
CREATE INDEX idx_edge_decided ON life_graph.decided USING btree (start_id, end_id);
CREATE INDEX idx_edge_related_to ON life_graph.related_to USING btree (start_id, end_id);
CREATE INDEX idx_edge_supersedes ON life_graph.supersedes USING btree (start_id, end_id);
CREATE INDEX idx_edge_based_on ON life_graph.based_on USING btree (start_id, end_id);
CREATE INDEX idx_edge_conflicts_with ON life_graph.conflicts_with USING btree (start_id, end_id);
```

> [!NOTE]
> AGE internal table names follow the pattern `<graph_name>."<LabelName>"`. The quotes are required because AGE creates labels with their original casing.

---

## 5. Hybrid Query Examples

### 5.1 Semantic Search + Relational Filtering

Find the most relevant active memories for a given query, filtered by status and minimum importance:

```sql
-- $1 = query embedding (vector(768)), $2 = importance threshold, $3 = limit
SELECT
    id,
    content,
    tags,
    importance,
    1 - (embedding::halfvec(768) <=> $1::halfvec(768)) AS semantic_similarity
FROM memories
WHERE status = 'active'
  AND importance >= $2
  AND embedding IS NOT NULL
ORDER BY embedding::halfvec(768) <=> $1::halfvec(768)
LIMIT $3;
```

### 5.2 Semantic Search + Tag Filtering

```sql
-- Find Python-related preferences similar to a query
SELECT
    id,
    content,
    importance,
    1 - (embedding::halfvec(768) <=> $1::halfvec(768)) AS similarity
FROM memories
WHERE status = 'active'
  AND tags @> ARRAY['python', 'preference']
  AND embedding IS NOT NULL
ORDER BY embedding::halfvec(768) <=> $1::halfvec(768)
LIMIT 10;
```

### 5.3 Graph Traversal — Pure Cypher

Find all technologies the developer prefers, and what projects use them:

```sql
SELECT * FROM cypher('life_graph', $$
    MATCH (p:Person {uuid: 'developer-uuid'})
          -[:prefers]->(t:Technology)
          <-[:uses]-(proj:Project)
    RETURN t.name AS technology,
           collect(proj.name) AS projects,
           count(proj) AS project_count
    ORDER BY project_count DESC
$$) AS (technology agtype, projects agtype, project_count agtype);
```

Find the decision chain for a specific topic:

```sql
SELECT * FROM cypher('life_graph', $$
    MATCH path = (d1:Decision)-[:supersedes*1..5]->(d2:Decision)
    WHERE d1.topic = 'database_choice'
    RETURN d1.content AS current_decision,
           d2.content AS original_decision,
           length(path) AS evolution_steps
$$) AS (current_decision agtype, original_decision agtype, evolution_steps agtype);
```

### 5.4 Combined: Graph Narrows Scope → Vector Search

First use graph traversal to find relevant memory UUIDs, then do vector search only within that scope:

```sql
-- Step 1: Get UUIDs of memories related to current project via graph
WITH graph_scope AS (
    SELECT (properties->>'uuid')::uuid AS memory_uuid
    FROM cypher('life_graph', $$
        MATCH (proj:Project {name: 'life-graph'})
              -[:uses]->(t:Technology)
              <-[:related_to]-(m:Memory)
        RETURN m.uuid AS uuid
    $$) AS (uuid agtype)
    CROSS JOIN LATERAL (
        SELECT properties FROM life_graph."Memory"
        WHERE properties->>'uuid' = uuid::text
    ) sub
)
-- Step 2: Vector search ONLY within graph-scoped memories
SELECT
    m.id,
    m.content,
    m.tags,
    m.importance,
    1 - (m.embedding::halfvec(768) <=> $1::halfvec(768)) AS similarity
FROM memories m
JOIN graph_scope gs ON m.id = gs.memory_uuid
WHERE m.status = 'active'
  AND m.embedding IS NOT NULL
ORDER BY m.embedding::halfvec(768) <=> $1::halfvec(768)
LIMIT 10;
```

### 5.5 Context-Dependent Retrieval with Blended Scoring

```sql
-- Blended score: 0.6 * semantic_similarity + 0.4 * context_match
-- $1 = query embedding, $2 = session context JSONB
WITH candidates AS (
    SELECT
        m.id,
        m.content,
        m.tags,
        m.importance,
        m.properties,
        1 - (m.embedding::halfvec(768) <=> $1::halfvec(768)) AS semantic_sim
    FROM memories m
    WHERE m.status = 'active'
      AND m.embedding IS NOT NULL
    ORDER BY m.embedding::halfvec(768) <=> $1::halfvec(768)
    LIMIT 100  -- Pre-filter: top 100 by pure semantic similarity
),
scored AS (
    SELECT
        c.*,
        -- Context match: how many context keys overlap
        (
            SELECT count(*)::real / greatest(jsonb_object_keys_count($2), 1)
            FROM jsonb_each_text(c.properties->'context') ctx
            WHERE $2 ? ctx.key
              AND $2->>ctx.key = ctx.value
        ) AS context_score
    FROM candidates c
)
SELECT
    id,
    content,
    tags,
    importance,
    semantic_sim,
    context_score,
    (0.6 * semantic_sim + 0.4 * context_score) AS blended_score
FROM scored
ORDER BY blended_score DESC
LIMIT 10;
```

> [!NOTE]
> The context scoring above is a simplified SQL version. In practice, the full `context_similarity()` function runs in Python (see `06_proactive_recall.md`) with richer Jaccard set overlap logic. The SQL version handles the fast pre-filter; Python handles the precise ranking.

### 5.6 Proactive Recall — Session Start Check

When a new session begins, surface the most relevant memories:

```sql
-- 1. Active intentions that are due
SELECT 'intention' AS source, id, content, 'HIGH' AS priority
FROM intentions
WHERE status = 'pending'
  AND (
      (trigger_type = 'time' AND trigger_time <= now())
      OR trigger_type = 'context'
  )
ORDER BY trigger_time ASC NULLS LAST
LIMIT 5;

-- 2. Recent high-importance memories from related sessions
SELECT 'recent_memory' AS source, m.id, m.content, 'MEDIUM' AS priority
FROM memories m
JOIN memory_sessions ms ON m.id = ms.memory_id
JOIN sessions s ON ms.session_id = s.id
WHERE m.status = 'active'
  AND m.importance >= 0.7
  AND s.started_at >= now() - INTERVAL '7 days'
ORDER BY m.importance DESC, m.updated_at DESC
LIMIT 5;

-- 3. Unresolved knowledge gaps (things the system doesn't know)
SELECT 'knowledge_gap' AS source, id, topic AS content, 'LOW' AS priority
FROM knowledge_gaps
WHERE resolved = FALSE
ORDER BY query_count DESC
LIMIT 3;
```

### 5.7 Decay Score Calculation

The forgetting curve determines which memories stay active and which go dormant:

```sql
-- Decay score formula:
-- decay_score = importance * (confidence ^ 1.5)
--             * (1.0 / (1.0 + ln(1 + days_since_access)))
--             * (1.0 + 0.1 * ln(1 + access_count))

SELECT
    id,
    content,
    importance,
    confidence,
    access_count,
    updated_at,
    EXTRACT(EPOCH FROM (now() - updated_at)) / 86400.0 AS days_since_access,

    -- Full decay score
    importance
    * power(confidence, 1.5)
    * (1.0 / (1.0 + ln(1 + EXTRACT(EPOCH FROM (now() - updated_at)) / 86400.0)))
    * (1.0 + 0.1 * ln(1 + access_count))
    AS decay_score

FROM memories
WHERE status = 'active'
ORDER BY decay_score ASC    -- Lowest scores are candidates for dormancy
LIMIT 50;

-- Mark memories with decay_score below threshold as dormant
UPDATE memories
SET status = 'dormant',
    properties = properties || '{"dormant_reason": "decay", "dormant_at": "'
                 || now()::text || '"}'::jsonb
WHERE status = 'active'
  AND (
      importance
      * power(confidence, 1.5)
      * (1.0 / (1.0 + ln(1 + EXTRACT(EPOCH FROM (now() - updated_at)) / 86400.0)))
      * (1.0 + 0.1 * ln(1 + access_count))
  ) < 0.1;   -- Dormancy threshold
```

> [!TIP]
> **Decay score interpretation:**
> - `> 0.7` — Core memory, frequently accessed and important. Will never decay.
> - `0.3 - 0.7` — Active memory, healthy access pattern.
> - `0.1 - 0.3` — Fading memory, candidate for consolidation.
> - `< 0.1` — Dormant candidate. Not deleted — just moved to dormant status for possible reactivation.

---

## 6. Performance Characteristics

HNSW index tuning parameters at different memory scales:

| Scale | HNSW `m` | `ef_construction` | `ef_search` | RAM (index) | Latency (p99) |
|-------|----------|-------------------|-------------|-------------|---------------|
| 10K   | 16       | 64                | 40          | ~50MB       | <5ms          |
| 100K  | 16       | 100               | 60          | ~500MB      | <10ms         |
| 1M    | 24       | 200               | 100         | ~5GB        | <20ms         |
| 10M   | 32       | 300               | 150         | ~50GB       | <50ms         |

> [!NOTE]
> - `m` = max connections per layer. Higher = better recall, more RAM.
> - `ef_construction` = search width during index build. Higher = better index quality, slower builds.
> - `ef_search` = search width at query time. Tunable per-query via `SET hnsw.ef_search = N`.
> - RAM estimates assume halfvec(768) with 50% storage savings.

**Recommended starting configuration** (for <100K memories in Year 1):

```sql
-- Set at query time for tuning recall vs speed
SET hnsw.ef_search = 60;
```

---

## 7. halfvec Optimization

> [!IMPORTANT]
> Use halfvec from day one. The storage savings compound significantly as the memory count grows.

### How It Works

1. **Store** embeddings as `vector(768)` — full 32-bit float precision for inserts
2. **Index** using `::halfvec(768)` cast — 16-bit float, 50% smaller index
3. **Search** using `::halfvec(768)` — matches the index format

```sql
-- Insert with full precision
INSERT INTO memories (content, embedding)
VALUES ('Prefers type hints in all Python code', $1);  -- $1 is vector(768)

-- Search with halfvec cast (uses the HNSW index)
SELECT id, content,
       1 - (embedding::halfvec(768) <=> $1::halfvec(768)) AS similarity
FROM memories
WHERE status = 'active'
ORDER BY embedding::halfvec(768) <=> $1::halfvec(768)
LIMIT 10;
```

### Storage Comparison

| Memories | vector(768) Index | halfvec(768) Index | Savings |
|----------|-------------------|--------------------|---------|
| 10K      | ~100MB            | ~50MB              | 50%     |
| 100K     | ~1GB              | ~500MB             | 50%     |
| 1M       | ~10GB             | ~5GB               | 50%     |

### Recall Quality

At 10K memories with `ef_search = 40`:
- **vector(768)**: 99.2% recall@10
- **halfvec(768)**: 98.5% recall@10
- **Delta**: <1% — negligible for a personal memory system

---

## 8. Partitioning Strategy

> [!NOTE]
> Partitioning is **not needed** until 1M+ memories. For the first 1-3 years of personal use (likely <100K memories), a single table with proper indexes is more than sufficient.

### When to Partition

Partition when:
- Table exceeds 1M rows
- Query performance degrades despite proper indexes
- Backup/maintenance windows become too long

### Range Partition by Month

```sql
-- Convert to partitioned table (at migration time)
CREATE TABLE memories_partitioned (
    LIKE memories INCLUDING ALL
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE memories_y2024m01 PARTITION OF memories_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE memories_y2024m02 PARTITION OF memories_partitioned
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- ... continue for each month

-- Default partition for anything that doesn't fit
CREATE TABLE memories_default PARTITION OF memories_partitioned
    DEFAULT;
```

### Auto-Partition Creation

```sql
-- Function to auto-create next month's partition
CREATE OR REPLACE FUNCTION create_monthly_partition()
RETURNS void AS $$
DECLARE
    next_month DATE := date_trunc('month', now() + INTERVAL '1 month');
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    partition_name := 'memories_y' || to_char(next_month, 'YYYY') ||
                      'm' || to_char(next_month, 'MM');
    start_date := to_char(next_month, 'YYYY-MM-DD');
    end_date := to_char(next_month + INTERVAL '1 month', 'YYYY-MM-DD');

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF memories_partitioned
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;
```

---

## 9. Migration Path

### Phase 1 → Phase 2 Transition

```
Phase 1 (MVP)                      Phase 2 (Add Graph)
─────────────                      ───────────────────
✓ memories table                   ✓ Everything from Phase 1 (unchanged)
✓ sessions table                   ✓ CREATE EXTENSION age
✓ intentions table                 ✓ CREATE GRAPH life_graph
✓ knowledge_gaps table             ✓ Vertex labels for entities
✓ pgvector HNSW indexes            ✓ Edge labels for relationships
✓ GIN + BTREE indexes              ✓ Bridge indexes on AGE tables
✓ JSONB properties for ad-hoc      ✓ Migration script: JSONB → graph edges
  relationships
```

### Phase 1: JSONB for Ad-Hoc Relationships

Before AGE is available, store relationships in the JSONB `properties` field:

```sql
-- Store a relationship in JSONB (Phase 1)
UPDATE memories
SET properties = properties || '{
    "related_to": ["uuid-of-related-memory-1", "uuid-of-related-memory-2"],
    "supersedes_context": "Switched from Django to FastAPI",
    "project": "life-graph"
}'::jsonb
WHERE id = 'this-memory-uuid';
```

### Phase 2: Migrate JSONB Relationships to Graph

```sql
-- Migration script: create vertices for all existing memories
DO $$
DECLARE
    mem RECORD;
BEGIN
    FOR mem IN SELECT id, content, tags, created_at FROM memories WHERE status = 'active'
    LOOP
        PERFORM * FROM cypher('life_graph', format($$
            CREATE (m:Memory {
                uuid: %L,
                content: %L,
                created_at: %L
            })
        $$, mem.id, mem.content, mem.created_at)) AS (v agtype);
    END LOOP;
END $$;

-- Migration script: convert JSONB "related_to" arrays into graph edges
DO $$
DECLARE
    mem RECORD;
    related_uuid TEXT;
BEGIN
    FOR mem IN
        SELECT id, properties->'related_to' AS related
        FROM memories
        WHERE properties ? 'related_to'
    LOOP
        FOR related_uuid IN SELECT jsonb_array_elements_text(mem.related)
        LOOP
            PERFORM * FROM cypher('life_graph', format($$
                MATCH (a:Memory {uuid: %L}), (b:Memory {uuid: %L})
                CREATE (a)-[:related_to {migrated: true}]->(b)
            $$, mem.id, related_uuid)) AS (e agtype);
        END LOOP;
    END LOOP;
END $$;
```

> [!IMPORTANT]
> **Key principle:** Phase 2 adds capabilities WITHOUT breaking Phase 1 queries. Every SQL query that worked in Phase 1 continues to work identically. The graph layer is purely additive.

---

## 10. Schema Evolution Rules

### Rule 1: Never Remove Columns

```sql
-- WRONG: Dropping a column
ALTER TABLE memories DROP COLUMN old_field;

-- RIGHT: Mark deprecated in JSONB metadata, stop writing to it
UPDATE memories
SET properties = properties || '{"deprecated_fields": ["old_field"]}'::jsonb
WHERE old_field IS NOT NULL;
```

### Rule 2: JSONB Properties as Escape Hatch

When you need a new field but don't want a migration:

```sql
-- Store new data in properties immediately
UPDATE memories
SET properties = properties || '{"source_url": "https://...", "sentiment": 0.8}'::jsonb
WHERE id = $1;

-- Query it with GIN index support
SELECT * FROM memories
WHERE properties @> '{"sentiment": 0.8}';

-- Later, if the field proves permanent, promote to a real column
ALTER TABLE memories ADD COLUMN sentiment REAL;
UPDATE memories SET sentiment = (properties->>'sentiment')::real
WHERE properties ? 'sentiment';
```

### Rule 3: Embedding Model Versioning

```sql
-- Store embedding model info with each memory
INSERT INTO memories (content, embedding, properties)
VALUES (
    'Prefers PostgreSQL over MongoDB',
    $1,  -- 768-dim embedding
    '{"embedding_model": "all-mpnet-base-v2", "embedding_dim": 768}'::jsonb
);

-- When switching models: find memories that need re-embedding
SELECT id, content FROM memories
WHERE properties->>'embedding_model' != 'new-model-name'
   OR NOT (properties ? 'embedding_model')  -- Legacy memories without model info
ORDER BY importance DESC;  -- Re-embed important memories first
```

### Rule 4: Online Index Creation

```sql
-- Always use CONCURRENTLY for production index changes
CREATE INDEX CONCURRENTLY idx_memories_new_field
    ON memories ((properties->>'new_field'))
    WHERE properties ? 'new_field';
```

> [!WARNING]
> `CREATE INDEX CONCURRENTLY` cannot run inside a transaction. Run it as a standalone statement. It takes longer but does not lock the table.

### Rule 5: Backward Compatibility

Every schema change must satisfy:

1. Old code can still read/write without errors
2. New fields have sensible defaults or are nullable
3. Data migrations are idempotent (safe to run multiple times)
4. Rollback path exists (even if it means ignoring new columns)

---

## Appendix: Helper Functions

### A.1 jsonb_object_keys_count

Used in the blended scoring query:

```sql
CREATE OR REPLACE FUNCTION jsonb_object_keys_count(j JSONB)
RETURNS INTEGER AS $$
    SELECT count(*)::integer FROM jsonb_object_keys(j);
$$ LANGUAGE sql IMMUTABLE;
```

### A.2 Increment Access Count

Called every time a memory is retrieved and shown to the user:

```sql
CREATE OR REPLACE FUNCTION touch_memory(memory_uuid UUID)
RETURNS void AS $$
    UPDATE memories
    SET access_count = access_count + 1,
        updated_at = now()
    WHERE id = memory_uuid;
$$ LANGUAGE sql;
```

### A.3 Supersede a Memory

Replace one memory with another while maintaining the chain:

```sql
CREATE OR REPLACE FUNCTION supersede_memory(
    old_id UUID,
    new_content TEXT,
    new_tags TEXT[],
    new_embedding vector(768)
)
RETURNS UUID AS $$
DECLARE
    new_id UUID;
BEGIN
    -- Create the new memory
    INSERT INTO memories (content, tags, embedding, supersedes)
    VALUES (new_content, new_tags, new_embedding, old_id)
    RETURNING id INTO new_id;

    -- Update the old memory
    UPDATE memories
    SET status = 'superseded',
        superseded_by = new_id
    WHERE id = old_id;

    RETURN new_id;
END;
$$ LANGUAGE plpgsql;
```
