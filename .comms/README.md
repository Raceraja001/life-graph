# Inter-Agent Communication Protocol

> This directory enables structured communication between multiple Antigravity instances working on the same project.

## How It Works

```
Instance A (Chat 1)                    Instance B (Chat 2)
       │                                      │
       ├── writes task to inbox/ ──────→ reads task
       │                                      │
       │                              implements task
       │                                      │
       └── reads result ←────────── writes to outbox/
```

## Directory Structure

```
.comms/
├── README.md          ← You're reading this
├── inbox/             ← Pending tasks for any agent to pick up
├── outbox/            ← Completed task reports
├── context/           ← Shared knowledge accessible to all agents
└── active/            ← Tasks currently being worked on (claimed)
```

## Message Format

Every message file uses this format:

```markdown
---
id: YYYY-MM-DD-NNN
from: <source-chat-description>
to: <target-chat-description or "any">
priority: low | medium | high | critical
status: pending | claimed | in-progress | done | blocked
created: ISO-8601 timestamp
claimed_by: <conversation-id> (filled when claimed)
completed: ISO-8601 timestamp (filled when done)
---

# Task Title

## Context
Brief background and links to relevant docs.

## Instructions
Step-by-step what needs to be done.

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Output
Where to write results (outbox file, code changes, etc.)
```

## Rules

1. **Claiming tasks**: Before starting work, move the file from `inbox/` to `active/` and set `status: claimed`
2. **Completing tasks**: When done, move from `active/` to `outbox/` and set `status: done`
3. **File naming**: `YYYY-MM-DD-NNN-<short-slug>.md` (e.g., `2026-07-05-001-product-factory.md`)
4. **One task per file**: Don't combine multiple tasks
5. **Always link sources**: Reference docs, files, or conversation IDs for context
6. **Context files**: Shared knowledge goes in `context/` — any agent can read/update these
