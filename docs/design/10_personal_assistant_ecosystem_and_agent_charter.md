# 10. Personal Assistant Ecosystem & Agent Charter

> **Mandatory reading for any AI agent, coding assistant, or background worker.**
> This document states Raja's core vision, the "Jarvis" personal assistant thesis,
> the unified identity model, and the operating rules for the multi-agent ecosystem.
>
> **Last updated:** 2026-10-19 | **Status:** Active Canonical Design

---

## 1. The Core Vision: The "Jarvis" Life-Partner Thesis

Life Graph is **not** just a multi-tenant SaaS backend or a database utility.

It is designed to be **Raja's lifelong personal AI assistant and partner** (Jarvis to Iron Man) across all facets of his life:
* **Work & Engineering:** Healthcare HIS, ERP, software architecture, and DevOps.
* **Study & Research:** AI research, computer science, paper syntheses, and flashcards (`per-learn`).
* **Family & Personal Life:** Life with his wife, home routines, health, promises, commitments, and native Tamil voice interaction.
* **Hobbies & Interests:** Continuous learning and personal growth.

Every AI agent operating in this repository must understand that it is building a system that models **how Raja thinks, how he makes decisions, and what his non-negotiable values are.**

---

## 2. Invariant: The Unified Identity Model (`tenant: raja`)

### Rule: One Human Being = One Unified Memory Graph
* **Do NOT partition Raja into sub-tenants** (`work_tenant`, `home_tenant`, etc.).
* A human mind is not compartmentalized into separate corporate silos. How Raja decides trade-offs in family life informs his risk tolerance in business architecture; health and energy inform work scheduling.
* All life facets live under **`tenant_id: "raja"`** and radiate from a single central **Identity Node (`Raja`)**.
* `tenant_id` exists strictly as a boundary for **future external SaaS customers** (e.g. `tenant: customer_b`), never for splitting Raja's own life.

### How Domains are Scoped without Clutter
* Separation of concerns is handled via **Tags**, **Graph Edges**, and **Surfaces** in Apache AGE and Postgres:
  * `domain: family`, `domain: work_his`, `domain: study`, `domain: health`
  * When a coding agent works on `his`, it filters searches by `domain: work_his`, but traverses to Raja's **Core Principles** (`tag: core_principle`, `tag: preference`) so it writes code matching his exact philosophy.
  * When the Telegram assistant plans family routines, it respects family time while maintaining awareness of critical work deployments.

---

## 3. The Dual-Sphere Architecture & VRAM Invariant

### Hardware Constraints
The local host (`race-wsl`) runs an **NVIDIA GeForce RTX 5080 with 16 GB VRAM**. 
16 GB cannot hold multiple massive models simultaneously. VRAM must be managed strictly:

```
┌────────────────────────────────────────────────────────────────────────┐
│               LOCAL RTX 5080 VRAM BUDGET (Max ~11.5 GB Used)           │
│  • gemma3:12b (Tamil/English conversational core)         ~8.0 GB      │
│  • faster-whisper CUDA (medium/turbo speech recognition)   ~1.5 GB      │
│  • bge-m3 (Life Graph vector embedding engine)            ~0.6 GB      │
│  • Headroom for Windows / WSL display buffers              ~1.5 GB      │
└────────────────────────────────────────────────────────────────────────┘
```

### Sphere A: The Private Life & Voice Vault (100% Local)
* **Components:** `tamil-ai` (Port 8005), `life-graph` (Port 8080), Faster-Whisper, Edge-TTS, and Gemma 3 12B.
* **Privacy Rule:** Family names, photos, health notes, personal voice audio, and wife/home conversations **MUST NEVER leave the local machine**. They are processed exclusively on the local RTX 5080.
* **Residency:** `OLLAMA_MAX_LOADED_MODELS=2` in `/home/raja/docker/ollama/docker-compose.yml` keeps both `gemma3:12b` and `bge-m3` warm in VRAM permanently.

### Sphere B: The Autonomous Tech Swarm (Cloud Free-Tier Swarm)
* **Components:** OpenRouter free tier (`qwen-2.5-coder-32b:free`, `llama-3.3-70b:free`, `gemini-2.0-flash:free`), LiteLLM gateway (Port 4000).
* **The Micro-Task Rule:**
  * Agents executing coding tasks must **NOT** load heavy 30B models locally that starve the local voice VRAM.
  * Deconstruct coding features into atomic micro-tasks (< 50 lines).
  * Dispatch generic coding tasks to the free cloud swarm.
  * Run local verification in an isolated git worktree via `ruff check` and `pytest`.
  * Only merge if **100% of tests pass** (Fail-closed autonomy).

---

## 4. The Satellite Ecosystem Map

To prevent `life-graph` from bloating into an unmaintainable monolith, the ecosystem is decoupled across modular repositories:

| Repository / Service | Host / Port | Role |
| :--- | :--- | :--- |
| **`life-graph`** | `race-wsl:8080` | **The Brain & Substrate:** Knowledge graph (Apache AGE), semantic search (pgvector), nightly sleep consolidation (3AM), capture spine, judgment engine. |
| **`life-graph-ui`** | `race-wsl:5173` | **The Visual Cockpit:** React + TypeScript dashboard, approval queues, memory timelines, graph visualizer. |
| **`tamil-ai`** | `race-wsl:8005` | **Ears & Mouth:** Real-time conversational Tamil/English voice studio (`faster-whisper`, `edge-tts`, WebSocket stream, `life_graph_bridge.py`). |
| **`his` / `apptx-v2`** | `~/Projects/` | **Engineering Domains:** Hospital Information System and multi-tenant ERP codebases. |
| **`per-learn`** | `~/Projects/` | **Study & Knowledge:** AI concepts, architecture guides, and study notes. |
| **Telegram Bridge** | Background Poller | **Mobile Life Interface:** Phone capture of text, photos, and voice notes via `@BotFather` integration. |

---

## 5. Protocols for Any Agent Working with Raja

When you (an AI agent) are tasked with building, debugging, or modifying code in this ecosystem:

1. **Check Established Context First:**
   * Query Life Graph: `POST /api/v1/search/` with `X-Tenant-ID: raja` before proposing major architectural shifts or asking Raja to re-explain his stack.
2. **Deterministic Code Over LLM Prompts:**
   * If logic can be solved with Python regex, standard algorithms, or database queries, do not burn LLM tokens. Reserve models for genuine ambiguity.
3. **Capture Decisions Automatically:**
   * When an architectural or product decision is made, emit a capture event: `POST /api/v1/capture/` with `X-Tenant-ID: raja` and `surface: "agent"` so the rest of the ecosystem stays synchronized.
4. **Preserve Native Language Support:**
   * The conversational assistant natively speaks fluent Tamil, Tanglish, and English. Never degrade Tamil phonetic accuracy or replace the warm conversational tone with robotic generic replies.
