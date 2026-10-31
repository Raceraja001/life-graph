<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Produced by scripts/gen_state.py. Run `python scripts/gen_state.py`
     to refresh. Intent and rationale live in CHARTER.md, not here. -->

# Life Graph — State

> **What exists right now.** Generated from the code by `scripts/gen_state.py`.
>
> This file deliberately contains **no rationale** — for why any of it exists, read [CHARTER.md](../CHARTER.md).

Generated `2026-10-31 16:26 UTC` from `master` @ `6760a25`

---

## At a glance

| | |
|---|---|
| HTTP operations | **65** across 56 paths, 14 tags |
| Database tables | **68** |
| Migrations | **56** (head: `056_study_upgrade`) |
| Event types | **79** |
| Built-in personas | **13** |
| Agent tools | **14** |
| Scheduled jobs | **34** |
| Config settings | **277** (prefix `LIFE_GRAPH_`) |
| Test functions | **3986** in 460 files |
| Dashboard pages | **22** |
| Python | 448 files, 115,582 lines |

---

## HTTP API

65 operations, grouped by OpenAPI tag.

### `memories` — 13

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/memories/` | List memories with optional filters |
| POST | `/api/v1/memories/` | Create memories from text or structured input |
| POST | `/api/v1/memories/approvals/bulk` | Approve/reject memories in batch |
| POST | `/api/v1/memories/batch` | Expand memory ids to full memories (progressive-disclosure step 2) |
| GET | `/api/v1/memories/pending/count` | Count memories awaiting approval |
| DELETE | `/api/v1/memories/{memory_id}` | Delete a memory |
| GET | `/api/v1/memories/{memory_id}` | Get a memory by ID |
| PATCH | `/api/v1/memories/{memory_id}` | Update a memory |
| POST | `/api/v1/memories/{memory_id}/approve` | Approve a memory |
| POST | `/api/v1/memories/{memory_id}/deny` | Deny a memory — mark as no longer accurate |
| POST | `/api/v1/memories/{memory_id}/reinforce` | Reinforce a memory — confirm it is still accurate |
| POST | `/api/v1/memories/{memory_id}/reject` | Reject a memory |
| POST | `/api/v1/memories/{memory_id}/unarchive` | Unarchive a memory |

### `memory-page` — 6

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/memories/overview` | What Jarvis knows: review queue, form, notes, older memories |
| POST | `/api/v1/memories/{memory_id}/archive` | Archive a memory (kept, shown under older memories) |
| GET | `/api/v1/memories/{memory_id}/connections` | One memory's links, history and mentions |
| POST | `/api/v1/memories/{memory_id}/correct` | Correct a memory: the old one is kept as history |
| POST | `/api/v1/memories/{memory_id}/drop` | Drop a memory: reject if pending, take back if active |
| POST | `/api/v1/memories/{memory_id}/restore` | Bring an archived memory back into use |

### `preferences` — 6

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/preferences/` | List preferences with filters |
| POST | `/api/v1/preferences/` | Create a preference |
| POST | `/api/v1/preferences/search` | Semantic preference search |
| DELETE | `/api/v1/preferences/{preference_id}` | Soft-delete a preference |
| GET | `/api/v1/preferences/{preference_id}` | Get a preference by ID |
| PATCH | `/api/v1/preferences/{preference_id}` | Update a preference |

### `(untagged)` — 5

| Method | Path | Summary |
|---|---|---|
| GET | `/` | Root |
| GET | `/health` | Health Check |
| GET | `/live` | Liveness |
| GET | `/metrics` | Metrics |
| GET | `/ready` | Readiness |

### `capture-spine` — 5

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/capture/` | List capture events |
| POST | `/api/v1/capture/` | Ingest a capture event |
| POST | `/api/v1/capture/correction` | Record a correction |
| GET | `/api/v1/capture/corrections` | List corrections |
| GET | `/api/v1/capture/corrections/export` | Export correction triples as NDJSON |

### `graph` — 5

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/graph/entities` | List all graph entities |
| GET | `/api/v1/graph/entity/{name}` | Get entity detail with neighbors |
| GET | `/api/v1/graph/path` | Find path between two entities |
| POST | `/api/v1/graph/query` | Execute a Cypher query |
| POST | `/api/v1/graph/search` | Hybrid graph + vector search |

### `intentions` — 5

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/intentions/` | List pending intentions |
| POST | `/api/v1/intentions/` | Create a new intention |
| POST | `/api/v1/intentions/triggered` | Get currently triggered intentions |
| PATCH | `/api/v1/intentions/{intention_id}/complete` | Mark an intention as completed |
| PATCH | `/api/v1/intentions/{intention_id}/dismiss` | Dismiss an intention |

### `sessions` — 5

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/sessions/` | List recent sessions |
| POST | `/api/v1/sessions/start` | Start a new session |
| GET | `/api/v1/sessions/{session_id}` | Get a session by ID |
| POST | `/api/v1/sessions/{session_id}/end` | End a session |
| POST | `/api/v1/sessions/{session_id}/heartbeat` | Update session context mid-conversation |

### `identity` — 4

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/identity/beliefs` | Get active beliefs |
| POST | `/api/v1/identity/challenge` | Challenge a belief |
| GET | `/api/v1/identity/stale` | Find stale beliefs |
| GET | `/api/v1/identity/timeline` | Get identity timeline |

### `memory-links` — 4

| Method | Path | Summary |
|---|---|---|
| DELETE | `/api/v1/memories/links/{link_id}` | Delete a memory link |
| GET | `/api/v1/memories/{memory_id}/linked` | Get linked memories (context expansion) |
| GET | `/api/v1/memories/{memory_id}/links` | List links for a memory |
| POST | `/api/v1/memories/{memory_id}/links` | Create a link between two memories |

### `search` — 4

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/search/` | Search across memories (vector, hybrid, or tri-hybrid) |
| POST | `/api/v1/search/ask` | Ask a question — get a synthesized answer from memories |
| POST | `/api/v1/search/recall` | Proactive recall at session start |
| POST | `/api/v1/search/recall/event` | Mid-session event-driven recall |

### `health` — 1

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/health/memory` | Is the memory engine able to store and find memories? |

### `ingest` — 1

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/ingest/external-transcript` | Ingest External Transcript |

### `transcript` — 1

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/ingest/transcript` | Ingest a chat transcript and extract preferences |

---

## Database tables

68 tables. **Tenant** marks a `tenant_id` column — the multi-tenancy invariant requires every query to filter on it.

| Table | Columns | Tenant | Created by |
|---|---:|:---:|---|
| `action_safety_rules` | 18 | ✓ | `018_autonomous_ai` |
| `advisor_sessions` | 13 | ✓ | `014_personal_ai` |
| `agent_messages` | 18 | ✓ | `017_agent_networks` |
| `agent_personas` | 23 | ✓ | `—` |
| `agent_run_steps` | 12 | ✓ | `044_agent_run_steps` |
| `agent_sessions` | 15 | ✓ | `—` |
| `agent_tasks` | 40 | ✓ | `—` |
| `approval_queue` | 25 | ✓ | `018_autonomous_ai` |
| `approvals` | 15 | ✓ | `026_approvals` |
| `audit_log` | 22 | ✓ | `018_autonomous_ai` |
| `auto_actions` | 31 | ✓ | `018_autonomous_ai` |
| `autonomy_levels` | 28 | ✓ | `018_autonomous_ai` |
| `budget_spend` | 6 | ✓ | `023_budget_spend` |
| `conversation_messages` | 8 | ✓ | `027_conversations` |
| `conversations` | 6 | ✓ | `027_conversations` |
| `cross_system_syncs` | 20 | ✓ | `017_agent_networks` |
| `eval_cases` | 10 | — | `015_self_improving` |
| `eval_results` | 14 | — | `015_self_improving` |
| `eval_runs` | 18 | — | `015_self_improving` |
| `eval_suites` | 14 | ✓ | `015_self_improving` |
| `evidence` | 16 | ✓ | `014_personal_ai` |
| `external_sessions` | 11 | ✓ | `030_external_sessions` |
| `extraction_traces` | 10 | ✓ | `038_extraction_traces` |
| `intentions` | 16 | ✓ | `001_initial_schema` |
| `job_runs` | 10 | ✓ | `003_multi_tenancy` |
| `knowledge_gaps` | 9 | ✓ | `001_initial_schema` |
| `life_graph.calibration_snapshots` | 11 | ✓ | `—` |
| `life_graph.capture_events` | 12 | ✓ | `—` |
| `life_graph.challenges` | 9 | ✓ | `—` |
| `life_graph.corrections` | 10 | ✓ | `—` |
| `life_graph.decisions` | 19 | ✓ | `—` |
| `life_graph.driver_stats` | 10 | ✓ | `—` |
| `life_graph.interview_questions` | 12 | ✓ | `—` |
| `life_graph.predictions` | 15 | ✓ | `—` |
| `life_graph.verification_runs` | 7 | ✓ | `—` |
| `memories` | 34 | ✓ | `001_initial_schema` |
| `memory_links` | 8 | ✓ | `—` |
| `memory_sessions` | 5 | — | `001_initial_schema` |
| `nightly_run_log` | 15 | ✓ | `015_self_improving` |
| `notification_channels` | 9 | ✓ | `016_ambient_ai` |
| `notifications` | 14 | ✓ | `013_projects_notifications` |
| `optimization_runs` | 28 | ✓ | `015_self_improving` |
| `preferences` | 21 | ✓ | `014_personal_ai` |
| `procedures` | 14 | ✓ | `—` |
| `projects` | 18 | ✓ | `013_projects_notifications` |
| `prompt_versions` | 14 | ✓ | `015_self_improving` |
| `push_subscriptions` | 8 | ✓ | `028_push_subscriptions` |
| `research_runs` | 12 | ✓ | `014_personal_ai` |
| `scheduled_jobs` | 19 | ✓ | `012_scheduled_jobs` |
| `sessions` | 10 | ✓ | `001_initial_schema` |
| `shadow_enrollments` | 9 | ✓ | `024_shadow_mode` |
| `shadow_runs` | 14 | ✓ | `024_shadow_mode` |
| `shared_context` | 17 | ✓ | `017_agent_networks` |
| `tech_radar` | 13 | ✓ | `016_ambient_ai` |
| `telegram_bindings` | 9 | ✓ | `037_telegram_bridge` |
| `telegram_pairing_codes` | 5 | ✓ | `037_telegram_bridge` |
| `tenant_configs` | 8 | ✓ | `004_webhooks_tenants_dedup` |
| `tenant_usage` | 7 | ✓ | `003_multi_tenancy` |
| `tenant_webhooks` | 9 | ✓ | `004_webhooks_tenants_dedup` |
| `trust_scores` | 22 | ✓ | `018_autonomous_ai` |
| `watch_configs` | 13 | ✓ | `016_ambient_ai` |
| `watch_events` | 11 | ✓ | `016_ambient_ai` |
| `watcher_notifications` | 15 | ✓ | `016_ambient_ai` |
| `watcher_runs` | 11 | ✓ | `016_ambient_ai` |
| `workflow_runs` | 12 | ✓ | `017_agent_networks` |
| `workflow_step_runs` | 13 | — | `017_agent_networks` |
| `workflow_steps` | 16 | — | `017_agent_networks` |
| `workflows` | 11 | ✓ | `017_agent_networks` |

---

## Events

79 event types on the async EventBus.

**Task** (13) — `agent:task:cancelled` · `agent:task:child_failed` · `agent:task:children_complete` · `agent:task:completed` · `agent:task:delegated` · `agent:task:failed` · `agent:task:handoff` · `driver:task:bounced` · `kernel:task:cancelled` · `kernel:task:completed` · `kernel:task:failed` · `kernel:task:spawned` · `kernel:task:timeout`

**Memory** (7) — `memory:approved` · `memory:created` · `memory:deleted` · `memory:pending` · `memory:rejected` · `memory:retrieved` · `memory:updated`

**Decision** (4) — `capture:decision:candidate` · `judgment:decision:challenged` · `judgment:decision:recorded` · `judgment:decision:superseded`

**Workflow** (4) — `agent:workflow:completed` · `agent:workflow:failed` · `agent:workflow:started` · `agent:workflow:step_completed`

**Approval** (3) — `approval:requested` · `approval:resolved` · `driver:approval:filed`

**Driver** (3) — `driver:dispatched` · `driver:result` · `driver:steps`

**Preference** (3) — `preference:challenged` · `preference:created` · `preference:updated`

**Autonomous** (2) — `autonomy:action:completed` · `autonomy:action:pending`

**Conversation** (2) — `conversation:distilled` · `conversation:message`

**Interview** (2) — `capture:interview:answered` · `capture:interview:asked`

**Message** (2) — `agent:message:read` · `agent:message:sent`

**Prediction** (2) — `judgment:prediction:created` · `judgment:prediction:resolved`

**Project** (2) — `kernel:project:registered` · `kernel:project:scanned`

**Schedule** (2) — `kernel:schedule:disabled` · `kernel:schedule:fired`

**Session** (2) — `session:end` · `session:start`

**Shadow** (2) — `autonomy:shadow:graduated` · `autonomy:shadow:recorded`

**Sync** (2) — `agent:sync:completed` · `agent:sync:failed`

**Verification** (2) — `driver:verification:failed` · `driver:verification:passed`

**Watcher** (2) — `watcher:completed` · `watcher:failed`

**Bias** (1) — `judgment:bias:detected`

**Brief** (1) — `capture:brief:composed`

**Calibration** (1) — `judgment:calibration:updated`

**Capture** (1) — `capture:received`

**Context** (1) — `agent:context:shared`

**Contradiction** (1) — `contradiction:detected`

**Correction** (1) — `capture:correction:recorded`

**Document** (1) — `document:imported`

**Evidence** (1) — `evidence:added`

**Image** (1) — `image:processed`

**Intention** (1) — `intention:triggered`

**Notification** (1) — `kernel:notification:created`

**Pipeline** (1) — `driver:pipeline:task_originated`

**Procedure** (1) — `capture:procedure:candidate`

**Research** (1) — `research:completed`

**Second** (1) — `driver:second_opinion:dissent`

**Transcript** (1) — `transcript:distilled`

**Voice** (1) — `voice:transcribed`

---

## Built-in personas

13 active personas seeded at startup, plus 7 retired (seeded switched off; docs/design/11_persona_roster_plan.md).

| Persona | Driver | Task types | Verifiers | Tools |
|---|---|---|---|---:|
| ~~chief~~ (retired) — Classifies user intent and routes to the best specialist agent. | `—` | — | — | 0 |
| **cody** — Writes, reviews, debugs, and refactors code. | `—` | — | — | 7 |
| ~~rex~~ (retired) — Researches topics, answers questions, and synthesizes information. | `—` | — | — | 2 |
| **ops** — Manages deployments, infrastructure, and monitoring. | `—` | — | — | 1 |
| ~~penny~~ (retired) — Analyzes data, queries databases, and builds analytics. | `—` | — | — | 3 |
| ~~scribe~~ (retired) — Writes and maintains documentation, READMEs, and guides. | `—` | — | — | 3 |
| ~~uzhavu-ops~~ (retired) — Operates the Uzhavu platform — deploy checks, incident diagnosis, and fixes. | `claude_code` | `deploy_check`, `incident_fix` | `build_ok_diff`, `tests_pass` | 6 |
| **dependency-updater** — Turns dependency-watcher findings into safe upgrade PRs, running project tests before landing. | `claude_code` | `dependency_update` | `tests_pass`, `diff_within_scope` | 7 |
| **code-fixer** — Makes small, focused code changes in a registered project. File tools only — no shell — and every change is verified and offered as a PR for approval. | `claude_code` | `code_change` | `build_ok_diff`, `lint_clean_diff` | 2 |
| **code-fixer-local** — Code Fixer on a local model: the code never leaves the machine. Set its model to a local model that fits the GPU: ollama_chat/gpt-oss:20b scored best on the driver benchmark (evals/driver_bench/README.md). Same verification and PR approval as Code Fixer. | `local` | `code_change` | `build_ok_diff`, `lint_clean_diff`, `diff_within_scope`, `tests_exercise_code` | 5 |
| **code-fixer-opencode** — Code Fixer on OpenCode, an open-source coding agent, with a local model: the code never leaves the machine. An alternative engine to code-fixer-local; compare them on the Agent scorecards. | `opencode` | `code_change` | `build_ok_diff`, `lint_clean_diff`, `diff_within_scope`, `tests_exercise_code` | 5 |
| **code-fixer-cloud** — Code Fixer on a free cloud model, for queued work while the GPU is busy with speech (services/compute_router.py). The code leaves the machine; personal context does not. Free models only, never paid. Its model is the first of dev_cloud_models; change it here. | `cloud` | `code_change` | `build_ok_diff`, `lint_clean_diff`, `diff_within_scope`, `tests_exercise_code` | 5 |
| **code-fixer-auto** — Code Fixer that picks its driver per project from the record of merged vs rejected PRs: the free local model unless its work on that project keeps getting rejected, then Claude Code. | `auto` | `code_change` | `build_ok_diff`, `lint_clean_diff`, `diff_within_scope`, `tests_exercise_code` | 4 |
| **tutor** — Tracks what you're learning, guides you, and checks understanding. | `—` | — | — | 3 |
| **scout** — Ambiently researches topics useful to the user and surfaces findings. | `—` | — | — | 4 |
| **admin** — Surfaces work/life admin items (bills, follow-ups, meeting prep) for review. | `—` | — | — | 13 |
| ~~assistant~~ (retired) — Answers the user's everyday questions from their own data and the web. | `—` | — | — | 20 |
| **support-desk** — Answers customer questions about one of the user's apps from its docs. | `—` | — | — | 3 |
| ~~swe-lead~~ (retired) — Coordinates cody/ops/rex on engineering work that needs more than one specialist. | `—` | — | `tests_pass`, `diff_within_scope` | 6 |
| **jarvis** — The user's assistant and the lead: the one persona the user talks to. | `—` | — | — | 33 |

---

## Agent tools

14 tools registered via the `@tool` decorator.

| Tool | Description |
|---|---|
| `browse_web` | Browse a web page and extract its text content. Use for: reading documentation, checking release notes, scraping articles, checking GitHub repos. Returns the page text content (no JavaScript execution). Private and local network addresses cannot be fetched. |
| `calculator` | Evaluate a mathematical expression safely |
| `delegate_to_persona` | Delegate a sub-task to another persona and get their result back. Use this when part of the request is better handled by a specialist persona than by you. |
| `file_read` | Read the contents of a file on the host system. Provide an absolute path. Returns the file's text content, truncated if very large. |
| `file_write` | Write text content to a file on the host system, creating it (and parent directories) if needed, or overwriting it if it already exists. Provide an absolute path. |
| `get_current_datetime` | Get the current date, time, and timezone information |
| `git_branch` | List branches or get current branch name. |
| `git_diff` | Show changes in the working directory or between commits. Without arguments, shows unstaged changes. |
| `git_log` | Get recent git commit history. Returns commit hash, author, date, and message for the last N commits. |
| `git_status` | Get the current git status of a repository. Shows modified, staged, and untracked files. |
| `inspect_system` | Read-only system inspection. `check` must be one of: disk, docker_logs, docker_ps, git_status, memory, systemctl_status, uptime. Optional `target` names a container/service where relevant. Cannot modify anything. |
| `research_web` | Research a question on the web: reads several result pages and returns an answer in short claims, each citing the pages that state it. Slower than web_search; use it for questions that need more than one page (comparisons, 'what is the latest on'). Do not put personal details in the question. |
| `run_command` | Execute a shell command on the host system and return the output. Use for: checking system status, running scripts, git operations, docker commands, file listing, etc. Commands time out after 30 seconds. DANGEROUS: Only use when explicitly asked by the user. |
| `web_search` | Search the web for current information. Returns titles, URLs and snippets; cite the URLs you rely on. |

---

## Scheduled jobs

34 ARQ cron jobs (times are UTC).

| Job | Schedule | Function |
|---|---|---|
| `check_approval_timeouts` | every 5 min | `life_graph.workers.tasks.check_approval_timeouts` |
| `close_claude_code_sessions` | hourly at :04,:14,:24,:34,:44,:54 | `life_graph.workers.claude_code_sessions.close_claude_code_sessions` |
| `decay_trust_scores` | 05:00 | `life_graph.workers.tasks.decay_trust_scores` |
| `distill_idle_conversations` | every 15 min | `life_graph.workers.distill.distill_idle_conversations` |
| `failure_pattern_mining` | 02:30 | `life_graph.workers.tasks.failure_pattern_mining` |
| `purge_connector_items` | 04:40 | `life_graph.workers.tasks.purge_connector_items` |
| `purge_telegram_pairing_codes` | 04:30 | `life_graph.workers.telegram.purge_telegram_pairing_codes` |
| `purge_temporary_chats` | hourly at :27 | `life_graph.workers.temporary_chats.purge_temporary_chats` |
| `run_all_consolidations` | 03:00 | `life_graph.workers.tasks.run_all_consolidations` |
| `run_all_decay_sweeps` | 04:00 | `life_graph.workers.decay.run_all_decay_sweeps` |
| `run_all_form_fills` | 03:20 | `life_graph.workers.form_fill.run_all_form_fills` |
| `run_all_merge_suggestions` | 03:45 | `life_graph.workers.tasks.run_all_merge_suggestions` |
| `run_all_research` | Sun 02:00 | `life_graph.workers.tasks.run_all_research` |
| `run_assistant_daily` | daily at (settings.brief_hour_utc - 1) % 24:30 | `life_graph.workers.tasks.run_assistant_daily` |
| `run_daily_brief` | daily at settings.brief_hour_utc:00 | `life_graph.workers.tasks.run_daily_brief` |
| `run_daily_digest` | 08:00 | `life_graph.workers.tasks.run_daily_digest` |
| `run_llm_catalog_diff` | 21:30 | `life_graph.workers.llm_offers.run_llm_catalog_diff` |
| `run_llm_offer_evals` | hourly at :45 | `life_graph.workers.llm_offers.run_llm_offer_evals` |
| `run_llm_offer_news` | every 6h at :15 | `life_graph.workers.llm_offers.run_llm_offer_news` |
| `run_nightly_calibration` | 04:15 | `life_graph.workers.tasks.run_nightly_calibration` |
| `run_nightly_dev_suggestions` | 21:00 | `life_graph.workers.tasks.run_nightly_dev_suggestions` |
| `run_nightly_self_heal` | 03:30 | `life_graph.workers.tasks.run_nightly_self_heal` |
| `run_tech_watch` | 22:00 | `life_graph.workers.web_research.run_tech_watch` |
| `run_watchers` | hourly at :00 | `life_graph.workers.tasks.run_watchers` |
| `send_approval_escalations` | every 30 min | `life_graph.workers.tasks.send_approval_escalations` |
| `send_memory_check` | daily at (settings.brief_hour_utc - 1) % 24:50 | `life_graph.workers.memory_check.send_memory_check` |
| `send_nudges` | hourly at :12,:42 | `life_graph.workers.nudges.send_nudges` |
| `send_study_nudge` | hourly at :07 | `life_graph.workers.study_nudge.send_study_nudge` |
| `sweep_stuck_captures` | hourly at :07,:22,:37,:52 | `life_graph.workers.capture_sweep.sweep_stuck_captures` |
| `sync_connectors` | every 5 min | `life_graph.workers.tasks.sync_connectors` |
| `sync_dev_task_prs` | every 15 min | `life_graph.workers.tasks.sync_dev_task_prs` |
| `tick_scheduled_jobs` | every minute | `life_graph.workers.tasks.tick_scheduled_jobs` |
| `write_daily_episodes` | hourly at :41 | `life_graph.workers.episodes.write_daily_episodes` |
| `write_due_notifications` | hourly at :04,:19,:34,:49 | `life_graph.workers.due_notifications.write_due_notifications` |

---

## Dashboard

22 pages.

| Route | File |
|---|---|
| `/m/approvals` | `dashboard/app/(mobile)/m/approvals/page.tsx` |
| `/m/chat` | `dashboard/app/(mobile)/m/chat/page.tsx` |
| `/m/memories` | `dashboard/app/(mobile)/m/memories/page.tsx` |
| `/m` | `dashboard/app/(mobile)/m/page.tsx` |
| `/m/personas` | `dashboard/app/(mobile)/m/personas/page.tsx` |
| `/m/schedules` | `dashboard/app/(mobile)/m/schedules/page.tsx` |
| `/m/settings` | `dashboard/app/(mobile)/m/settings/page.tsx` |
| `/m/shadow` | `dashboard/app/(mobile)/m/shadow/page.tsx` |
| `/m/tasks` | `dashboard/app/(mobile)/m/tasks/page.tsx` |
| `/activity` | `dashboard/app/activity/page.tsx` |
| `/agents/failures` | `dashboard/app/agents/failures/page.tsx` |
| `/agents` | `dashboard/app/agents/page.tsx` |
| `/agents/scorecards` | `dashboard/app/agents/scorecards/page.tsx` |
| `/calibration` | `dashboard/app/calibration/page.tsx` |
| `/decisions` | `dashboard/app/decisions/page.tsx` |
| `/drivers/[id]` | `dashboard/app/drivers/[id]/page.tsx` |
| `/drivers` | `dashboard/app/drivers/page.tsx` |
| `/login` | `dashboard/app/login/page.tsx` |
| `/memories` | `dashboard/app/memories/page.tsx` |
| `/` | `dashboard/app/page.tsx` |
| `/settings` | `dashboard/app/settings/page.tsx` |
| `/tasks` | `dashboard/app/tasks/page.tsx` |

---

## Spec status

Each spec in `docs/specs/` checked against the code that would implement it.

| Spec | Status | Evidence |
|---|---|---|
| `agent-condenser` | Unclassified | — |
| `agent-drivers` | Built | `life_graph/drivers/dispatcher.py` |
| `agent-observability` | Unclassified | — |
| `approvals-feed` | Built | `life_graph/api/approvals.py` |
| `assistant-capabilities` | Unclassified | — |
| `autonomous-app-development` | Unclassified | — |
| `bills-from-mail` | Unclassified | — |
| `capture-spine` | Built | `life_graph/services/capture.py` |
| `connector-contacts` | Unclassified | — |
| `connector-github` | Unclassified | — |
| `connector-tasks` | Unclassified | — |
| `connectors` | Unclassified | — |
| `dashboard-pwa` | Built | `dashboard/app/(mobile)/m/page.tsx` |
| `device-access` | Unclassified | — |
| `era4-personal-ai` | Built | `life_graph/api/advisor.py` |
| `era5-self-improving` | Built | `life_graph/self_improving/prompt_resolver.py` |
| `era6-ambient-ai` | Built | `life_graph/watchers/framework.py` |
| `era7-agent-networks` | Built | `life_graph/api/agent_workflows.py` |
| `era8-autonomous-ai` | Built | `life_graph/autonomy/router.py` |
| `era8-autonomy-reconciliation` | Built | `life_graph/autonomy/kill_switch.py` |
| `eval-harness` | Built | `life_graph/self_improving/eval_service.py` |
| `free-llm-offers` | Unclassified | — |
| `judgment-engine` | Built | `life_graph/services/judgment.py` |
| `llm-trace-viewer` | Built | `life_graph/api/model_health.py` |
| `mcp-tool-server` | Built | `life_graph/mcp_server.py` |
| `money-checkin-and-app-health` | Unclassified | — |
| `natural-language-queries` | Built | `life_graph/api/search.py` |
| `night-shift-report` | Unclassified | — |
| `os-kernel` | Built | `life_graph/kernel/process_manager.py` |
| `personal-model-tuning` | Spec'd, not built | — |
| `personal-roles` | Built | `life_graph/kernel/ambient.py` |
| `prompt-registry` | Built | `life_graph/self_improving/prompt_version_service.py` |
| `pwa-mobile` | Built | `dashboard/app/(mobile)/m/page.tsx` |
| `razorpay-upi` | Not this product | — |
| `research-and-tech-watch` | Unclassified | — |
| `telegram-bridge` | Built | `life_graph/api/integrations_telegram.py` |
| `template-gallery` | Not this product | — |
| `web-chat-wave1` | Unclassified | — |
| `whatsapp-bot` | Not this product | — |

---

## Migrations

56 revisions, head `056_study_upgrade`.

`001_initial_schema` · `002_add_age_graph` · `003_multi_tenancy` · `004_webhooks_tenants_dedup` · `005_cold_start_config` · `006_confidence_decay` · `007_bm25_search` · `008_impact_scoring` · `009_memory_links` · `010_procedures` · `011_os_kernel` · `012_scheduled_jobs` · `013_projects_notifications` · `014_personal_ai` · `015_self_improving` · `016_ambient_ai` · `017_agent_networks` · `018_autonomous_ai` · `019_capture_spine` · `020_judgment_engine` · `021_agent_drivers` · `022_trust_tiers` · `023_budget_spend` · `024_shadow_mode` · `025_embedding_dim` · `026_approvals` · `027_conversations` · `028_push_subscriptions` · `029_conversation_last_distilled_at` · `030_external_sessions` · `031_add_kind_instruction_to_autonomy` · `032_autonomy_kill_switch` · `033_widen_evidence_stance` · `034_notification_channel_name` · `035_decay_horizon_six_months` · `036_backfill_memory_trust_tiers` · `037_telegram_bridge` · `038_extraction_traces` · `039_connectors` · `040_connector_contacts` · `041_connector_code` · `042_connector_tasks` · `043_assistant_message_surface` · `044_agent_run_steps` · `045_documents` · `046_money` · `047_page_monitors` · `048_review_cards` · `049_invoices` · `050_llm_offers` · `051_topic_findings` · `052_devices` · `053_entities` · `054_feature_ideas` · `055_feature_idea_worth` · `056_study_upgrade`

---

## Tests

Counts `def test_*` declarations. pytest collects more cases than this — `@pytest.mark.parametrize` expands one function into many.

| Suite | Files | Functions |
|---|---:|---:|
| `tests/unit/` | 347 | 3169 |
| `tests/integration/` | 112 | 805 |
| `tests/ (root)` | 1 | 12 |
| **total** | **460** | **3986** |

---

## Configuration

277 settings, all overridable by environment variable.

| Environment variable | Default |
|---|---|
| `LIFE_GRAPH_APP_NAME` | `'Life Graph'` |
| `LIFE_GRAPH_VERSION` | `'1.0.0'` |
| `LIFE_GRAPH_ENVIRONMENT` | `'development'` |
| `LIFE_GRAPH_DEBUG` | `False` |
| `LIFE_GRAPH_LOG_LEVEL` | `'INFO'` |
| `LIFE_GRAPH_LOG_FORMAT` | `'text'` |
| `LIFE_GRAPH_PROFILE` | `'memory_core'` |
| `LIFE_GRAPH_EDITION` | `''` |
| `LIFE_GRAPH_WORKER_CRON_ENABLED` | `True` |
| `LIFE_GRAPH_API_KEY` | `—` |
| `LIFE_GRAPH_SERVICE_API_KEYS` | `''` |
| `LIFE_GRAPH_DEVICE_TOKEN_IDLE_DAYS` | `60` |
| `LIFE_GRAPH_APP_RELEASE_DIR` | `''` |
| `LIFE_GRAPH_DATABASE_URL` | `'postgresql+asyncpg://life_graph:life_graph@localhost:543…` |
| `LIFE_GRAPH_DATABASE_URL_SYNC` | `'postgresql://life_graph:life_graph@localhost:5432/life_g…` |
| `LIFE_GRAPH_DATABASE_POOL_SIZE` | `10` |
| `LIFE_GRAPH_DATABASE_MAX_OVERFLOW` | `20` |
| `LIFE_GRAPH_REDIS_URL` | `'redis://localhost:6379/0'` |
| `LIFE_GRAPH_GRAPH_ENABLED` | `True` |
| `LIFE_GRAPH_REQUIRE_EMBEDDING_BACKEND` | `True` |
| `LIFE_GRAPH_EMBEDDING_MODEL` | `'BAAI/bge-m3'` |
| `LIFE_GRAPH_EMBEDDING_DIMENSION` | `1024` |
| `LIFE_GRAPH_LLM_MODEL_CHEAP` | `'openrouter/openai/gpt-oss-20b:free'` |
| `LIFE_GRAPH_LLM_MODEL_EXPENSIVE` | `'gemini/gemini-3.6-flash'` |
| `LIFE_GRAPH_LLM_DAILY_BUDGET_USD` | `1.0` |
| `LIFE_GRAPH_RECALL_MAX_SESSION_START` | `5` |
| `LIFE_GRAPH_RECALL_MAX_DURING_SESSION` | `2` |
| `LIFE_GRAPH_RECALL_COOLDOWN_DAYS` | `7` |
| `LIFE_GRAPH_RECALL_CONFIDENCE_THRESHOLD` | `0.7` |
| `LIFE_GRAPH_RECALL_INDEX_CONTENT_CHARS` | `120` |
| `LIFE_GRAPH_MEMORY_BATCH_MAX` | `50` |
| `LIFE_GRAPH_DRIVER_LAND_VERIFIED_WORK` | `True` |
| `LIFE_GRAPH_DECAY_ARCHIVE_THRESHOLD` | `0.01` |
| `LIFE_GRAPH_DECAY_PROPOSAL_LIMIT` | `50` |
| `LIFE_GRAPH_PENDING_MEMORY_EXPIRY_DAYS` | `14` |
| `LIFE_GRAPH_MEMORY_START_AT` | `''` |
| `LIFE_GRAPH_MEMORY_JUDGE_MODEL` | `''` |
| `LIFE_GRAPH_MEMORY_COLD_TIER` | `True` |
| `LIFE_GRAPH_MEMORY_LINKS` | `True` |
| `LIFE_GRAPH_MEMORY_STRENGTH_RANK` | `False` |
| `LIFE_GRAPH_MEMORY_FORM_FILL` | `True` |
| `LIFE_GRAPH_PROFILE_CARD_MAX_ITEMS` | `40` |
| `LIFE_GRAPH_DECAY_DEFAULT_LAMBDA` | `0.1` |
| `LIFE_GRAPH_DEDUP_ENABLED` | `True` |
| `LIFE_GRAPH_DEDUP_THRESHOLD` | `0.92` |
| `LIFE_GRAPH_CONTRADICTION_SIMILARITY_THRESHOLD` | `0.75` |
| `LIFE_GRAPH_MERGE_REVIEW_LOW` | `0.85` |
| `LIFE_GRAPH_MERGE_SUGGEST_SCAN_LIMIT` | `200` |
| `LIFE_GRAPH_CAPTURE_LLM_CLEAN` | `True` |
| `LIFE_GRAPH_EXTRACTION_LANGUAGE_GUARD` | `True` |
| `LIFE_GRAPH_EXTRACTION_TAG_ONLY_ENTITIES` | `True` |
| `LIFE_GRAPH_EXTRACTION_MIN_CONFIDENCE` | `0.45` |
| `LIFE_GRAPH_EXTRACTION_LLM_MIN_WORDS` | `20` |
| `LIFE_GRAPH_EXTRACTION_LLM_CONFIDENCE_THRESHOLD` | `0.5` |
| `LIFE_GRAPH_CAPTURE_NO_EXTRACT_SURFACES` | `'tool_exhaust,assistant_message'` |
| `LIFE_GRAPH_CAPTURE_SAVED_BY_TOOL_SURFACES` | `'jarvis_app'` |
| `LIFE_GRAPH_CAPTURE_SAVED_BY_TOOL_WAIT_SECONDS` | `90` |
| `LIFE_GRAPH_CLAUDE_CODE_SESSION_END_GRACE_MINUTES` | `5` |
| `LIFE_GRAPH_CLAUDE_CODE_SESSION_IDLE_MINUTES` | `240` |
| `LIFE_GRAPH_COLD_START_MIN_MEMORIES` | `50` |
| `LIFE_GRAPH_WHISPER_MODEL` | `'small'` |
| `LIFE_GRAPH_STT_BASE_URL` | `''` |
| `LIFE_GRAPH_STT_MODEL` | `'deepdml/faster-whisper-large-v3-turbo-ct2'` |
| `LIFE_GRAPH_CF_ACCOUNT_ID` | `''` |
| `LIFE_GRAPH_CF_AI_TOKEN` | `''` |
| `LIFE_GRAPH_GROQ_API_KEY` | `''` |
| `LIFE_GRAPH_MINIO_ENDPOINT` | `'localhost:9000'` |
| `LIFE_GRAPH_MINIO_ACCESS_KEY` | `'minioadmin'` |
| `LIFE_GRAPH_MINIO_SECRET_KEY` | `'minioadmin'` |
| `LIFE_GRAPH_MINIO_BUCKET` | `'life-graph'` |
| `LIFE_GRAPH_LM_STUDIO_URL` | `'http://localhost:1234/v1'` |
| `LIFE_GRAPH_LM_STUDIO_API_KEY` | `'lm-studio'` |
| `LIFE_GRAPH_LM_EXTRACTION_MODEL` | `'qwen2.5-3b-instruct'` |
| `LIFE_GRAPH_LM_SYNTHESIS_MODEL` | `'qwen2.5-coder-7b-instruct'` |
| `LIFE_GRAPH_LM_EMBEDDING_MODEL` | `'text-embedding-nomic-embed-text-v1.5'` |
| `LIFE_GRAPH_USE_LOCAL_LLM` | `True` |
| `LIFE_GRAPH_LM_STRUCTURED_OUTPUT` | `True` |
| `LIFE_GRAPH_LM_REASONING_EFFORT` | `—` |
| `LIFE_GRAPH_OPENROUTER_API_KEY` | `''` |
| `LIFE_GRAPH_OPENROUTER_URL` | `'https://openrouter.ai/api/v1'` |
| `LIFE_GRAPH_OPENROUTER_MODEL` | `'deepseek/deepseek-chat'` |
| `LIFE_GRAPH_USE_HYBRID_LLM` | `False` |
| `LIFE_GRAPH_VERTEX_PROJECT` | `'work-update-467706'` |
| `LIFE_GRAPH_VERTEX_LOCATION` | `'global'` |
| `LIFE_GRAPH_VERTEX_CREDENTIALS_PATH` | `''` |
| `LIFE_GRAPH_ADVISOR_MODELS` | `'openrouter/openai/gpt-4o-mini,openrouter/deepseek/deepse…` |
| `LIFE_GRAPH_ADVISOR_TIMEOUT_SECONDS` | `10` |
| `LIFE_GRAPH_ADVISOR_MAX_COST_PER_QUERY` | `0.01` |
| `LIFE_GRAPH_LLM_FALLBACK_CHAIN` | `'openrouter/deepseek/deepseek-chat,gemini/gemini-3.5-flas…` |
| `LIFE_GRAPH_LLM_COOLDOWN_429_SECONDS` | `60` |
| `LIFE_GRAPH_LLM_COOLDOWN_ERROR_SECONDS` | `30` |
| `LIFE_GRAPH_LLM_COOLDOWN_MAX_SECONDS` | `900` |
| `LIFE_GRAPH_LLM_HEALTH_TTL_SECONDS` | `3600` |
| `LIFE_GRAPH_LLM_PAID_FALLBACK_MODEL` | `—` |
| `LIFE_GRAPH_OMNIROUTE_API_KEY` | `''` |
| `LIFE_GRAPH_OMNIROUTE_URL` | `'http://localhost:20128/v1'` |
| `LIFE_GRAPH_OMNIROUTE_MODEL` | `'openai/auto'` |
| `LIFE_GRAPH_RESEARCH_STALE_DAYS` | `30` |
| `LIFE_GRAPH_RESEARCH_MAX_PER_RUN` | `5` |
| `LIFE_GRAPH_RESEARCH_MONTHLY_BUDGET_USD` | `0.6` |
| `LIFE_GRAPH_RESEARCH_CONFIDENCE_THRESHOLD` | `0.7` |
| `LIFE_GRAPH_MONTHLY_BUDGET_USD` | `10.0` |
| `LIFE_GRAPH_BUDGET_SOFT_THRESHOLD` | `0.8` |
| `LIFE_GRAPH_SHADOW_MODE_ENABLED` | `True` |
| `LIFE_GRAPH_SHADOW_MIN_DAYS` | `14` |
| `LIFE_GRAPH_SHADOW_MIN_SAMPLES` | `5` |
| `LIFE_GRAPH_SHADOW_GOOD_RATE` | `0.8` |
| `LIFE_GRAPH_IMPACT_BOOST_ON_SUCCESS` | `0.1` |
| `LIFE_GRAPH_IMPACT_PENALTY_ON_FAILURE` | `0.05` |
| `LIFE_GRAPH_IMPACT_DEFAULT` | `0.5` |
| `LIFE_GRAPH_DEFAULT_PLAN` | `'free'` |
| `LIFE_GRAPH_TENANT_PLANS` | `'{}'` |
| `LIFE_GRAPH_MCP_SERVERS` | `'[]'` |
| `LIFE_GRAPH_MCP_HTTP_ENABLED` | `False` |
| `LIFE_GRAPH_MCP_HTTP_SELF_URL` | `'http://127.0.0.1:8080'` |
| `LIFE_GRAPH_MCP_HTTP_ALLOWED_HOSTS` | `'localhost,127.0.0.1'` |
| `LIFE_GRAPH_CORS_ORIGINS` | `'http://localhost:3000,http://localhost:8000'` |
| `LIFE_GRAPH_AGENT_LLM_MODEL` | `'gemini/gemini-3.6-flash'` |
| `LIFE_GRAPH_AGENT_LLM_TEMPERATURE` | `0.7` |
| `LIFE_GRAPH_AGENT_LLM_MAX_TOKENS` | `4096` |
| `LIFE_GRAPH_AGENT_FALLBACK_MODEL` | `'gemini/gemini-3.5-flash-lite'` |
| `LIFE_GRAPH_AGENT_MAX_ITERATIONS` | `5` |
| `LIFE_GRAPH_AGENT_CONDENSER_ENABLED` | `True` |
| `LIFE_GRAPH_AGENT_CONTEXT_TOKENS` | `32768` |
| `LIFE_GRAPH_AGENT_CONTEXT_TOKENS_BY_MODEL` | `'{}'` |
| `LIFE_GRAPH_AGENT_STUCK_DETECTION` | `True` |
| `LIFE_GRAPH_KERNEL_MAX_CONCURRENT_TASKS` | `8` |
| `LIFE_GRAPH_KERNEL_DEFAULT_TIMEOUT` | `300` |
| `LIFE_GRAPH_KERNEL_DEFAULT_MAX_RETRIES` | `2` |
| `LIFE_GRAPH_KERNEL_TASK_CLEANUP_DAYS` | `30` |
| `LIFE_GRAPH_KERNEL_ENABLE_SCHEDULER` | `True` |
| `LIFE_GRAPH_KERNEL_MAX_CONSECUTIVE_FAILURES` | `3` |
| `LIFE_GRAPH_TAVILY_API_KEY` | `''` |
| `LIFE_GRAPH_WEB_SEARCH_PROVIDER` | `'auto'` |
| `LIFE_GRAPH_SEARXNG_URL` | `''` |
| `LIFE_GRAPH_WEB_SEARCH_MAX_RESULTS` | `6` |
| `LIFE_GRAPH_FETCH_ALLOW_HOSTS` | `''` |
| `LIFE_GRAPH_REQUIRE_SOURCES_PERSONAS` | `'scout,rex'` |
| `LIFE_GRAPH_CONNECTORS_ENABLED` | `True` |
| `LIFE_GRAPH_USER_TIMEZONE` | `'UTC'` |
| `LIFE_GRAPH_CONNECTOR_SECRETS_DIR` | `'~/.config/life-graph/connectors'` |
| `LIFE_GRAPH_CONNECTOR_LOCAL_MODEL_PREFIXES` | `''` |
| `LIFE_GRAPH_CONNECTOR_SYNC_MINUTES` | `15` |
| `LIFE_GRAPH_CONNECTOR_EMAIL_RETENTION_DAYS` | `90` |
| `LIFE_GRAPH_CONNECTOR_EVENT_PAST_DAYS` | `90` |
| `LIFE_GRAPH_CONNECTOR_EVENT_FUTURE_DAYS` | `365` |
| `LIFE_GRAPH_CONNECTOR_NEEDS_REPLY_MIN_HOURS` | `24` |
| `LIFE_GRAPH_CONNECTOR_NEEDS_REPLY_MAX_DAYS` | `14` |
| `LIFE_GRAPH_CONNECTOR_SUMMARIES_PER_SYNC` | `40` |
| `LIFE_GRAPH_CONNECTOR_BILLS_CLOUD` | `'details'` |
| `LIFE_GRAPH_CONNECTOR_OAUTH_REDIRECT_BASE` | `'http://localhost:8080'` |
| `LIFE_GRAPH_CONNECTOR_OAUTH_RETURN_URL` | `'http://localhost:3001/settings'` |
| `LIFE_GRAPH_LANGFUSE_PUBLIC_KEY` | `''` |
| `LIFE_GRAPH_LANGFUSE_SECRET_KEY` | `''` |
| `LIFE_GRAPH_LANGFUSE_HOST` | `'http://localhost:3001'` |
| `LIFE_GRAPH_METRICS_ENABLED` | `True` |
| `LIFE_GRAPH_SELF_IMPROVING_ENABLED` | `False` |
| `LIFE_GRAPH_SELF_IMPROVING_TRACE_ENABLED` | `True` |
| `LIFE_GRAPH_SELF_IMPROVING_PROMPTS_ENABLED` | `True` |
| `LIFE_GRAPH_EVAL_MAX_PARALLEL` | `5` |
| `LIFE_GRAPH_EVAL_ACCURACY_THRESHOLD_PCT` | `90.0` |
| `LIFE_GRAPH_OPTIMIZATION_MIN_IMPROVEMENT_PCT` | `2.0` |
| `LIFE_GRAPH_OPTIMIZATION_MAX_REGRESSION_PCT` | `2.0` |
| `LIFE_GRAPH_OPTIMIZATION_MAX_FEW_SHOT` | `3` |
| `LIFE_GRAPH_OPTIMIZATION_CANDIDATES` | `3` |
| `LIFE_GRAPH_OPTIMIZATION_MIN_HOLDOUT` | `20` |
| `LIFE_GRAPH_EVAL_FACT_MATCH_THRESHOLD` | `0.8` |
| `LIFE_GRAPH_EVAL_FACT_PASS_F1` | `0.8` |
| `LIFE_GRAPH_EVAL_MAX_HOLDOUT_CASES` | `60` |
| `LIFE_GRAPH_UZHAVU_SYNC_URL` | `'http://localhost:8001/api/v1/sync/preferences'` |
| `LIFE_GRAPH_INTERNAL_API_KEY` | `''` |
| `LIFE_GRAPH_WATCHER_SMTP_HOST` | `''` |
| `LIFE_GRAPH_WATCHER_SMTP_PORT` | `587` |
| `LIFE_GRAPH_WATCHER_SMTP_USER` | `''` |
| `LIFE_GRAPH_WATCHER_SMTP_PASSWORD` | `''` |
| `LIFE_GRAPH_WATCHER_SMTP_FROM` | `'life-graph@localhost'` |
| `LIFE_GRAPH_WATCHER_DIGEST_SCHEDULE` | `'0 8 * * *'` |
| `LIFE_GRAPH_WATCHER_WEBHOOK_SECRET` | `''` |
| `LIFE_GRAPH_WATCHER_MAX_EVENTS_PER_RUN` | `100` |
| `LIFE_GRAPH_WATCHER_AUTO_DISABLE_AFTER_FAILURES` | `5` |
| `LIFE_GRAPH_AUTONOMY_TRUST_DECAY_DAYS` | `30` |
| `LIFE_GRAPH_AUTONOMY_TRUST_DECAY_RATE` | `0.05` |
| `LIFE_GRAPH_AUTONOMY_TRUST_FAILURE_PENALTY` | `0.5` |
| `LIFE_GRAPH_AUTONOMY_TRUST_SUCCESS_BOOST` | `0.02` |
| `LIFE_GRAPH_AUTONOMY_APPROVAL_TIMEOUT_HOURS` | `24` |
| `LIFE_GRAPH_AUTONOMY_APPROVAL_STALE_DAYS` | `14` |
| `LIFE_GRAPH_AUTONOMY_MAX_AUTO_ACTIONS_PER_HOUR` | `10` |
| `LIFE_GRAPH_AUTONOMY_MAX_BLAST_RADIUS` | `3` |
| `LIFE_GRAPH_AUTONOMY_DEFAULT_LEVEL` | `'L0'` |
| `LIFE_GRAPH_DRIVER_CLAUDE_CODE_BIN` | `'claude'` |
| `LIFE_GRAPH_DRIVER_CLAUDE_CODE_TIMEOUT_SECONDS` | `1200` |
| `LIFE_GRAPH_DRIVER_CLAUDE_CODE_AUTH` | `'oauth'` |
| `LIFE_GRAPH_DRIVER_CLAUDE_CODE_API_KEY` | `''` |
| `LIFE_GRAPH_DRIVER_OPENCODE_BIN` | `'opencode'` |
| `LIFE_GRAPH_DRIVER_OPENCODE_MODEL` | `'ollama/qwen3-coder:30b'` |
| `LIFE_GRAPH_DRIVER_OPENCODE_OLLAMA_BASE` | `'http://localhost:11434/v1'` |
| `LIFE_GRAPH_DRIVER_OPENCODE_TIMEOUT_SECONDS` | `1200` |
| `LIFE_GRAPH_DRIVER_OPENCODE_ALLOW_BASH` | `False` |
| `LIFE_GRAPH_AUTO_PLAN_MAX_TASKS` | `3` |
| `LIFE_GRAPH_POST_DEPLOY_SMOKE_TIMEOUT` | `300` |
| `LIFE_GRAPH_BOOTSTRAP_ROOT` | `''` |
| `LIFE_GRAPH_BOOTSTRAP_CREATE_GITHUB` | `False` |
| `LIFE_GRAPH_DEV_TASK_RUNNER_ENABLED` | `True` |
| `LIFE_GRAPH_DEV_ROUTE_QUEUE` | `True` |
| `LIFE_GRAPH_DEV_CLOUD_MODELS` | `'openrouter/poolside/laguna-s-2.1:free,openrouter/nvidia/…` |
| `LIFE_GRAPH_USER_ACTIVE_MINUTES` | `30` |
| `LIFE_GRAPH_SPEECH_MODELS` | `'gemma3'` |
| `LIFE_GRAPH_OLLAMA_API_BASE` | `'http://localhost:11434'` |
| `LIFE_GRAPH_LOCAL_LLM_NUM_CTX` | `16384` |
| `LIFE_GRAPH_LOCAL_LLM_WARM_HOURS` | `'7-23'` |
| `LIFE_GRAPH_LOCAL_LLM_IDLE_KEEP_ALIVE` | `'5m'` |
| `LIFE_GRAPH_DEV_LOCAL_HOURS` | `''` |
| `LIFE_GRAPH_OPENCODE_MIN_FREE_GB` | `12.0` |
| `LIFE_GRAPH_CLOUD_RATE_LIMIT_COOLDOWN_SECONDS` | `3600` |
| `LIFE_GRAPH_NVIDIA_NIM_API_KEY` | `''` |
| `LIFE_GRAPH_OFFERS_TENANTS` | `''` |
| `LIFE_GRAPH_OFFERS_NEWS_QUERIES` | `'free LLM API tier\nfree LLM API credits developers\nnew …` |
| `LIFE_GRAPH_OFFERS_MAX_PAGES` | `8` |
| `LIFE_GRAPH_OFFERS_MAX_EVALS_PER_DAY` | `2` |
| `LIFE_GRAPH_PROVIDER_DAILY_LIMITS` | `'{"openrouter": 900, "nvidia_nim": 1000}'` |
| `LIFE_GRAPH_RESEARCH_MAX_PAGES` | `5` |
| `LIFE_GRAPH_RESEARCH_PAGE_CHARS` | `8000` |
| `LIFE_GRAPH_RESEARCH_MODELS` | `''` |
| `LIFE_GRAPH_TECH_WATCH_TENANTS` | `''` |
| `LIFE_GRAPH_TECH_WATCH_TOPICS` | `'{"Open models that fit 16 GB": {"kind": "model", "max_me…` |
| `LIFE_GRAPH_TECH_WATCH_MAX_PAGES` | `6` |
| `LIFE_GRAPH_TECH_WATCH_DIGEST_PER_TOPIC` | `6` |
| `LIFE_GRAPH_TRAJECTORY_STEP_MAX_CHARS` | `16000` |
| `LIFE_GRAPH_TRAJECTORY_OPT_OUT_TENANTS` | `''` |
| `LIFE_GRAPH_DRIVER_SECOND_OPINION_ENABLED` | `False` |
| `LIFE_GRAPH_DRIVER_SECOND_OPINION_MODEL` | `—` |
| `LIFE_GRAPH_CHANGE_REVIEW_MODEL` | `''` |
| `LIFE_GRAPH_DRIVER_PR_AGENT_BIN` | `'pr-agent'` |
| `LIFE_GRAPH_DRIVER_PR_DESCRIPTION_ENABLED` | `True` |
| `LIFE_GRAPH_DRIVER_CODE_CONTEXT_ENABLED` | `True` |
| `LIFE_GRAPH_DRIVER_PR_DESCRIPTION_MODEL` | `—` |
| `LIFE_GRAPH_DRIVER_GH_BIN` | `'gh'` |
| `LIFE_GRAPH_VERIFIER_SANDBOX` | `'none'` |
| `LIFE_GRAPH_VERIFIER_SANDBOX_IMAGE` | `'life-graph-verifier:py3.12'` |
| `LIFE_GRAPH_VERIFIER_SANDBOX_NODE_IMAGE` | `'life-graph-verifier:node22'` |
| `LIFE_GRAPH_VERIFIER_SANDBOX_JVM_IMAGE` | `'life-graph-verifier:jvm17'` |
| `LIFE_GRAPH_VERIFIER_SANDBOX_JVM_MEMORY` | `'6g'` |
| `LIFE_GRAPH_VERIFIER_SANDBOX_CACHE_DIR` | `''` |
| `LIFE_GRAPH_VERIFIER_SANDBOX_MEMORY` | `'4g'` |
| `LIFE_GRAPH_VERIFIER_SANDBOX_CPUS` | `'4'` |
| `LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX` | `'none'` |
| `LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX_IMAGE` | `'life-graph-claude-driver:latest'` |
| `LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX_MEMORY` | `'4g'` |
| `LIFE_GRAPH_DRIVER_CLAUDE_SANDBOX_CPUS` | `'4'` |
| `LIFE_GRAPH_DRIVER_CLAUDE_CODE_CREDS_PATH` | `'~/.claude/.credentials.json'` |
| `LIFE_GRAPH_TOOL_SHELL_ENABLED` | `True` |
| `LIFE_GRAPH_TOOL_SHELL_MODE` | `'allowlist'` |
| `LIFE_GRAPH_TOOL_PRIVILEGED_TENANTS` | `'default'` |
| `LIFE_GRAPH_TOOL_FS_ROOTS` | `''` |
| `LIFE_GRAPH_INTERVIEW_MAX_QUESTIONS_PER_DAY` | `3` |
| `LIFE_GRAPH_INTERVIEW_QUESTION_TTL_DAYS` | `7` |
| `LIFE_GRAPH_BRIEF_HOUR_UTC` | `2` |
| `LIFE_GRAPH_PHONE_DUE_NOTIFICATIONS` | `True` |
| `LIFE_GRAPH_STUDY_NUDGE_HOUR` | `18` |
| `LIFE_GRAPH_VAPID_PUBLIC_KEY` | `''` |
| `LIFE_GRAPH_VAPID_PRIVATE_KEY` | `''` |
| `LIFE_GRAPH_VAPID_SUBJECT` | `'mailto:tolokanathan@gmail.com'` |
| `LIFE_GRAPH_TELEGRAM_BOT_TOKEN` | `''` |
| `LIFE_GRAPH_TELEGRAM_POLL_TIMEOUT` | `25` |
| `LIFE_GRAPH_TELEGRAM_RATE_LIMIT_PER_MIN` | `20` |
| `LIFE_GRAPH_TELEGRAM_ALLOW_APPROVALS` | `False` |
| `LIFE_GRAPH_TELEGRAM_ASSISTANT_PERSONA` | `'jarvis'` |
| `LIFE_GRAPH_LEAD_LOCAL_MODEL` | `''` |
| `LIFE_GRAPH_TELEGRAM_ASK_TIMEOUT_SECONDS` | `240` |
| `LIFE_GRAPH_TTS_BASE_URL` | `''` |
| `LIFE_GRAPH_TTS_MODEL` | `'speaches-ai/Kokoro-82M-v1.0-ONNX'` |
| `LIFE_GRAPH_TTS_VOICE` | `'af_heart'` |
| `LIFE_GRAPH_TTS_FORMAT` | `'mp3'` |
| `LIFE_GRAPH_INVOICE_SELLER_NAME` | `''` |
| `LIFE_GRAPH_INVOICE_SELLER_DETAILS` | `''` |
| `LIFE_GRAPH_SEED_TENANTS` | `'default'` |
| `LIFE_GRAPH_PLAN_LIMITS` | `{'free': {'requests_per_min': 60, 'max_memories': 1000, '…` |
