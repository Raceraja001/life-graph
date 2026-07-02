# 🧠 Life Graph

> A brain-inspired, self-hosted personal memory system and AI coding team.

## What Is This?

Life Graph is a lifetime personal memory system that:
- **Remembers you permanently** — coding style, decisions, preferences, life history
- **Costs $30-80/month** instead of $300-500/month on AI subscriptions
- **Grows smarter** with every interaction — never needs re-explaining
- **Goes beyond code** — career, health, finance, personal decisions
- **Uses neuroscience-inspired memory** — consolidation, decay, proactive recall

## Project Status: Research & Design Complete

We've completed extensive research and design. The system is ready for implementation.

### Research Documents (`docs/research/`)
| Document | Contents |
|---|---|
| `01_build_vs_buy_analysis.md` | Should we build from scratch or use existing tools? |
| `02_open_source_evaluation.md` | 7 open source projects evaluated for forking |
| `03_codex_copilot_design_study.md` | How Codex and GitHub Copilot apps are architectured |
| `04_memory_mechanisms.md` | Vector DB vs Knowledge Graph vs Relational — honest comparison |
| `05_memory_philosophy.md` | How Mem0/Letta/Zep founders thought, and where they fell short |

### Design Documents (`docs/design/`)
| Document | Contents |
|---|---|
| `01_project_scope.md` | Phased roadmap and effort estimates |
| `02_life_graph_v2_design.md` | The definitive architecture — 8 brain-inspired innovations |
| `03_devils_advocate_review.md` | Critical self-review — 15 weaknesses and fixes |

## Tech Stack
- **Base Platform**: OpenHands (fork)
- **Backend**: Python / FastAPI
- **Database**: PostgreSQL + pgvector + Apache AGE
- **Agent Framework**: CrewAI
- **LLM Routing**: LiteLLM
- **Local NLP**: spaCy, sentence-transformers
- **Sandbox**: Docker
- **Object Storage**: MinIO

## Key Design Principles
1. Schema-less core — no hardcoded types or domains
2. Storage abstraction — backends are swappable
3. LLM as advisor, not authority — 85% of operations are rule-based
4. Growth-permitting — identity evolves, beliefs can be exploratory
5. Plugin-first — event bus architecture for extensions
6. Proactive recall — system pushes relevant memories, doesn't wait
7. Future-proof data — versioned embeddings, standard APIs, fully exportable

## Quick Links
- [KNOWLEDGE.md](KNOWLEDGE.md) — All decisions and context for this project
- [AGENTS.md](AGENTS.md) — Instructions for AI agents working in this repo
