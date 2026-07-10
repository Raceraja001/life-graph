# ⚠️ STRATEGIC DECISION — READ BEFORE BUILDING ANYTHING

> **Date:** 06 Jul 2026
> **Decision by:** Developer (Raja)
> **Status:** FINAL — do not override without developer approval

---

## The Rule

**DO NOT build what already exists as open-source. pip install it, docker run it, wire it together.**

We spent ~308 developer-days worth of specs planning 65 features. After analysis, **90% of those features already exist as mature open-source tools**. Building them from scratch is reinventing the wheel.

---

## What to USE (Don't Build)

| Need | Use This | Install |
|:-----|:---------|:--------|
| **Coding agent** | Antigravity (you are this) | Already running |
| **Browser automation** | [browser-use](https://github.com/browser-use/browser-use) | `pip install browser-use` |
| **Multi-agent framework** | [CrewAI](https://github.com/crewaiinc/crewai) or [LangGraph](https://github.com/langchain-ai/langgraph) | `pip install crewai` |
| **Memory system** | [Mem0](https://github.com/mem0ai/mem0) | `pip install mem0ai` |
| **LLM routing** | [LiteLLM](https://github.com/BerriAI/litellm) | Already in stack |
| **Eval harness** | [promptfoo](https://github.com/promptfoo/promptfoo) | `npm install -g promptfoo` |
| **LLM tracing + prompt registry** | [Langfuse](https://github.com/langfuse/langfuse) | `docker compose up` (self-hosted) |
| **Workflow builder** | [n8n](https://github.com/n8n-io/n8n) | `docker compose up` (self-hosted) |
| **Research/web search** | [Tavily](https://tavily.com/) or browser-use | API key / pip install |
| **MCP server** | Built into most frameworks now | N/A |

### ❌ DO NOT BUILD FROM SCRATCH:
- ❌ Eval harness (use promptfoo)
- ❌ LLM trace viewer (use Langfuse)
- ❌ Prompt registry (use Langfuse)
- ❌ Workflow builder (use n8n)
- ❌ Memory library (use Mem0)
- ❌ Multi-agent framework (use CrewAI/LangGraph)
- ❌ Browser agent (use browser-use)
- ❌ MCP tool server (use existing MCP implementations)

---

## What to BUILD (Unique to Us)

Only **3 things** don't exist elsewhere and are worth building:

### 1. 🧠 Personal AI Platform (~24 days total)
**Full spec:** `.comms/specs/personal-ai-platform.md` — READ THIS FOR IMPLEMENTATION DETAILS.
**No hardcoded branding** — name, logo, colors come from dynamic config.

Three products that don't exist anywhere:

| Product | What | Days |
|:--------|:-----|:-----|
| **Core (Knowledge Engine)** | Stores YOUR preferences, challenges them with evidence from 3 AI models, weekly autonomous research | 8 |
| **Learn (Self-Optimizer)** | Auto-detects weaknesses, runs DSPy BootstrapFewShot, deploys better prompts without human intervention | 7 |
| **Watch (Ambient AI)** | Monitors deps, server, tech news, code quality. Proactively alerts you BEFORE things break | 9 |

**Monthly cost: ~₹130 ($1.56).** Self-hosted, no vendor lock-in.

**Tech:** FastAPI + PostgreSQL (pgvector + Apache AGE) + LiteLLM + browser-use + Mem0 + DSPy + promptfoo

**NOT the same as:** Perplexity (generic), Obsidian (passive), ChatGPT (no memory of you)

### 2. 💰 Uzhavu Product Factory (~3-4 days)
**Why unique:** Our specific codebase, our market, our revenue opportunity.

**What it does:**
- Frontend layer for the existing SaasProduct model
- Domain-based routing → standalone branded apps
- Template gallery for quick setup
- Launch individual SaaS products (school mgmt, gym tracker, etc.)

**The backend already exists.** Just need the frontend middleware + admin UI.

### 3. 🔗 Integration Layer (~3-5 days)
**Why unique:** The specific glue between existing tools, customized for our workflow.

**What it does:**
- Docker compose that deploys: n8n + Langfuse + Mem0 + our services
- FastAPI orchestrator that wires browser-use + Mem0 + LiteLLM
- Knowledge Engine talks to all tools via unified API
- .comms/ protocol bridge (so agents can read/write shared context)

---

## Implementation Order

| Phase | What | Days | Revenue? |
|:------|:-----|:-----|:---------|
| **Phase 0** | Docker compose: deploy n8n + Langfuse + Mem0 | 1-2 | No |
| **Phase 1** | Knowledge Engine core (preference store + multi-model advisor) | 5 | No |
| **Phase 2** | Wire browser-use + Mem0 into Knowledge Engine | 3 | No |
| **Phase 3** | Product Factory frontend | 3-4 | **YES** |
| **Phase 4** | First standalone app launched (e.g., School Management) | 3-4 | **YES** |
| **Total** | | **~15-20 days** | |

---

## The Specs Are NOT Wasted

The 18 specs in `.comms/specs/` are a **reference library**. Use them when:
- A CUSTOMER needs WhatsApp → build from `whatsapp-bot.md`
- A CUSTOMER needs payments → build from `razorpay-upi.md`
- Revenue justifies the feature → use the spec, don't re-plan

**Don't build features before you have customers paying for them.**

---

## For Any Antigravity Instance Reading This

1. **Read this file FIRST** before starting any work
2. **Check if what you're about to build already exists** as open-source
3. If it exists → install it, configure it, integrate it
4. If it doesn't exist → check if it's one of the 3 things above
5. If it's not → **ASK the developer before building**

### The Developer's Philosophy
- Solo developer, values self-hosted solutions and cost efficiency
- Prefers to OWN the toolchain but NOT reinvent it
- Glue code > ground-up builds
- Revenue features > infrastructure features
- 15 days of focused work > 308 days of building everything

---

## Tool Stack Summary

```
SELF-HOSTED (Docker Compose):
├── n8n              → Workflow automation
├── Langfuse         → LLM tracing + prompt management
├── Mem0             → AI memory
├── PostgreSQL       → Database (pgvector + Apache AGE)
├── Redis            → Cache + queues
└── Our Services:
    ├── Knowledge Engine (FastAPI)
    ├── Uzhavu API (NestJS)
    ├── Uzhavu Web (Next.js)
    └── Uzhavu AI Engine (FastAPI)

PIP/NPM PACKAGES (used by our code):
├── browser-use      → Browser automation
├── litellm          → LLM routing
├── crewai           → Multi-agent (if needed)
├── promptfoo        → Eval testing
└── playwright       → Browser driver

ALREADY RUNNING:
├── Antigravity      → AI coding assistant (you)
└── LiteLLM proxy    → Model routing
```
