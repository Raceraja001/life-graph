# 🧠 The Life Graph v2: Definitive Design

> Synthesized from neuroscience, PKM failure research, and privacy/architecture analysis.
> This is the improved blueprint — what Mem0, Letta, and Zep should have built.

---

## The 8 Brain-Inspired Innovations

These come directly from how human memory actually works. None of the existing tools implement all of them.

### 1. 🔄 Memory Consolidation Pipeline
**Borrowed from:** Hippocampus → Neocortex transfer during sleep

Your brain doesn't permanently store everything the instant it happens. It sits in a temporary buffer, gets reviewed during sleep, and only the important stuff gets promoted to long-term storage.

```
Session Interaction
       │
       ▼
┌──────────────┐     Background Job      ┌──────────────────┐
│ Session      │    (runs end-of-day)     │  Permanent       │
│ Buffer       │ ──────────────────────►  │  Knowledge Store │
│              │  Extract patterns        │                  │
│ Raw memories │  Merge with existing     │  Distilled facts │
│ Full context │  Discard noise           │  Linked concepts │
│ Conversation │  Link to graph           │  Updated beliefs │
│ logs         │                          │                  │
└──────────────┘                          └──────────────────┘
```

**Why this matters:** Instead of dumping everything into the vector DB (noise!), a nightly "sleep cycle" reviews the day's interactions, extracts principles, and integrates them with existing knowledge. Just like your brain does.

**What existing tools do:** Dump everything immediately into storage. No review, no integration, no noise filtering.

---

### 2. 📉 Forgetting Curve & Decay Scoring
**Borrowed from:** Ebbinghaus forgetting curve + active synaptic pruning

Your brain actively FORGETS things that aren't important. This isn't failure — it's memory management.

```python
# Every memory gets a living score
effective_weight = importance × (access_count^0.3) × e^(-λ × days_since_access)

# Example after 30 days with no access:
#   "Always use Pydantic"     → importance=0.9, accessed 12x → score: 0.87 (stays)
#   "Mentioned pizza Tuesday" → importance=0.1, accessed 0x  → score: 0.003 (fades)
```

| Priority Tier | Analog | Decay Rate | Example |
|---|---|---|---|
| 🔴 Critical | Traumatic memory | Almost zero | "Never deploy Friday — caused data loss" |
| 🟠 Important | Emotional event | Very slow | Architecture decisions, cost choices |
| 🟡 Normal | Regular memory | Normal | Coding preferences, tool choices |
| 🟢 Low | Trivial memory | Fast | One-off conversation details |

**What existing tools do:** Store everything forever with equal weight. No decay. No pruning.

---

### 3. 🎯 Context-Dependent Retrieval
**Borrowed from:** Encoding Specificity Principle (Tulving, 1973)

You remember things better when you're in the SAME context where you learned them. A scuba diver recalls underwater lessons better when underwater.

```python
# Every memory stores rich context
memory = {
    "content": "Use JWT with short-lived tokens + refresh tokens",
    "context": {
        "project": "ai-agent-platform",
        "module": "auth-system",
        "phase": "design",
        "tools_active": ["FastAPI", "Docker"],
        "files_open": ["auth/routes.py"]
    }
}

# Retrieval boosts memories from matching context
def smart_retrieve(query, current_context):
    results = vector_search(query)
    for r in results:
        context_match = overlap(r.context, current_context)
        r.score = (0.6 × r.semantic_score) + (0.4 × context_match)
    return sorted(results)
```

**Result:** When you're working on auth, auth-related memories surface more strongly — even if the semantic match isn't perfect. Just like your brain.

**What existing tools do:** Pure semantic similarity. No context awareness.

---

### 4. 🔁 Memory Reconsolidation (Memories Evolve)
**Borrowed from:** Nader et al. (2000) — memories become modifiable when recalled

Every time you recall a memory, your brain rewrites it slightly. Memories aren't recordings — they're living documents.

```python
def retrieve_and_evolve(query, current_context):
    memory = find_memory(query)
    
    # Retrieval is NOT read-only — it's an update
    memory.access_count += 1
    memory.last_accessed = now()
    memory.related_contexts.append(current_context.summary)
    
    # Check for contradictions
    if contradicts(memory.content, current_context):
        memory.confidence -= 0.1
        memory.needs_review = True
    
    # Re-embed with accumulated context (memory evolves)
    memory.embedding = re_embed(memory.content + memory.context_history)
    
    save(memory)
    return memory
```

**Result:** A decision made in Phase 1 ("use PostgreSQL") gets enriched with Phase 2 context ("also great for pgvector") — becoming more useful over time.

**What existing tools do:** Immutable records. Once stored, never enriched.

---

### 5. ❤️ Importance Tagging (Emotional Analog)
**Borrowed from:** Amygdala's emotional significance detection

Your brain remembers emotional events more vividly. We simulate this with signal-based importance scoring.

```python
def calculate_importance(content, conversation):
    signals = {
        "explicit_emphasis":  detect("IMPORTANT", "never do", "always"),  # 0.9
        "from_failure":       is_bug_or_incident(content),               # 0.85
        "architecture_decision": is_arch_decision(content),              # 0.8
        "repeated_mention":   times_mentioned(content) > 2,             # 0.7
        "cost_impact":        has_financial_implications(content),        # 0.75
        "user_said_remember": "remember this" in conversation,          # 0.95
        "casual_mention":     is_offhand_comment(content),              # 0.2
    }
    return weighted_score(signals)
```

**Result:** "NEVER use eval() — it caused a security breach" gets stored as critical. "I had pizza for lunch" gets minimum weight. Current tools treat both equally.

---

### 6. 🔮 Intentions Store (Prospective Memory)
**Borrowed from:** Prefrontal cortex — remembering to do things in the future

This is the **biggest gap** in every existing tool. No AI memory system can say "remember to do X when Y happens."

```yaml
intention:
  content: "Refactor auth module to use refresh tokens"
  trigger:
    type: event                          # or "time"
    condition: "user opens auth/ OR mentions auth"
    time_condition: null                 # or "2026-07-10"
  priority: high
  status: pending                        # pending → triggered → completed → expired
  created_context: "security review session"
  expiry: 2026-08-01
```

**How it works:**
1. During conversation, agent detects intentions ("I should refactor that auth module later")
2. Stores with trigger conditions
3. At the START of every future session, checks:
   - Are any time-based triggers due?
   - Does the current context match any event triggers?
4. Proactively surfaces: "You mentioned wanting to refactor auth — you're in that module now. Want to do it?"

**What existing tools do:** Nothing. Zero prospective memory.

---

### 7. ⚔️ Contradiction Detection & Resolution
**Borrowed from:** Anterior Cingulate Cortex — conflict monitoring

```python
def store_with_conflict_check(new_memory):
    similar = search_existing(new_memory.topic)
    
    for old in similar:
        conflict = detect_contradiction(old, new_memory)
        
        if conflict.score > 0.8:
            if is_newer_and_explicit(new_memory):
                # SUPERSEDE: Mark old as replaced
                old.status = "superseded"
                old.superseded_by = new_memory.id
                old.superseded_reason = "User explicitly changed preference"
                
            elif different_scope(old, new_memory):
                # SCOPE: Both valid in different contexts
                old.scope = "production"
                new_memory.scope = "prototyping"
                
            else:
                # ASK: Ambiguous — ask the user
                prompt_user(f"You previously said '{old.content}' "
                           f"but now said '{new_memory.content}'. "
                           f"Which is current?")
```

**Result:** No more silent contradictions in your knowledge base. Old decisions get marked as superseded with reasoning — creating a decision history.

---

### 8. 🪞 Metamemory (Knowing What You Know)
**Borrowed from:** Prefrontal cortex metacognitive monitoring

The agent should know what it DOESN'T know.

```python
def query_with_awareness(query):
    results = retrieve(query)
    
    confidence = assess_confidence(results)
    
    if confidence < 0.3:
        return "I don't have reliable info on this. Want to teach me?"
    elif confidence < 0.7:
        return f"I have partial info (may be outdated): {results}"
    else:
        return f"Based on your preferences: {results}"

# Track knowledge gaps
gaps = track_unanswered_queries()
# → "You've asked about Kubernetes 3 times but I have no preferences stored.
#    Want to add your K8s setup?"
```

**Result:** The agent proactively identifies its own blind spots and asks to learn — instead of silently making stuff up.

---

## The 7 Anti-Patterns We Must Avoid

From studying why Obsidian/Notion/Roam users abandon their systems:

| # | Anti-Pattern | Our Solution |
|---|---|---|
| 1 | **Maintenance tax** — spending more time organizing than using | AI handles ALL organization. Zero user effort. |
| 2 | **Collector's Fallacy** — saving = feeling productive | Only store DECISIONS, PATTERNS, LESSONS — not bookmarks |
| 3 | **Information graveyards** — notes never revisited | **Proactive recall** — system surfaces relevant memories automatically |
| 4 | **Cold start death** — empty system = no value = abandonment | **Pre-populate from Git repos, code analysis, existing notes** |
| 5 | **Capture friction** — too many steps to save | Agent OBSERVES your work. You never "save" anything manually. |
| 6 | **Reactive only** — user must search for everything | **Proactive surfacing** during workflow. "You used pattern X for this before." |
| 7 | **Proprietary lock-in** | Markdown/YAML canonical format. PostgreSQL. Everything exportable. |

---

## Unified Architecture

### Database: One PostgreSQL, Three Capabilities

```
┌────────────────────────────────────────────────────┐
│              PostgreSQL 16+                         │
│                                                     │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────┐ │
│  │   pgvector    │  │Apache AGE│  │  Core Tables │ │
│  │              │  │          │  │              │ │
│  │ Semantic     │  │ Knowledge│  │ Memories     │ │
│  │ similarity   │  │ graph    │  │ Intentions   │ │
│  │ search       │  │ queries  │  │ Domains      │ │
│  │              │  │ (Cypher) │  │ Sessions     │ │
│  │ Experiences  │  │ Entities │  │ Metadata     │ │
│  │ Patterns     │  │ Relations│  │ Gaps         │ │
│  │ Code chunks  │  │ Temporal │  │ Audit log    │ │
│  └──────────────┘  └──────────┘  └──────────────┘ │
│                                                     │
│  Single backup target. ACID transactions.           │
│  Vector + Graph + Relational in one process.        │
└────────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │  MinIO  │  (S3-compatible object storage)
    │         │  Images, voice notes, screenshots
    │         │  PDFs, design docs
    └─────────┘
```

**Why not ChromaDB?** ChromaDB is vector-only. PostgreSQL with pgvector + Apache AGE gives us vector, graph, AND relational in one ACID-compliant database with one backup target.

### Multi-Modal Input Pipeline

```
Text  ──────────────────────────────→ Embed + Extract entities
Images ──→ CLIP embedding + caption → Embed + Store in MinIO
Voice ───→ Whisper STT → text ─────→ Embed + Extract entities  
Screenshots → OCR + caption ───────→ Embed + Store in MinIO
```

All modalities end up in the same unified vector + graph space. You can search "find the screenshot where I discussed auth" and it works.

### Security & Sovereignty

| Layer | Protection |
|---|---|
| **At rest** | PostgreSQL TDE + disk encryption (BitLocker/LUKS) |
| **In transit** | TLS 1.3 + WireGuard/Tailscale VPN |
| **Access** | Single user, localhost only (or VPN) |
| **Backup** | Daily pg_dump + encrypted off-site (Restic) |
| **Versioning** | Bitemporal modeling (valid_from/valid_to on every fact) |
| **Portability** | Export as Markdown/YAML + JSON-LD + DB dump |
| **Right to forget** | Cascade deletion pipeline with audit trail |
| **Poisoning prevention** | Source provenance + confidence scoring + fact auditing |

---

## The Complete Memory Schema

Every memory in the system:

```yaml
memory:
  id: uuid
  content: "Decided to use FastAPI for all APIs"
  
  # TYPE — what kind of memory
  type: decision        # identity | decision | experience | knowledge |
                        # reflection | intention
  
  # DOMAIN — which part of your life
  domain: code          # code | life | career | health | finance | projects
  
  # IMPORTANCE — emotional analog
  importance: 0.85      # 0.0 → 1.0, from signal detection
  importance_tier: high  # critical | high | normal | low
  
  # CONFIDENCE — metamemory
  confidence: 0.95      # how sure are we this is accurate
  source_type: explicit  # inferred | mentioned | stated | explicit | core_belief
  
  # CONTEXT — encoding specificity
  context:
    project: "ai-agent-platform"
    module: "backend"
    phase: "design"
    tools: ["FastAPI", "Python"]
    conversation_topic: "framework selection"
  
  # TEMPORAL — when was this true
  created_at: 2026-07-02
  valid_from: 2026-07-02
  valid_until: null       # null = still current
  
  # REASONING — the WHY (unique to us)
  reasoning: "Flask too bare, Django too heavy. FastAPI = type safety + async + auto docs."
  
  # RELATIONSHIPS — graph connections
  related_to: ["pydantic-preference", "type-safety-value", "api-platform-project"]
  supersedes: null        # or ID of old memory this replaces
  superseded_by: null
  
  # LIFECYCLE — forgetting curve
  access_count: 7
  last_accessed: 2026-07-01
  decay_score: 0.92       # calculated field
  
  # PROVENANCE — poisoning prevention
  source: "conversation-2026-07-02-session-3"
  trust_score: 0.9
  
  # EMBEDDING
  embedding: [0.023, -0.041, ...]  # pgvector
```

---

## Proactive Recall — The Killer Feature

This is what separates a "database" from a "brain." The system doesn't wait for you to search. It **pushes** relevant memories to you.

```
┌──────────────────────────────────────────────────┐
│          SESSION START                             │
│                                                    │
│  1. Load your Identity layer (always)             │
│  2. Detect current context:                        │
│     - What project? What files? What topic?       │
│  3. Check Intentions:                              │
│     → "You said you'd refactor auth this week"    │
│  4. Surface relevant experience:                   │
│     → "Last time you built similar endpoint,      │
│        you used dependency injection pattern"     │
│  5. Flag knowledge gaps:                           │
│     → "You've asked about Redis 3x but I         │
│        don't have your caching preferences"       │
│  6. Check for stale facts:                         │
│     → "Your Node.js version preference is         │
│        6 months old — still current?"             │
│                                                    │
│  All automatic. Zero user effort.                 │
└──────────────────────────────────────────────────┘
```

---

## Cold Start Solution

The #1 killer of PKM systems. We solve it by pre-populating:

```
Day 1 Import Sources:
├── Git repositories → analyze coding style, framework choices, patterns
├── Git commit history → decision patterns, project timeline
├── Existing KNOWLEDGE.md / AGENTS.md → explicit preferences
├── Obsidian/Notion export (if exists) → existing notes
├── package.json / requirements.txt → tech stack facts
├── README files → project context
└── First few conversations → rapid preference learning
```

The system should have **50+ useful memories within the first hour** without the user manually entering anything.

---

## Implementation Priority

| # | Innovation | Effort | Impact | When |
|---|---|---|---|---|
| 1 | Importance Tagging | 🟢 3 days | 🟢 Huge | Week 1 |
| 2 | Context Metadata | 🟢 3 days | 🟢 Huge | Week 1 |
| 3 | Cold Start / Import | 🟡 1 week | 🟢 Huge | Week 1-2 |
| 4 | Intentions Store | 🟡 1 week | 🟢 Huge | Week 2 |
| 5 | Proactive Recall | 🟡 1 week | 🟢 Huge | Week 2-3 |
| 6 | Contradiction Detection | 🟡 1 week | 🟡 High | Week 3 |
| 7 | Forgetting / Decay | 🟢 3 days | 🟡 High | Week 3 |
| 8 | Metamemory / Gaps | 🟢 3 days | 🟡 High | Week 4 |
| 9 | Reconsolidation | 🟡 1 week | 🟡 Medium | Week 4 |
| 10 | Consolidation Pipeline | 🔴 2 weeks | 🟡 Medium | Week 5-6 |
| 11 | Multi-modal (images/voice) | 🔴 2 weeks | 🟡 Medium | Week 7-8 |

**Core system (innovations 1-7) buildable in ~4-5 weeks.**

---

> [!IMPORTANT]
> ### What Makes This Different From Everything Else
> 
> | What Mem0/Letta/Zep do | What we do |
> |---|---|
> | Store facts | Store facts + WHY + confidence + importance |
> | Flat retrieval | Context-aware retrieval + proactive surfacing |
> | Code-only | Life-wide domains (code, career, health, finance) |
> | AI decides what to remember | AI proposes, you can browse/edit/curate |
> | No prospective memory | Intentions store with trigger-based recall |
> | No self-awareness | Metamemory — knows what it doesn't know |
> | Equal weight for all memories | Importance tiers with forgetting curve |
> | Immutable records | Memories evolve on access (reconsolidation) |
> | Cold start problem | Pre-populates from your existing code/notes |
> | Vendor-hosted | Self-hosted, encrypted, fully portable |
> 
> This isn't just a better memory system. It's a system that **thinks about memory the way your brain does** — and then does it better, because it never sleeps and never loses data.
