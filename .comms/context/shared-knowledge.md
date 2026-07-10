# Shared Context — All Agents Read This

> Last updated: 2026-07-06 (12:42 IST)
> Updated by: Strategic Decision Session (7277501b)

## 🚨 READ FIRST: Strategic Decision

**Read `strategic-decision.md` in this directory BEFORE building anything.**

Key rule: **DO NOT build what exists as open-source.** pip install it, docker run it, wire it together. Only build 3 things from scratch:
1. **Knowledge Engine** — personal AI advisor (unique, nothing like it exists)
2. **Product Factory frontend** — revenue generation (our codebase)
3. **Integration layer** — glue between existing tools

The 18 specs in `.comms/specs/` are a REFERENCE LIBRARY, not a build queue. Build from them only when a paying customer needs the feature.

---

## ⚠️ ALSO READ: Platform Audit

**Read `uzhavu-audit.md` in this directory before doing ANY work.**

It contains a full inventory of everything already built — 110 Prisma models, 62 API modules, 79 dashboard pages. Many features you might think need building **already exist**.

---

## Active Projects

### 1. Life Graph (`d:\DevTools\Projects\agents`)
- **Status**: Architecture designed, core code exists, building agent layer
- **Tech**: Python, FastAPI, PostgreSQL + pgvector + Apache AGE, CrewAI, LiteLLM
- **Key docs**: `KNOWLEDGE.md`, `docs/design/`
- **Current focus**: AI colleague team (multi-agent system)

### 2. Uzhavu (`\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race`)
- **Status**: Production-ready SaaS platform, AI engine built
- **Tech**: Next.js 16 + NestJS 11 + FastAPI (AI) + PostgreSQL + Redis + BullMQ
- **Scale**: ~110 models, 62 API modules, 79 pages, 77 UI components, 19 themes
- **Domains**: Business SaaS + School Management + Community/Social + AI Assistant + 22 Dev Tools
- **Key docs**: `APP_ARCHITECTURE.md`, `ARCHITECTURE.md`, `AGENTS.md`
- **Current focus**: Product factory, WhatsApp, Razorpay, PWA, AI engineering tools

---

## What's Already Built (DON'T REBUILD)

### Business SaaS (15 features — ALL DONE)
Contacts, Products, Orders, Invoicing, Payments, Expenses, Appointments, Files, RBAC, Billing/Plans, Webhooks, Feedback, Audit Logs, Calendar, Notifications

### School Management (17 features — ALL DONE)
Students, Fees, Attendance, Exams, Timetable, Hostel, Transport, Library, Report Cards, Staff, Homework, Classes, Promotion, Transfer Certificates, Parent Portal, School Events, Academic Years

### Community/Social (12 features — ALL DONE)
Posts, Likes (6 types), Comments, Polls, Groups, Follow, Block, Moderation, Saved Posts, Directory, Notifications, Feeds

### AI Engine (15 features — ALL DONE)
Chat (SSE), Conversations (persistent), Voice (STT+TTS), RAG/Knowledge Base, User Preferences, Agent Actions, Custom Personas, Usage Tracking, Prompt Templates, Sharing, Web Search, Gmail, Calendar, Calculator, Life Graph integration

### Dev Services (22 tools — ALL DONE)
Error Tracking, API Analytics, Health, Feature Flags, Webhooks, Jobs, Tenant Admin, DB Studio, Audit, Performance, **Status Page, Uptime Monitor, Log Explorer, Cron Manager, Env Manager, Feedback Widget, API Keys, Release Notes**, Notification Center, Dev Projects, Deployments (partial), Canary Tests (partial)

### Product Factory — PARTIALLY DONE
- ✅ `SaasProduct` Prisma model (slug, domain, aliasDomains, apps[], branding, plans JSON, features, marketing)
- ✅ `saas-products` NestJS module (CRUD)
- ❌ Domain routing middleware (not built)
- ❌ Frontend product filtering/branding (not built)

---

## What GENUINELY Needs Building

| Feature | Spec File | Priority |
|:--------|:----------|:---------|
| Product Factory — frontend layer only | `product-factory-implementation.md` | 🔴 High |
| WhatsApp Bot | `whatsapp-bot.md` | 🔴 High |
| Razorpay deep integration | `razorpay-upi.md` | 🔴 High |
| PWA (installable, offline, push) | `pwa-mobile.md` | 🟡 Medium |
| Natural Language Queries | `natural-language-queries.md` | 🟡 Medium |
| Template Gallery | `template-gallery.md` | 🟡 Medium |
| Eval Harness | `eval-harness.md` | 🟡 Medium |
| LLM Trace Viewer | `llm-trace-viewer.md` | 🟡 Medium |
| Prompt Registry | `prompt-registry.md` | 🟢 Low |
| MCP Tool Server | `mcp-tool-server.md` | 🟢 Low |
| Personal AI Agent System | `agent-system-spec.md` | 🟡 Medium |
| Platform Extensions (7 features) | `platform-extensions.md` | 🟢 Low |

---

## Developer Preferences

- Solo developer (Race Raja), based in Coimbatore, India
- OS: Windows 11 ARM (Snapdragon X, 16GB RAM)
- Values: self-hosted, cost-efficient, no vendor lock-in
- Backend: Python (FastAPI) preferred
- Frontend: Next.js
- Database: PostgreSQL for everything (pgvector for embeddings)
- LLM strategy: LiteLLM routing — cheap models for bulk, expensive for reasoning
- Local models: Phi-4 Mini 3.8B, Qwen2.5-Coder 7B (limited by 16GB RAM)
- Minimize LLM dependency: 85% rule-based/local, 15% API calls

## Hardware

- Current: ASUS Vivobook S 16, Snapdragon X (X126100), 16GB RAM, 477GB storage
- No discrete GPU — relies on CPU inference for local models
- Future: PC build with RTX 4070 Ti Super (16GB) → upgrade to RTX 5080 Super (24GB) in ~6 months

## Key Decisions

- PostgreSQL is the ONLY database — not ChromaDB, not SQLite, not MongoDB
- No hardcoded enums — schema-less core with dynamic tags
- Protocol-based interfaces — backends are swappable
- LLM as advisor, not authority — rule-based fallbacks for everything
- Plugin-first architecture — event bus, extensions
- Fork OpenHands + add CrewAI multi-agent + Life Graph memory

## All Specs & Docs (in `.comms/specs/`)

| Doc | File | Purpose |
|:----|:-----|:--------|
| Product Factory | `product-factory-implementation.md` | Domain-based standalone app system |
| AI Engine Improvements | `ai-engine-improvements.md` | 15 prioritized improvements |
| DevTools Modules | `devtools-modules-spec.md` | ⚠️ ALREADY BUILT — use for reference only |
| WhatsApp Bot | `whatsapp-bot.md` | WhatsApp Business API integration |
| Razorpay UPI | `razorpay-upi.md` | Payment collection + reconciliation |
| PWA Mobile | `pwa-mobile.md` | Progressive Web App conversion |
| NL Queries | `natural-language-queries.md` | Natural language to SQL |
| Template Gallery | `template-gallery.md` | Pre-built business configurations |
| Eval Harness | `eval-harness.md` | AI testing & evaluation framework |
| LLM Trace Viewer | `llm-trace-viewer.md` | AI observability & cost tracking |
| Prompt Registry | `prompt-registry.md` | Prompt versioning & A/B testing |
| MCP Tool Server | `mcp-tool-server.md` | Model Context Protocol interop |
| **Agent Handbook** | **`agent-engineering-handbook.md`** | **⭐ Patterns from 8 OSS repos — READ THIS for agent building** |
| **AI Engineering Tools** | **`ai-engineering-tools.md`** | **⭐ 5-feature spec: Local Models, Cost Dashboard, Prompt Testing, Knowledge Graph, Agent Memory** |
| **Agent System** | **`agent-system-spec.md`** | **⭐ Core spec: 8 agents + orchestrator, memory, tools, LiteLLM routing** |
| **Platform Extensions** | **`platform-extensions.md`** | **7 features: Marketplace, Voice, Testing, Docs, Client AI, Plugins, Workflows** |
| **Revenue & Growth** | **`revenue-growth.md`** | **6 features: App Launcher, Billing, Onboarding, i18n, Import/Export, Public API** |
| **DevOps Infrastructure** | **`devops-infrastructure.md`** | **5 features: CI/CD, Docker, Backups, Monitoring, SSL/Domains** |
| **Personal Tools** | **`personal-tools.md`** | **3 features: Dashboard, Project Manager, Research Manager** |

## Context Files

| File | Purpose |
|:-----|:--------|
| `shared-knowledge.md` | This file — start here |
| **`strategic-decision.md`** | **🚨 Don't reinvent the wheel — what to build vs install** |
| `uzhavu-audit.md` | Full platform inventory (110 models, 62 modules, 79 pages) |
