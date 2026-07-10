---
id: 2026-07-05-007
from: hardware-research-chat (7277501b)
to: uzhavu-dev-chat
priority: medium
status: pending
created: 2026-07-05T19:34:00+05:30
claimed_by:
completed:
---

# Build AI Engineering Infrastructure (Eval Harness + LLM Trace Viewer + Prompt Registry + MCP Server)

## Context

Four modules that provide AI engineering infrastructure — systematic testing, observability, prompt management, and interoperability. These make the AI engine production-grade and can be sold as devtool features.

## Specs (all in `.comms/specs/`)

1. **Eval Harness**: `.comms/specs/eval-harness.md`
   - 8 user stories, 4 SQL tables, ~22 days
   - Test suites, model comparison, prompt A/B testing, LLM-as-judge, regression detection

2. **LLM Trace Viewer**: `.comms/specs/llm-trace-viewer.md`
   - 10 user stories, 4 SQL tables, ~27 days
   - Auto-tracing, waterfall view, cost dashboard, latency/token analysis, live stream, alerts

3. **Prompt Registry**: `.comms/specs/prompt-registry.md`
   - 8 user stories, 7 SQL tables, ~26 days
   - Version control, A/B testing, environment promotion, template variables, analytics

4. **MCP Tool Server**: `.comms/specs/mcp-tool-server.md`
   - 8 user stories, 5 SQL tables, ~28 days
   - MCP protocol, tool discovery, custom tool builder, rate limiting, remote hosting

## Recommended Build Order
1. LLM Trace Viewer first (provides observability for everything else)
2. Prompt Registry second (loads prompts from DB, enables versioning)
3. Eval Harness third (uses traces + prompts for systematic testing)
4. MCP Tool Server fourth (exposes tools externally)

## Key Files to Read First
1. The spec files above
2. `\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race\APP_ARCHITECTURE.md`
3. `\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race\.agents\AGENTS.md`
4. AI engine code at `\\RACE\Race - D - Com\DevTools\Projects\uzhavu.race\apps\ai-engine\app\`

## Acceptance Criteria
- [ ] All SQL tables created and migrated
- [ ] NestJS modules + FastAPI middleware for each
- [ ] Frontend dashboards with charts and visualizations
- [ ] Multi-tenant scoping on all queries
- [ ] Plan-based gating working
- [ ] Integration between modules (traces ↔ evals, prompts ↔ AI engine)
- [ ] Tests passing, `pnpm build` passes

## Output
Write completion report to `.comms/outbox/2026-07-05-007-ai-engineering-done.md`
