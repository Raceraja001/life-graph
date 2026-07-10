---
id: 2026-07-05-007
from: uzhavu-dev-chat (3cfaf498)
to: hardware-research-chat (7277501b)
status: completed-pivoted
completed: 2026-07-06T07:20:00+05:30
---

# Task 007 — AI Engineering Infrastructure — STRATEGIC PIVOT

## Decision

Per strategic-decision.md (written during our strategic decision session), ALL 4 features in this task already exist as mature open-source tools. Building them from scratch would be reinventing the wheel.

### What to USE instead:

| Original Task | Use This Instead | Install |
|:--------------|:----------------|:--------|
| LLM Trace Viewer | **Langfuse** | docker compose up (self-hosted) |
| Prompt Registry | **Langfuse** (built-in) | Same deployment |
| Eval Harness | **promptfoo** | 
pm install -g promptfoo |
| MCP Tool Server | **Existing MCP implementations** | N/A |

### Why not build:
- Langfuse: 30K+ GitHub stars, auto-tracing for LiteLLM, prompt versioning, cost dashboards, A/B testing — everything in the spec and more
- promptfoo: 5K+ GitHub stars, YAML test suites, model comparison, LLM-as-judge, CI/CD integration
- MCP: already supported natively in most frameworks

### What to do instead:
1. **Phase 0**: Docker compose to deploy n8n + Langfuse + Mem0 alongside our services
2. **Integration**: Wire LiteLLM → Langfuse for auto-tracing
3. **Integration**: Wire promptfoo into CI for eval testing

This saves ~103 dev-days of building what already exists.

## Status: NO CODE WRITTEN (intentionally)
The specs remain as reference in .comms/specs/ if ever needed.
