# 06 — Proactive Recall Engine

## The Memory System That Surfaces Knowledge Before You Search

> [!IMPORTANT]
> Traditional memory systems wait for you to search. Life Graph's proactive recall **pushes** relevant memories to you — like a recommendation engine (Netflix/Spotify) applied to personal knowledge. The best memory system is one where you never need to search.

---

## 1. Overview

### Push vs Pull

| Aspect | Traditional (Pull) | Life Graph (Push) |
|--------|-------------------|-------------------|
| Trigger | User types a query | System detects context change |
| Latency | User must remember to ask | Zero — happens automatically |
| Coverage | Only what you think to search for | Surfaces things you forgot you knew |
| Mental load | You are the context loader | System loads context for you |
| Analogies | Google Search | Netflix recommendations, Spotify Discover |

### Key Design Principles

1. **Recommendation engine patterns** — retrieve → rank → rerank funnel
2. **Anti-annoyance first** — one dismissed memory costs more trust than ten surfaced ones
3. **Cheapest signal first** — SQL filters before embeddings, embeddings before LLM
4. **Context is king** — same memory is relevant in one context, noise in another
5. **Brain-inspired** — mirrors how human memory surfaces associations contextually

---

## 2. Three-Stage Funnel

Adapted from Netflix/Spotify recommendation architecture:

```
┌──────────────────────────────────────────────────────────┐
│                    ALL MEMORIES                           │
│                    (~10K-1M+)                             │
└──────────────────────┬───────────────────────────────────┘
                       │
              Stage 1: RETRIEVE
              SQL WHERE + pgvector ANN
              <50ms, ~100 candidates
                       │
              ┌────────▼────────┐
              │  ~100 candidates │
              └────────┬────────┘
                       │
              Stage 2: RANK
              Multi-signal scoring
              Python, ~10ms
                       │
              ┌────────▼────────┐
              │  ~10 ranked      │
              └────────┬────────┘
                       │
              Stage 3: RERANK
              Diversity + cooldown
              Python, ~5ms
                       │
              ┌────────▼────────┐
              │  3-5 final       │
              └──────────────────┘
```

### Stage 1 — Retrieve (Fast Candidate Generation)

- **Method**: SQL `WHERE` clauses + pgvector approximate nearest neighbor
- **Target**: <50ms latency, ~100 candidates
- **Why**: This is the cheap filter. Eliminates 99%+ of memories using indexes only.
- **Filters**: `status = 'active'`, `importance > 0.3`, optional tag matching, optional vector similarity

### Stage 2 — Rank (Multi-Signal Scoring)

- **Method**: Python-side scoring with 6 weighted signals
- **Target**: ~10ms, narrows ~100 → ~10
- **Signals**: semantic similarity, context match, importance, recency, frequency, trust
- **Why**: Pure vector similarity isn't enough. A memory from a different project with high cosine similarity is less useful than a medium-similarity memory from the current project.

### Stage 3 — Rerank (Quality Enforcement)

- **Method**: Diversity enforcement, deduplication, cooldown checks
- **Target**: ~5ms, narrows ~10 → 3-5 final results
- **Rules**: No two memories about the same topic, 7-day cooldown per memory, max items per session
- **Why**: Prevents the system from showing 5 variations of the same preference.

---

## 3. Trigger Map

| Trigger | Detection Method | What to Surface | Priority |
|---------|-----------------|-----------------|----------|
| **File opened** | `onDidOpenTextDocument` / inotify | Related decisions, past patterns for that module | MEDIUM |
| **Project started** | cwd detection + `.git/config` parse | Project preferences, architecture decisions, open intentions | HIGH |
| **Similar code pattern** | Embed current code context, ANN search | Past approaches, gotchas, style preferences | MEDIUM |
| **Time-based intention** | Cron job: `WHERE trigger_time <= now()` | Due intentions, scheduled reviews | HIGH |
| **Error matches past bug** | Hook into stderr/error output, embed error, search | Past solutions, workarounds, related decisions | CRITICAL |
| **Branch/git change** | Watch `.git/HEAD` file for changes | Branch-specific context, related feature decisions | LOW |
| **Repeated question** | Track query similarity, increment `knowledge_gaps.query_count` | Knowledge gap notification, related partial answers | MEDIUM |
| **Stale fact detected** | Background scan: `WHERE valid_until < now()` | Prompt for review/confirmation/retirement | LOW |

> [!NOTE]
> **Priority levels determine the delivery tier:**
> - CRITICAL → TIER 1 PUSH (interrupts)
> - HIGH → TIER 1 or TIER 2 (depending on urgency)
> - MEDIUM → TIER 2 AMBIENT-PROMINENT (sidebar)
> - LOW → TIER 3 AMBIENT-PASSIVE (collapsed)

---

## 4. Context Fingerprint Matching

The cheapest first-pass relevance filter — pure Python set operations, no embeddings needed.

```python
"""Context fingerprint matching for proactive recall."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def context_similarity(current: dict[str, Any], stored: dict[str, Any]) -> float:
    """
    Compute structured context similarity between current session
    and a stored memory's context.

    Uses set overlap on structured fields — no embeddings, no LLM.
    This is the cheapest possible relevance signal.

    Args:
        current: Current session context, e.g.:
            {
                "project": "life-graph",
                "modules": ["memory", "recall", "api"],
                "tools": ["fastapi", "postgresql", "pytest"],
                "current_file": "src/recall/engine.py"
            }
        stored: Memory's stored context (from properties or context_match), e.g.:
            {
                "project": "life-graph",
                "modules": ["memory", "storage"],
                "tools": ["fastapi", "postgresql"],
                "current_file": "src/memory/store.py"
            }

    Returns:
        Float between 0.0 and 1.0 representing context similarity.
    """
    # --- Project match (exact) ---
    project_match = 1.0 if (
        current.get("project") and
        current.get("project") == stored.get("project")
    ) else 0.0

    # --- Module overlap (Jaccard) ---
    current_modules = set(current.get("modules", []))
    stored_modules = set(stored.get("modules", []))
    module_overlap = _jaccard_similarity(current_modules, stored_modules)

    # --- Tool overlap (Jaccard) ---
    current_tools = set(current.get("tools", []))
    stored_tools = set(stored.get("tools", []))
    tool_overlap = _jaccard_similarity(current_tools, stored_tools)

    # --- File proximity ---
    current_file = current.get("current_file", "")
    stored_file = stored.get("current_file", "")

    if current_file and stored_file:
        if current_file == stored_file:
            file_proximity = 1.0
        elif (PurePosixPath(current_file).parent ==
              PurePosixPath(stored_file).parent):
            file_proximity = 0.5
        else:
            file_proximity = 0.0
    else:
        file_proximity = 0.0

    # --- Weighted average ---
    score = (
        0.4 * project_match +
        0.3 * module_overlap +
        0.2 * tool_overlap +
        0.1 * file_proximity
    )

    return round(score, 4)
```

> [!TIP]
> Context similarity is computed **in Python, not SQL**. It runs on the ~100 candidates returned by Stage 1, so the input size is always small. This avoids the complexity of encoding set operations into SQL while keeping latency trivial (~1ms for 100 candidates).

---

## 5. Anti-Annoyance Rules

> [!WARNING]
> **The #1 failure mode for proactive recall is annoying the user.** One bad suggestion costs more trust than ten good ones earn. Every rule below exists because without it, users disable the system within a week.

### 5.1 Confidence Threshold

Only surface memories where `final_score > 0.7`. Below this threshold, the relevance is too uncertain to justify interrupting the developer's flow.

### 5.2 Rate Limits

| Context | Max Surfaces | Cooldown |
|---------|-------------|----------|
| Session start | 3-5 memories | Once per session |
| Active work | 1-2 memories | 30+ minutes between surfaces |
| Error detected | 1 memory | Per error occurrence |

### 5.3 Memory Cooldown

- **7-day minimum** between re-surfacing the same memory
- Tracked per memory ID in the `memory_sessions` junction table
- Exceptions: error matches and due intentions bypass cooldown

### 5.4 Behavioral Triggers

- **DO** fire during: file save, terminal idle >10s, task completion, session start
- **DON'T** fire during: active typing, mid-command execution, test runs, builds

### 5.5 Dismissal Tracking

```python
# Track dismissals per memory per context
# After 3 dismissals, auto-suppress for this context
DISMISSAL_THRESHOLD = 3

async def handle_dismissal(memory_id: str, context: dict) -> None:
    """Track user dismissal and auto-suppress if threshold reached."""
    context_key = f"{context.get('project', 'global')}:{context.get('module', 'any')}"

    # Increment dismissal count in memory properties
    await db.execute("""
        UPDATE memories
        SET properties = jsonb_set(
            properties,
            '{dismissals}',
            COALESCE(properties->'dismissals', '{}') || 
            jsonb_build_object($1, 
                COALESCE((properties->'dismissals'->>$1)::int, 0) + 1
            )
        )
        WHERE id = $2
    """, context_key, memory_id)

    # Check if threshold reached
    dismissal_count = await db.fetchval("""
        SELECT COALESCE((properties->'dismissals'->>$1)::int, 0)
        FROM memories WHERE id = $2
    """, context_key, memory_id)

    if dismissal_count >= DISMISSAL_THRESHOLD:
        # Auto-suppress for this context
        await db.execute("""
            UPDATE memories
            SET properties = jsonb_set(
                properties,
                '{suppressed_contexts}',
                COALESCE(properties->'suppressed_contexts', '[]') || 
                to_jsonb($1::text)
            )
            WHERE id = $2
        """, context_key, memory_id)
```

### 5.6 User Control — Intensity Slider

```python
# Intensity levels (stored as user preference memory)
INTENSITY_SETTINGS = {
    "aggressive": {
        "score_threshold": 0.5,
        "max_session_start": 7,
        "max_active_work": 3,
        "cooldown_days": 3,
    },
    "balanced": {  # DEFAULT
        "score_threshold": 0.7,
        "max_session_start": 5,
        "max_active_work": 2,
        "cooldown_days": 7,
    },
    "minimal": {
        "score_threshold": 0.85,
        "max_session_start": 3,
        "max_active_work": 1,
        "cooldown_days": 14,
    },
    "off": {
        "score_threshold": 999.0,  # Nothing passes
        "max_session_start": 0,
        "max_active_work": 0,
        "cooldown_days": 999,
    },
}
```

### 5.7 Positive Framing

Frame suggestions as helpful discoveries, never interruptions:

| ❌ Bad Framing | ✅ Good Framing |
|---------------|----------------|
| "Warning: You previously decided..." | "💡 Related decision: You chose FastAPI because..." |
| "Error: This contradicts..." | "🔍 Worth noting: Your earlier take on this was..." |
| "Reminder: Don't forget..." | "📌 From last month: You wanted to revisit..." |

> [!TIP]
> **The Duolingo Lesson:** Duolingo succeeds because every notification feels like encouragement, not nagging. Life Graph's recall should feel the same — "Here's something useful" not "Here's something you forgot."

---

## 6. Ambient vs Push Tiering

### TIER 1 — PUSH (Notification / Toast)

**Interrupts the developer. Used sparingly for time-critical information.**

- ⏰ Intentions that are due (`trigger_time <= now()`)
- ⚠️ Contradictions detected (new memory conflicts with existing belief)
- 🐛 Error matches past bugs (current error resembles a previously-solved issue)

### TIER 2 — AMBIENT-PROMINENT (Sidebar Panel, Highlighted)

**Visible but non-intrusive. The developer sees it in peripheral vision.**

- 📋 Related decisions for current context
- 🔄 Past patterns for current code module
- ❓ Knowledge gaps relevant to current work
- 🧭 Architecture decisions for current project

### TIER 3 — AMBIENT-PASSIVE (Collapsed / Dimmed Section)

**Available on hover/expand. Zero distraction until intentionally opened.**

- 💭 Tangentially related memories
- 📅 Stale facts needing review
- 💡 General tips and patterns from other projects
- 📊 Consolidation reports from last night's sleep cycle

---

## 7. Multi-Signal Ranking Formula

```python
"""Multi-signal ranking for proactive recall."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np


def calculate_recall_score(
    memory: dict[str, Any],
    context: dict[str, Any],
    query_embedding: np.ndarray | None = None,
) -> float:
    """
    Calculate the proactive recall score for a memory candidate.

    Combines 6 signals with tuned weights to produce a final
    relevance score between 0.0 and 1.0.

    Args:
        memory: Memory dict with keys:
            - embedding: np.ndarray (768,)
            - importance: float (0-1)
            - confidence: float (0-1)
            - access_count: int
            - updated_at: datetime
            - properties: dict (contains context info)
        context: Current session context dict
        query_embedding: Optional query embedding for semantic similarity

    Returns:
        Float between 0.0 and 1.0 representing recall relevance.

    Signal weights:
        semantic_similarity: 0.25
        context_match:       0.25
        importance:          0.20
        recency:             0.15
        frequency:           0.10
        trust:               0.05
    """
    # --- Signal 1: Semantic Similarity (weight: 0.25) ---
    if query_embedding is not None and memory.get("embedding") is not None:
        mem_emb = np.asarray(memory["embedding"])
        query_emb = np.asarray(query_embedding)
        # Cosine similarity
        dot_product = np.dot(mem_emb, query_emb)
        norm_product = np.linalg.norm(mem_emb) * np.linalg.norm(query_emb)
        semantic_sim = float(dot_product / norm_product) if norm_product > 0 else 0.0
        # Clamp to [0, 1]
        semantic_sim = max(0.0, min(1.0, semantic_sim))
    else:
        semantic_sim = 0.0

    # --- Signal 2: Context Match (weight: 0.25) ---
    stored_context = memory.get("properties", {}).get("context", {})
    context_score = context_similarity(context, stored_context)

    # --- Signal 3: Importance (weight: 0.20) ---
    importance = float(memory.get("importance", 0.5))

    # --- Signal 4: Recency (weight: 0.15) ---
    updated_at = memory.get("updated_at")
    if isinstance(updated_at, datetime):
        now = datetime.now(timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        days_since = max(0, (now - updated_at).total_seconds() / 86400.0)
    else:
        days_since = 365.0  # Default to old if no timestamp

    recency = 1.0 / (1.0 + math.log(1 + days_since))

    # --- Signal 5: Frequency (weight: 0.10) ---
    access_count = int(memory.get("access_count", 0))
    frequency = min(access_count / 10.0, 1.0)  # Normalized, cap at 1.0

    # --- Signal 6: Trust (weight: 0.05) ---
    trust = float(memory.get("confidence", 1.0))

    # --- Weighted Sum ---
    WEIGHTS = {
        "semantic": 0.25,
        "context": 0.25,
        "importance": 0.20,
        "recency": 0.15,
        "frequency": 0.10,
        "trust": 0.05,
    }

    final_score = (
        WEIGHTS["semantic"] * semantic_sim +
        WEIGHTS["context"] * context_score +
        WEIGHTS["importance"] * importance +
        WEIGHTS["recency"] * recency +
        WEIGHTS["frequency"] * frequency +
        WEIGHTS["trust"] * trust
    )

    return round(final_score, 4)
```

---

## 8. Three-Stage Retrieval Pipeline

### Stage 1 — Retrieve (SQL)

```sql
-- Fast candidate generation: SQL WHERE + optional vector search
-- Returns ~100 candidates in <50ms

-- $1 = optional query embedding (NULL if context-only trigger)
-- $2 = current project name
-- $3 = importance threshold (default 0.3)
-- $4 = limit (default 100)

SELECT
    m.id,
    m.content,
    m.tags,
    m.importance,
    m.confidence,
    m.access_count,
    m.updated_at,
    m.embedding,
    m.properties,
    CASE
        WHEN $1::vector IS NOT NULL AND m.embedding IS NOT NULL
        THEN 1 - (m.embedding::halfvec(768) <=> $1::halfvec(768))
        ELSE 0.0
    END AS semantic_sim
FROM memories m
WHERE m.status = 'active'
  AND m.importance >= $3
  -- Exclude suppressed memories for this context
  AND NOT (m.properties->'suppressed_contexts' ? $2)
  -- Exclude recently surfaced (7-day cooldown)
  AND NOT EXISTS (
      SELECT 1 FROM memory_sessions ms
      JOIN sessions s ON ms.session_id = s.id
      WHERE ms.memory_id = m.id
        AND s.started_at > now() - INTERVAL '7 days'
  )
ORDER BY
    CASE
        WHEN $1::vector IS NOT NULL AND m.embedding IS NOT NULL
        THEN m.embedding::halfvec(768) <=> $1::halfvec(768)
        ELSE 1 - m.importance  -- Fall back to importance ordering
    END
LIMIT $4;
```

### Stage 2 — Rank (Python)

```python
"""Stage 2: Apply multi-signal ranking to candidates."""

from typing import Any

import numpy as np


async def rank_candidates(
    candidates: list[dict[str, Any]],
    context: dict[str, Any],
    query_embedding: np.ndarray | None = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Apply multi-signal scoring to candidate memories.

    Takes ~100 candidates from Stage 1 and returns top ~10 by
    weighted recall score.

    Args:
        candidates: List of memory dicts from Stage 1 SQL query.
        context: Current session context.
        query_embedding: Optional query embedding.
        top_k: Number of top candidates to return.

    Returns:
        Top-k candidates sorted by recall score, with score attached.
    """
    scored: list[tuple[float, dict[str, Any]]] = []

    for candidate in candidates:
        score = calculate_recall_score(
            memory=candidate,
            context=context,
            query_embedding=query_embedding,
        )
        candidate["recall_score"] = score
        scored.append((score, candidate))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    return [candidate for _, candidate in scored[:top_k]]
```

### Stage 3 — Rerank (Diversity + Cooldown)

```python
"""Stage 3: Diversity enforcement, deduplication, and final filtering."""

from __future__ import annotations

from typing import Any


def diversity_rerank(
    ranked_candidates: list[dict[str, Any]],
    session_surfaced: set[str],
    max_items: int = 5,
    tag_similarity_threshold: float = 0.6,
) -> list[dict[str, Any]]:
    """
    Apply diversity enforcement and cooldown to ranked candidates.

    Rules:
    1. No two memories about the same topic (detected by tag overlap).
    2. Skip memories already surfaced in this session.
    3. Cap at max_items.

    Args:
        ranked_candidates: Pre-ranked candidates from Stage 2 (sorted by score).
        session_surfaced: Set of memory IDs already surfaced in this session.
        max_items: Maximum number of memories to return.
        tag_similarity_threshold: Jaccard threshold for considering two
            memories as "same topic".

    Returns:
        Final list of memories to surface, respecting diversity constraints.
    """
    final: list[dict[str, Any]] = []
    seen_tag_sets: list[set[str]] = []

    for candidate in ranked_candidates:
        if len(final) >= max_items:
            break

        memory_id = str(candidate.get("id", ""))

        # Skip if already surfaced in this session
        if memory_id in session_surfaced:
            continue

        # Check topic diversity (tag overlap)
        candidate_tags = set(candidate.get("tags", []))
        is_duplicate_topic = False

        for seen_tags in seen_tag_sets:
            if _jaccard_similarity(candidate_tags, seen_tags) > tag_similarity_threshold:
                is_duplicate_topic = True
                break

        if is_duplicate_topic:
            continue

        # Accept this candidate
        final.append(candidate)
        seen_tag_sets.append(candidate_tags)

    return final


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0
```

---

## 9. CrewAI Agent Integration

### LifeGraphBridge

The bridge between Life Graph's memory and CrewAI's agent system. Every agent gets personal context before executing a task.

```python
"""Bridge between Life Graph memory and CrewAI agents."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import numpy as np


class LifeGraphBridge:
    """
    Connects Life Graph memory to CrewAI agent execution.

    Provides two main capabilities:
    1. build_agent_context() — enriches agent prompts with personal memory
    2. learn_from_task() — extracts new memories from completed tasks
    """

    def __init__(self, db_pool, embedding_model) -> None:
        """
        Args:
            db_pool: asyncpg connection pool to PostgreSQL.
            embedding_model: SentenceTransformer model for embedding generation.
        """
        self.db = db_pool
        self.model = embedding_model

    async def build_agent_context(self, task_description: str) -> str:
        """
        Build a rich context string for a CrewAI agent based on Life Graph memory.

        Queries relevant memories and structures them into sections:
        IDENTITY, DECISIONS, EXPERIENCE, INTENTIONS, WARNINGS.

        Args:
            task_description: The task the agent is about to execute.

        Returns:
            Formatted context string to prepend to the agent's system prompt.
        """
        # Embed the task description for semantic search
        task_embedding = self.model.encode(task_description)

        # --- IDENTITY: Who the developer is ---
        identity_memories = await self.db.fetch("""
            SELECT content FROM memories
            WHERE status = 'active'
              AND tags @> ARRAY['identity']
            ORDER BY importance DESC
            LIMIT 5
        """)

        # --- DECISIONS: Relevant past decisions ---
        decision_memories = await self.db.fetch("""
            SELECT content, importance, reasoning FROM memories
            WHERE status = 'active'
              AND tags @> ARRAY['decision']
              AND embedding IS NOT NULL
            ORDER BY embedding::halfvec(768) <=> $1::halfvec(768)
            LIMIT 5
        """, task_embedding)

        # --- EXPERIENCE: Related past experiences ---
        experience_memories = await self.db.fetch("""
            SELECT content, tags FROM memories
            WHERE status = 'active'
              AND (tags @> ARRAY['lesson'] OR tags @> ARRAY['experience'])
              AND embedding IS NOT NULL
            ORDER BY embedding::halfvec(768) <=> $1::halfvec(768)
            LIMIT 5
        """, task_embedding)

        # --- INTENTIONS: Active intentions for this work ---
        active_intentions = await self.db.fetch("""
            SELECT content, trigger_condition FROM intentions
            WHERE status = 'pending'
              AND embedding IS NOT NULL
            ORDER BY embedding::halfvec(768) <=> $1::halfvec(768)
            LIMIT 3
        """, task_embedding)

        # --- WARNINGS: Contradictions, gotchas, past mistakes ---
        warnings = await self.db.fetch("""
            SELECT content, reasoning FROM memories
            WHERE status = 'active'
              AND (
                  tags @> ARRAY['gotcha']
                  OR tags @> ARRAY['mistake']
                  OR tags @> ARRAY['warning']
                  OR tags @> ARRAY['contradiction']
              )
              AND embedding IS NOT NULL
            ORDER BY embedding::halfvec(768) <=> $1::halfvec(768)
            LIMIT 3
        """, task_embedding)

        # --- Build formatted context ---
        sections: list[str] = []

        if identity_memories:
            items = "\n".join(f"  - {r['content']}" for r in identity_memories)
            sections.append(f"## IDENTITY\n{items}")

        if decision_memories:
            items = "\n".join(
                f"  - {r['content']}"
                + (f" (reason: {r['reasoning']})" if r.get("reasoning") else "")
                for r in decision_memories
            )
            sections.append(f"## RELEVANT DECISIONS\n{items}")

        if experience_memories:
            items = "\n".join(f"  - {r['content']}" for r in experience_memories)
            sections.append(f"## PAST EXPERIENCE\n{items}")

        if active_intentions:
            items = "\n".join(
                f"  - {r['content']}"
                + (f" (trigger: {r['trigger_condition']})"
                   if r.get("trigger_condition") else "")
                for r in active_intentions
            )
            sections.append(f"## ACTIVE INTENTIONS\n{items}")

        if warnings:
            items = "\n".join(
                f"  - ⚠️ {r['content']}"
                + (f" ({r['reasoning']})" if r.get("reasoning") else "")
                for r in warnings
            )
            sections.append(f"## WARNINGS\n{items}")

        if not sections:
            return ""

        header = "# Developer Context (from Life Graph memory)\n"
        return header + "\n\n".join(sections)

    async def learn_from_task(self, task_result: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract new memories from a completed task.

        Analyzes the task result to identify:
        - Decisions made during execution
        - New preferences discovered
        - Errors encountered and their solutions
        - Tools/patterns used successfully

        Args:
            task_result: Dict with keys:
                - task_description: str
                - output: str (task output/result)
                - tools_used: list[str]
                - errors: list[dict] (optional, errors encountered)
                - duration_seconds: float

        Returns:
            List of new memory dicts ready for storage.
        """
        memories: list[dict[str, Any]] = []
        output = task_result.get("output", "")
        task_desc = task_result.get("task_description", "")

        # --- Extract decisions ---
        decision_patterns = [
            r"(?:decided|chose|selected|went with|using)\s+(.+?)(?:\.|$)",
            r"(?:better to|should|will)\s+(.+?)(?:\.|$)",
        ]
        for pattern in decision_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            for match in matches[:3]:  # Cap at 3 decisions per task
                content = match.strip()
                if len(content) > 10:  # Skip trivially short matches
                    memories.append({
                        "content": f"Decision during task: {content}",
                        "tags": ["decision", "task-learned", "auto-extracted"],
                        "importance": 0.6,
                        "confidence": 0.7,
                        "properties": {
                            "source": "task_extraction",
                            "task": task_desc[:200],
                        },
                    })

        # --- Extract error solutions ---
        errors = task_result.get("errors", [])
        for error in errors[:5]:
            error_msg = error.get("message", "")
            solution = error.get("solution", "")
            if error_msg and solution:
                memories.append({
                    "content": f"Error: {error_msg[:200]} → Solution: {solution[:200]}",
                    "tags": ["error-solution", "task-learned", "debugging"],
                    "importance": 0.8,
                    "confidence": 0.9,
                    "properties": {
                        "source": "task_extraction",
                        "error_type": error.get("type", "unknown"),
                        "task": task_desc[:200],
                    },
                })

        # --- Extract tool usage ---
        tools_used = task_result.get("tools_used", [])
        if tools_used:
            memories.append({
                "content": f"Successfully used tools: {', '.join(tools_used)}",
                "tags": ["tool-usage", "task-learned"] + tools_used[:5],
                "importance": 0.4,
                "confidence": 0.9,
                "properties": {
                    "source": "task_extraction",
                    "task": task_desc[:200],
                },
            })

        # --- Generate embeddings for new memories ---
        for memory in memories:
            memory["embedding"] = self.model.encode(memory["content"]).tolist()

        return memories
```

---

## 10. Consolidation Pipeline (Nightly Sleep Cycle)

> [!IMPORTANT]
> The consolidation pipeline runs once daily (typically at night). It mirrors the brain's memory consolidation during sleep — strengthening important memories, merging duplicates, and letting unimportant ones fade. **Only step 5 (Distill) uses an LLM call.** Everything else is rule-based.

```
┌─────────────────────────────────────────────────────────┐
│              Nightly Consolidation Pipeline               │
│                                                          │
│  1. Gather ──► 2. Cluster ──► 3. Dedup ──► 4. Score     │
│       │              │             │            │        │
│       ▼              ▼             ▼            ▼        │
│  5. Distill ──► 6. Integrate ──► 7. Decay ──► 8. Audit  │
│  (LLM: 1x/day)                                          │
│       │                                                  │
│       ▼                                                  │
│  9. Report                                               │
└─────────────────────────────────────────────────────────┘
```

### Step-by-Step

| Step | Name | Method | LLM? | Description |
|------|------|--------|------|-------------|
| 1 | **Gather** | SQL query | ❌ | Collect all memories created/accessed in last 24h |
| 2 | **Cluster** | DBSCAN (eps=0.3) | ❌ | Group by embedding similarity into topical clusters |
| 3 | **Deduplicate** | Cosine sim > 0.95 | ❌ | Merge near-identical memories, keep highest importance |
| 4 | **Score** | Rule-based | ❌ | Recalculate importance based on access patterns, feedback, graph connections |
| 5 | **Distill** | LLM (gpt-4o-mini) | ✅ | Summarize clusters into consolidated memories. **Only LLM step.** |
| 6 | **Integrate** | Cypher queries | ❌ | Update graph connections, add edges between related memories |
| 7 | **Decay** | Decay formula | ❌ | Apply forgetting curve, mark low-score memories as 'dormant' |
| 8 | **Audit** | SQL + rules | ❌ | Check for contradictions, stale facts, orphaned memories |
| 9 | **Report** | Aggregation | ❌ | Generate summary: added, merged, decayed, contradictions found |

```python
"""Nightly consolidation pipeline — the brain's sleep cycle."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN


async def run_consolidation(db_pool, embedding_model, llm_client=None) -> dict[str, Any]:
    """
    Execute the full 9-step nightly consolidation pipeline.

    Args:
        db_pool: asyncpg connection pool.
        embedding_model: SentenceTransformer for embedding operations.
        llm_client: Optional LiteLLM client for step 5 (distillation).
                    If None, step 5 is skipped.

    Returns:
        Consolidation report dict.
    """
    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "memories_gathered": 0,
        "clusters_found": 0,
        "duplicates_merged": 0,
        "memories_distilled": 0,
        "edges_created": 0,
        "memories_decayed": 0,
        "contradictions_found": 0,
        "stale_facts": 0,
    }

    # --- Step 1: Gather ---
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_memories = await db_pool.fetch("""
        SELECT id, content, tags, importance, confidence,
               access_count, updated_at, embedding, properties
        FROM memories
        WHERE status = 'active'
          AND (created_at >= $1 OR updated_at >= $1)
          AND embedding IS NOT NULL
    """, cutoff)
    report["memories_gathered"] = len(recent_memories)

    if len(recent_memories) < 2:
        report["skipped"] = "Too few memories to consolidate"
        return report

    # --- Step 2: Cluster ---
    embeddings = np.array([r["embedding"] for r in recent_memories])
    # Normalize for cosine distance
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = embeddings / norms

    clustering = DBSCAN(eps=0.3, min_samples=2, metric="cosine").fit(normalized)
    labels = clustering.labels_

    clusters: dict[int, list[dict]] = defaultdict(list)
    for i, label in enumerate(labels):
        if label != -1:  # Skip noise points
            clusters[label].append(dict(recent_memories[i]))
    report["clusters_found"] = len(clusters)

    # --- Step 3: Deduplicate ---
    duplicates_merged = 0
    for cluster_id, cluster_memories in clusters.items():
        if len(cluster_memories) < 2:
            continue
        for i in range(len(cluster_memories)):
            for j in range(i + 1, len(cluster_memories)):
                emb_i = np.asarray(cluster_memories[i]["embedding"])
                emb_j = np.asarray(cluster_memories[j]["embedding"])
                sim = float(np.dot(emb_i, emb_j) / (
                    np.linalg.norm(emb_i) * np.linalg.norm(emb_j) + 1e-8
                ))
                if sim > 0.95:
                    # Keep the one with higher importance
                    keep = i if cluster_memories[i]["importance"] >= cluster_memories[j]["importance"] else j
                    discard = j if keep == i else i
                    await db_pool.execute("""
                        UPDATE memories SET status = 'superseded',
                            superseded_by = $1
                        WHERE id = $2
                    """, cluster_memories[keep]["id"], cluster_memories[discard]["id"])
                    duplicates_merged += 1
    report["duplicates_merged"] = duplicates_merged

    # --- Step 4: Score ---
    await db_pool.execute("""
        UPDATE memories
        SET importance = LEAST(1.0, importance + 0.05)
        WHERE status = 'active'
          AND access_count > 5
          AND updated_at >= $1
    """, cutoff)

    # --- Step 5: Distill (ONLY LLM STEP) ---
    if llm_client and clusters:
        for cluster_id, cluster_memories in clusters.items():
            if len(cluster_memories) < 3:
                continue
            contents = [m["content"] for m in cluster_memories[:10]]
            prompt = (
                "Summarize these related memories into a single consolidated memory. "
                "Keep the key decisions, preferences, and lessons. Be concise.\n\n"
                + "\n".join(f"- {c}" for c in contents)
            )
            try:
                response = await llm_client.acompletion(
                    model="gpt-4o-mini",  # Cheap model for distillation
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                )
                summary = response.choices[0].message.content.strip()
                if summary:
                    embedding = embedding_model.encode(summary)
                    await db_pool.execute("""
                        INSERT INTO memories (content, tags, importance, embedding, properties)
                        VALUES ($1, $2, $3, $4, $5)
                    """,
                        summary,
                        ["consolidated", "distilled"],
                        max(m["importance"] for m in cluster_memories),
                        embedding.tolist(),
                        {"source": "consolidation:distill",
                         "source_count": len(cluster_memories)},
                    )
                    report["memories_distilled"] += 1
            except Exception:
                pass  # Distillation is best-effort

    # --- Step 6: Integrate ---
    # (Graph edge creation — only meaningful in Phase 2 with AGE)
    # Placeholder: track co-occurring tags for future edge creation
    report["edges_created"] = 0

    # --- Step 7: Decay ---
    decayed = await db_pool.execute("""
        UPDATE memories
        SET status = 'dormant',
            properties = properties || jsonb_build_object(
                'dormant_reason', 'decay',
                'dormant_at', now()::text
            )
        WHERE status = 'active'
          AND (
              importance
              * power(confidence, 1.5)
              * (1.0 / (1.0 + ln(1 + EXTRACT(EPOCH FROM (now() - updated_at)) / 86400.0)))
              * (1.0 + 0.1 * ln(1 + access_count))
          ) < 0.1
    """)
    report["memories_decayed"] = int(decayed.split()[-1]) if isinstance(decayed, str) else 0

    # --- Step 8: Audit ---
    # Find potential contradictions (high similarity but different conclusions)
    stale = await db_pool.fetchval("""
        SELECT count(*) FROM memories
        WHERE status = 'active'
          AND valid_until IS NOT NULL
          AND valid_until < now()
    """)
    report["stale_facts"] = stale or 0

    # --- Step 9: Report ---
    report["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Store the report as a memory itself
    await db_pool.execute("""
        INSERT INTO memories (content, tags, importance, properties)
        VALUES ($1, $2, $3, $4)
    """,
        f"Consolidation report: {report['memories_gathered']} gathered, "
        f"{report['duplicates_merged']} merged, "
        f"{report['memories_decayed']} decayed",
        ["system", "consolidation-report"],
        0.3,
        report,
    )

    return report
```

> [!NOTE]
> **Cost of Step 5 (Distill):** With gpt-4o-mini at ~$0.15/1M input tokens, processing ~50 daily memories costs roughly **$0.001-0.01/day** (well under $1/month). This is the ONLY LLM cost in the entire system.

---

## 11. Identity Evolution

### The Timeline Concept

Identity isn't static — it evolves through **chapters**. Each chapter represents a period where the developer held a particular set of beliefs and preferences.

```python
"""Identity evolution — tracking how the developer changes over time."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# Belief states (stored as TEXT, not enum — matches Life Graph design principles)
# 'current'     — actively held belief
# 'superseded'  — replaced by a newer belief (linked to successor)
# 'uncertain'   — flagged for review
# 'exploring'   — tentative, being tested
# 'contextual'  — true in some contexts, not others
# 'retired'     — no longer relevant

VALID_BELIEF_STATES = {
    "current", "superseded", "uncertain",
    "exploring", "contextual", "retired",
}


@dataclass
class Belief:
    """A single belief or preference in the identity timeline."""
    id: str
    content: str
    state: str  # One of VALID_BELIEF_STATES
    established_at: datetime
    superseded_at: datetime | None = None
    successor_id: str | None = None
    context: str | None = None  # For 'contextual' beliefs
    tags: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)  # Memory IDs supporting this belief

    def to_memory_dict(self) -> dict[str, Any]:
        """Convert to a Life Graph memory dict for storage."""
        return {
            "content": self.content,
            "tags": ["identity", "belief", f"belief-{self.state}"] + self.tags,
            "importance": 0.9 if self.state == "current" else 0.5,
            "confidence": {
                "current": 1.0,
                "superseded": 0.3,
                "uncertain": 0.5,
                "exploring": 0.6,
                "contextual": 0.8,
                "retired": 0.1,
            }.get(self.state, 0.5),
            "properties": {
                "belief_state": self.state,
                "established_at": self.established_at.isoformat(),
                "superseded_at": self.superseded_at.isoformat() if self.superseded_at else None,
                "successor_id": self.successor_id,
                "context": self.context,
                "evidence_ids": self.evidence,
            },
        }


@dataclass
class IdentityChapter:
    """
    A chapter in the developer's identity timeline.

    Represents a period where a set of beliefs/preferences were active.
    """
    period_start: datetime
    period_end: datetime | None  # None = current chapter
    title: str  # "Python + Django Era", "FastAPI Migration", etc.
    beliefs: list[Belief] = field(default_factory=list)
    status: str = "current"  # 'current' or 'superseded'
    trigger: str | None = None  # What caused this chapter to begin

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "title": self.title,
            "status": self.status,
            "trigger": self.trigger,
            "beliefs": [b.content for b in self.beliefs],
            "belief_count": len(self.beliefs),
        }


class IdentityTimeline:
    """
    Manages the developer's identity evolution across chapters.

    Tracks beliefs, handles supersession, and schedules periodic
    challenge intervals for belief review.
    """

    def __init__(self) -> None:
        self.chapters: list[IdentityChapter] = []
        self.challenge_interval_months: int = 3  # Review every 3-6 months

    def add_chapter(self, chapter: IdentityChapter) -> None:
        """Add a new chapter, closing the previous one."""
        if self.chapters and self.chapters[-1].period_end is None:
            self.chapters[-1].period_end = chapter.period_start
            self.chapters[-1].status = "superseded"
        self.chapters.append(chapter)

    def supersede_belief(
        self,
        old_belief: Belief,
        new_content: str,
        reason: str,
    ) -> Belief:
        """
        Replace an old belief with a new one, maintaining the chain.

        The old belief is marked 'superseded' and linked to its successor.
        """
        new_belief = Belief(
            id=f"belief-{datetime.now(timezone.utc).timestamp()}",
            content=new_content,
            state="current",
            established_at=datetime.now(timezone.utc),
            tags=old_belief.tags,
            evidence=[],
        )

        old_belief.state = "superseded"
        old_belief.superseded_at = datetime.now(timezone.utc)
        old_belief.successor_id = new_belief.id

        return new_belief

    def get_beliefs_for_challenge(self) -> list[Belief]:
        """
        Find beliefs that are due for periodic review.

        Returns beliefs that have been 'current' for longer than
        the challenge interval without being reviewed.
        """
        now = datetime.now(timezone.utc)
        challenge_cutoff = now - timedelta(
            days=self.challenge_interval_months * 30
        )

        due_for_review: list[Belief] = []
        if not self.chapters:
            return due_for_review

        current_chapter = self.chapters[-1]
        for belief in current_chapter.beliefs:
            if (belief.state == "current" and
                    belief.established_at < challenge_cutoff):
                due_for_review.append(belief)

        return due_for_review

    def generate_challenge_questions(
        self,
        beliefs: list[Belief],
    ) -> list[dict[str, str]]:
        """
        Generate review questions for beliefs due for challenge.

        Returns questions in the format:
        {"belief": "...", "question": "Do you still...?", "belief_id": "..."}
        """
        questions: list[dict[str, str]] = []
        for belief in beliefs:
            questions.append({
                "belief_id": belief.id,
                "belief": belief.content,
                "question": f"Do you still believe: \"{belief.content}\"? "
                           f"(Established {belief.established_at.strftime('%Y-%m-%d')})",
            })
        return questions
```

### Challenge Intervals

Every 3-6 months, the system reviews core beliefs:

```
┌──────────────────────────────────────────────────────┐
│            Identity Challenge Cycle                    │
│                                                       │
│   Month 1-3: Accumulate new evidence                  │
│   Month 3:   System asks "Do you still believe X?"    │
│                                                       │
│   User responds:                                      │
│   ├── "Yes" → Belief stays 'current', timer resets    │
│   ├── "No"  → Belief becomes 'superseded', new one    │
│   ├── "Not sure" → Belief becomes 'uncertain'         │
│   └── "It depends" → Belief becomes 'contextual'      │
│                                                       │
│   Month 4-6: Accumulate, challenge again...           │
└──────────────────────────────────────────────────────┘
```

### Belief State Transitions

```
                    ┌──────────┐
          ┌────────►│ exploring │
          │         └─────┬────┘
          │               │ confirmed
          │               ▼
    ┌─────┴─────┐   ┌─────────┐    challenged    ┌───────────┐
    │ uncertain │◄──│ current │───────────────►│ uncertain │
    └───────────┘   └────┬────┘               └─────┬─────┘
                         │ replaced                  │ resolved
                         ▼                           ▼
                   ┌────────────┐             ┌─────────┐
                   │ superseded │             │ current │
                   └────────────┘             └─────────┘

                   ┌─────────────┐
                   │ contextual  │ (true in some contexts)
                   └─────────────┘

                   ┌─────────┐
                   │ retired │ (no longer relevant)
                   └─────────┘
```

> [!TIP]
> **Why track belief evolution?** Without it, the system treats a preference from 2 years ago with the same weight as one from yesterday. Identity evolution lets the system know that "Prefers Django" was superseded by "Prefers FastAPI" — so it never suggests Django patterns for new projects.
