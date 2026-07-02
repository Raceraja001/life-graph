# Life Graph — Requirements Specification

> Brain-inspired, self-hosted personal memory system + AI coding team

---

## User Stories

### US-1: Persistent Developer Memory
**As a** solo developer,
**I want** my AI agents to permanently remember my coding preferences, past decisions, and reasoning,
**So that** I never have to re-explain myself across sessions.

#### Acceptance Criteria
- WHEN a new session starts, THE SYSTEM SHALL load the user's identity, active decisions, and pending intentions from the knowledge store.
- WHEN the user expresses a preference (e.g., "I prefer FastAPI"), THE SYSTEM SHALL extract and store it as a memory with importance scoring.
- WHEN a stored memory is relevant to the current context, THE SYSTEM SHALL proactively surface it without the user searching.
- WHEN the user contradicts a previous preference, THE SYSTEM SHALL detect the contradiction and ask for resolution (supersede, scope, or keep both).

---

### US-2: Cold Start Bootstrap
**As a** new user setting up the system,
**I want** the system to automatically learn about me from my existing code and notes,
**So that** I get immediate value without manually entering preferences.

#### Acceptance Criteria
- WHEN the user provides Git repository paths, THE SYSTEM SHALL analyze commit history, code patterns, and dependencies within 10 minutes.
- WHEN the user provides an Obsidian vault path, THE SYSTEM SHALL import decisions and lessons from well-connected notes.
- WHEN parsing config files (pyproject.toml, tsconfig.json, Dockerfile), THE SYSTEM SHALL extract coding style preferences (formatting, linting, testing frameworks).
- WHEN cold start completes, THE SYSTEM SHALL have extracted at least 50 memories without any LLM API calls.
- WHEN analyzing Python codebases, THE SYSTEM SHALL detect naming conventions, type hint usage, error handling patterns, and architecture structure.

---

### US-3: Proactive Recall
**As a** developer working on a project,
**I want** the system to push relevant memories to me at the right time,
**So that** I benefit from past decisions without having to search.

#### Acceptance Criteria
- WHEN the user opens a file that was previously discussed, THE SYSTEM SHALL surface related decisions and conventions.
- WHEN the user starts working on a project, THE SYSTEM SHALL present relevant architecture decisions and active intentions.
- WHEN the user encounters an error matching a past bug, THE SYSTEM SHALL surface the previous fix.
- WHEN a time-based intention is due, THE SYSTEM SHALL notify the user at session start.
- THE SYSTEM SHALL limit proactive surfaces to 3-5 per session start and 1-2 during active work.
- THE SYSTEM SHALL NOT surface the same memory within a 7-day cooldown period.
- WHEN the user dismisses a category of surfaces 3+ times, THE SYSTEM SHALL auto-suppress that category.

---

### US-4: Intentions / Prospective Memory
**As a** developer with future tasks in mind,
**I want** the system to remember my planned actions and remind me at the right moment,
**So that** I don't forget TODOs across sessions.

#### Acceptance Criteria
- WHEN the user says "I should refactor auth later", THE SYSTEM SHALL create an intention with an event-based trigger.
- WHEN the user says "remind me to deploy by Friday", THE SYSTEM SHALL create an intention with a time-based trigger.
- WHEN the user's current context matches an intention's trigger condition, THE SYSTEM SHALL surface the intention proactively.
- WHEN an intention is completed, THE SYSTEM SHALL mark it as completed and stop surfacing it.
- WHEN an intention passes its expiry date, THE SYSTEM SHALL mark it as expired.

---

### US-5: Schema-less Memory Storage
**As a** long-term user whose life and interests evolve,
**I want** the memory system to grow in any direction without rigid categories,
**So that** the system never becomes a cage that forces my life into fixed boxes.

#### Acceptance Criteria
- THE SYSTEM SHALL store memories with open-ended tags instead of hardcoded type enums.
- THE SYSTEM SHALL allow user-defined domains that can be created, merged, split, or archived at any time.
- THE SYSTEM SHALL use JSONB properties for flexible key-value metadata on every memory.
- WHEN the system suggests a type or domain for a memory, it SHALL mark it as `user_confirmed: false` until validated.
- THE SYSTEM SHALL NOT refuse to store a memory because it doesn't fit a predefined category.

---

### US-6: Memory Lifecycle (Forgetting & Evolution)
**As a** user with years of accumulated memories,
**I want** the system to manage memory relevance over time,
**So that** retrieval stays useful and isn't polluted by stale information.

#### Acceptance Criteria
- WHEN a memory hasn't been accessed in a configurable period, THE SYSTEM SHALL reduce its effective retrieval weight using decay scoring.
- WHEN a memory is accessed, THE SYSTEM SHALL update its access count, last_accessed timestamp, and optionally enrich it with current context (reconsolidation).
- THE SYSTEM SHALL NOT auto-retire memories marked as "critical" importance tier.
- WHEN memories decay below a configurable threshold, THE SYSTEM SHALL archive them (status = 'retired'), not delete them.
- THE SYSTEM SHALL run a nightly consolidation pipeline that: clusters session memories, deduplicates near-identical entries, distills patterns into principles, updates decay scores, and checks for contradictions.

---

### US-7: Metamemory (Self-Awareness)
**As a** user who wants honest answers,
**I want** the system to know what it doesn't know,
**So that** it tells me when its information is incomplete or uncertain instead of guessing.

#### Acceptance Criteria
- WHEN the system retrieves memories with confidence < 0.3 for a query, THE SYSTEM SHALL respond with "I don't have reliable information on this."
- WHEN the system has partial information (confidence 0.3-0.7), THE SYSTEM SHALL caveat its response as potentially incomplete.
- WHEN the user asks about a topic 3+ times with no stored preferences, THE SYSTEM SHALL proactively suggest: "Want to teach me about this?"
- THE SYSTEM SHALL track knowledge gaps (topics asked about but not stored).

---

### US-8: Identity Evolution
**As a** person who changes over time,
**I want** the system to support my growth instead of locking me into past beliefs,
**So that** who I was doesn't prevent me from becoming who I want to be.

#### Acceptance Criteria
- THE SYSTEM SHALL support belief states: current, superseded, uncertain, exploring, contextual, retired.
- WHEN an identity memory hasn't been challenged in 6 months, THE SYSTEM SHALL prompt: "You've held this belief for N months. Still current?"
- THE SYSTEM SHALL maintain an identity timeline showing how beliefs evolved over chapters.
- THE SYSTEM SHALL periodically challenge stale preferences: "You've used X for 2 years. The ecosystem has changed. Worth reconsidering?"

---

### US-9: LLM-Minimal Architecture
**As a** cost-conscious solo developer,
**I want** 85%+ of memory operations to work without LLM API calls,
**So that** my monthly AI costs stay under $30-80.

#### Acceptance Criteria
- THE SYSTEM SHALL use spaCy NER + regex patterns for fact extraction (LLM fallback only for ambiguous cases, ~20%).
- THE SYSTEM SHALL use signal-based rules for importance scoring (zero LLM calls).
- THE SYSTEM SHALL use embedding similarity + regex for contradiction detection (LLM only ~10%).
- THE SYSTEM SHALL use session state + keywords for context classification (zero LLM calls).
- THE SYSTEM SHALL use regex pattern matching for query routing (zero LLM calls).
- THE SYSTEM SHALL use LLM only for consolidation/distillation (1 call per day, cheap model).
- THE SYSTEM SHALL use local sentence-transformers for embeddings (zero API cost).

---

### US-10: Data Sovereignty & Portability
**As a** privacy-conscious developer,
**I want** complete ownership and control of my lifetime memories,
**So that** no vendor can access, revoke, or lock in my personal data.

#### Acceptance Criteria
- THE SYSTEM SHALL run entirely self-hosted (VPS or local machine).
- THE SYSTEM SHALL store all data in PostgreSQL (user-controlled).
- THE SYSTEM SHALL support full export as Markdown/YAML + JSON-LD + database dump.
- WHEN the user requests deletion of a specific memory, THE SYSTEM SHALL cascade-delete the memory, its embeddings, and all graph relationships.
- THE SYSTEM SHALL encrypt data at rest and require TLS for remote access.
- THE SYSTEM SHALL log all data access in an audit trail.

---

### US-11: Agent Integration
**As a** developer using AI coding agents,
**I want** my agents to automatically receive relevant context from my memory system,
**So that** every agent task is informed by my preferences, patterns, and past decisions.

#### Acceptance Criteria
- WHEN a CrewAI agent starts a task, THE SYSTEM SHALL inject relevant memories as context (identity, decisions, experience, intentions, warnings).
- WHEN a CrewAI agent completes a task, THE SYSTEM SHALL extract new knowledge from the task conversation and store it.
- THE SYSTEM SHALL provide a LifeGraphBridge interface that any agent framework can consume.
- THE SYSTEM SHALL route LLM calls through LiteLLM for cost optimization.

---

### US-12: Multi-Modal Memories (Phase 2)
**As a** user who captures ideas in various formats,
**I want** the system to handle images, voice notes, and screenshots,
**So that** my memory isn't limited to text.

#### Acceptance Criteria
- WHEN a voice note is provided, THE SYSTEM SHALL transcribe it with Whisper and store both the transcript and audio.
- WHEN a screenshot is provided, THE SYSTEM SHALL extract text via OCR and generate a description.
- WHEN an image is provided, THE SYSTEM SHALL generate CLIP embeddings for cross-modal search.
- THE SYSTEM SHALL store original files in S3-compatible object storage (MinIO) with references in PostgreSQL.

---

### US-13: Plugin Architecture (Phase 2)
**As a** developer who wants to extend the system,
**I want** a plugin/extension mechanism,
**So that** I can add new input sources and behaviors without modifying core code.

#### Acceptance Criteria
- THE SYSTEM SHALL emit events on memory lifecycle (created, retrieved, updated, deleted, session_end).
- THE SYSTEM SHALL provide an EventBus that plugins can subscribe to.
- Plugins SHALL be able to add metadata to memories during the `memory:created` event.
- Plugins SHALL be able to modify retrieval results during the `memory:retrieved` event.
- THE SYSTEM SHALL document a Plugin API for third-party developers.

---

## Non-Functional Requirements

### NFR-1: Performance
- Vector search SHALL return results in <50ms for up to 1M memories.
- Cold start bootstrap SHALL complete in <10 minutes for 5 repos + 500 notes.
- Proactive recall context building SHALL complete in <200ms at session start.

### NFR-2: Scalability
- THE SYSTEM SHALL support 10+ years of continuous memory accumulation.
- THE SYSTEM SHALL support partitioning for memories exceeding 1M rows.
- THE SYSTEM SHALL use halfvec(768) embeddings for 50% storage reduction.

### NFR-3: Reliability
- THE SYSTEM SHALL perform daily automated backups (pg_dump + encrypted off-site).
- THE SYSTEM SHALL support point-in-time recovery via WAL archiving.
- Monthly restore drills SHALL verify backup integrity.

### NFR-4: Cost
- Monthly LLM API costs SHALL NOT exceed $30-80 under normal usage.
- All NLP operations (embedding, NER, classification) SHALL use local models by default.
- THE SYSTEM SHALL track and report daily API cost metrics.
