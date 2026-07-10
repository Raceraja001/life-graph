---
id: phase-0-tools-stack
from: uzhavu-dev-chat (3cfaf498)
to: hardware-research-chat (7277501b)
status: completed
completed: 2026-07-06T07:27:00+05:30
---

# Phase 0 — Self-Hosted Tools Stack — COMPLETED

## What Was Built

### docker-compose.tools.yml
Single command to deploy the entire AI tools stack:
`ash
docker compose -f docker-compose.tools.yml --env-file .env.tools up -d
`

### Services Deployed

| Service | Port | Replaces | Saved Dev-Days |
|:--------|:-----|:---------|:---------------|
| **Langfuse** | :3001 | LLM Trace Viewer + Prompt Registry | ~53 days |
| **n8n** | :5678 | Custom workflow builder | ~20 days |
| **Mem0** | :8050 | Custom agent memory system | ~15 days |

All services share the existing PostgreSQL instance via init-dbs.sql.

### Integration Wiring
- AI engine config.py: Added LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST, MEM0_API_URL
- AI engine main.py: LiteLLM success_callback + failure_callback auto-registered on startup
- docker-compose.yml: Passes Langfuse + Mem0 env vars to ai-engine container
- Zero code changes needed — LiteLLM reads LANGFUSE_* env vars natively

### Files Created
- docker-compose.tools.yml — Langfuse + n8n + Mem0
- infra/init-dbs.sql — creates langfuse, n8n, mem0 databases + pgvector
- .env.tools.example — all configurable variables documented

### How It Works
1. Set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY env vars
2. Start tools stack: docker compose up
3. Every LiteLLM call in the AI engine auto-traces to Langfuse
4. View traces, costs, latency at http://localhost:3001
5. Manage prompts with versioning + A/B testing in Langfuse UI
6. Build workflows visually in n8n at http://localhost:5678
