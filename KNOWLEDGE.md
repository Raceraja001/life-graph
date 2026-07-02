# 🧠 Project Knowledge Base

## Who You Are
- Solo developer building personal tools and infrastructure
- Previous projects: Universal Deployment Platform, Hugging Face model integration
- OS: Windows, deploys on self-hosted VPS
- Values: self-hosted, cost-efficient, no vendor lock-in, own your toolchain

## What You're Building
**Life Graph** — A lifetime personal memory system + AI coding team that:
1. Knows you permanently (coding style, preferences, decisions, life history)
2. Costs $30-80/month on API tokens instead of $300-500/month on subscriptions
3. Never needs you to re-explain yourself — grows smarter with every interaction
4. Extends beyond code — covers career, health, finance, personal decisions
5. Uses brain-inspired memory mechanisms (consolidation, decay, proactive recall)

## Why (Your Core Problems)
1. **Cost**: Paying thousands/year across Codex, Claude Code, Copilot subscriptions
2. **Context reset**: Every session starts from zero — tired of being a human context loader
3. **Generic agents**: Existing tools don't know YOUR preferences, patterns, opinions
4. **Lifetime scope**: Want a system that captures ALL important decisions, not just code

## Key Decisions Made

### Architecture
- **Approach**: Fork OpenHands (has web UI, sandbox, Git, LiteLLM) + add multi-agent team + Life Graph memory
- **Agent framework**: CrewAI for multi-agent orchestration
- **LLM routing**: LiteLLM — cheap models for grunt work, expensive for reasoning
- **Core differentiator**: Life Graph memory system (brain-inspired, not just vector search)
- **Phase 1**: CLI-first, web UI later
- **Timeline**: ~4 weeks to usable MVP

### Memory System (Life Graph)
- **Database**: PostgreSQL + pgvector + Apache AGE (unified vector + graph + relational) — NOT ChromaDB
- **Schema**: Schema-less core with dynamic tags — no hardcoded types or domains
- **Storage pattern**: Interfaces, not implementations — backends are swappable
- **LLM usage**: LLM as ADVISOR, not authority — 85% of operations use rule-based/local models
- **Proactive recall**: System pushes relevant memories, doesn't wait for searches
- **Cold start**: Pre-populate from Git repos, existing notes, code analysis on Day 1

### LLM-Reduction Strategy (85% fewer API calls)
| Operation | Method | LLM Needed? |
|---|---|---|
| Fact extraction | Regex + spaCy NER + dependency parsing | Only ambiguous ~20% |
| Importance scoring | Signal-based rules + user feedback | Never |
| Contradiction detection | Embedding similarity + regex + NER | Only ambiguous ~10% |
| Context classification | Session state + keywords + local classifier | Never |
| Consolidation | Clustering + dedup rule-based, LLM for distillation | 1x/day only |
| Query routing | Pattern-based regex router | Never |
| Tagging | Rules → local classifier → user feedback | Never |

### Extensibility Principles
1. Schema-less core — no hardcoded types/domains
2. Storage abstraction — swap backends freely
3. LLM as advisor — never decides alone, rule-based fallbacks
4. Growth-permitting — identity versions, belief states, exploratory memory
5. Plugin-first — event bus, third-party extensions
6. Ruthless MVP — ship 4 features, add rest over months
7. Future-proof data — versioned embeddings, standard APIs, export everything

### Brain-Inspired Innovations
1. Consolidation pipeline (sleep cycle analog)
2. Forgetting curve with decay scoring
3. Context-dependent retrieval
4. Memory reconsolidation (memories evolve on access)
5. Importance tagging (emotional analog)
6. Intentions store (prospective memory)
7. Contradiction detection and resolution
8. Metamemory (system knows what it doesn't know)

### Anti-Patterns to Avoid (from PKM failure research)
1. No maintenance tax — AI handles ALL organization
2. No collector's fallacy — store decisions/lessons, not bookmarks
3. Proactive recall — don't wait for user to search
4. Cold start solved — pre-populate from existing data
5. Zero capture friction — observe work, don't ask user to file things
6. Retrieval-first design — every memory has a path to being surfaced
7. No proprietary lock-in — Markdown/YAML canonical, PostgreSQL, fully exportable

## Research Completed
- Studied Codex desktop app architecture (Electron + React + ProseMirror, JSON-RPC, Git worktrees)
- Studied GitHub Copilot app (Canvases, BYOM, Agent fleet view)
- Evaluated open source: OpenHands (best fork candidate), MetaGPT (best multi-agent), Omnigent (best orchestration)
- Learned about AG-UI protocol, MCP, A2A standards
- Compared build-vs-buy: building the orchestration layer, not replacing the workers
- Studied Mem0 (Deshraj Yadav, ex-Tesla), Letta/MemGPT (UC Berkeley), Zep/Graphiti founding philosophies
- Analyzed PKM system failures (Obsidian, Notion, Roam) — why people abandon them
- Researched cognitive science: memory consolidation, forgetting curves, context-dependent recall
- Researched privacy/architecture: encryption, data portability, memory poisoning, backup strategies
- Devil's advocate review: identified 15 weaknesses and fixes in our own design

## Tech Stack (Revised)
- **Agent Framework**: CrewAI
- **LLM Routing**: LiteLLM
- **Base Platform**: OpenHands (fork)
- **Backend**: Python / FastAPI
- **Sandbox**: Docker
- **Database**: PostgreSQL + pgvector (vector) + Apache AGE (graph)
- **Object Storage**: MinIO (images, voice, files)
- **Local NLP**: spaCy, sentence-transformers, fastText
- **Frontend**: Web (later) — start CLI
- **Backup**: pg_dump + Restic (encrypted off-site)
- **Access**: WireGuard/Tailscale VPN

## Documents
- `docs/research/01_build_vs_buy_analysis.md` — Strategic trade-off analysis
- `docs/research/02_open_source_evaluation.md` — 7 open source projects evaluated
- `docs/research/03_codex_copilot_design_study.md` — Codex & Copilot architecture deep dive
- `docs/research/04_memory_mechanisms.md` — Storage mechanisms comparison
- `docs/research/05_memory_philosophy.md` — Mem0/Letta/Zep philosophy and limitations
- `docs/design/01_project_scope.md` — Full project scoping (phased roadmap)
- `docs/design/02_life_graph_v2_design.md` — Life Graph v2 definitive design
- `docs/design/03_devils_advocate_review.md` — Critical review and extensibility fixes
- `docs/design/04_database_schema.md` — PostgreSQL + pgvector + Apache AGE schema design
- `docs/design/05_cold_start.md` — Cold start bootstrap system (50+ memories, zero API calls)
- `docs/design/06_proactive_recall.md` — Proactive recall engine (push-based memory surfacing)
