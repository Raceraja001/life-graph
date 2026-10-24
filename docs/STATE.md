<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Produced by scripts/gen_state.py. Run `python scripts/gen_state.py`
     to refresh. Intent and rationale live in CHARTER.md, not here. -->

# Life Graph — State

> **What exists right now.** Generated from the code by `scripts/gen_state.py`.
>
> This file deliberately contains **no rationale** — for why any of it exists, read [CHARTER.md](../CHARTER.md).

Generated `2026-10-24 20:59 UTC` from `master` @ `460ce5f`

---

## At a glance

| | |
|---|---|
| HTTP operations | **351** across 304 paths, 43 tags |
| Database tables | **84** |
| Migrations | **53** (head: `053_entities`) |
| Event types | **79** |
| Built-in personas | **13** |
| Agent tools | **14** |
| Scheduled jobs | **29** |
| Config settings | **264** (prefix `LIFE_GRAPH_`) |
| Test functions | **3557** in 393 files |
| Dashboard pages | **18** |
| Python | 402 files, 105,774 lines |

---

## HTTP API

351 operations, grouped by OpenAPI tag.

### `assistant` — 34

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/apps/health` | Apps Health |
| GET | `/api/v1/documents` | List Documents |
| POST | `/api/v1/documents` | Add Document |
| GET | `/api/v1/documents/expiring` | Expiring Documents |
| DELETE | `/api/v1/documents/{doc_id}` | Delete Document |
| PATCH | `/api/v1/documents/{doc_id}` | Edit Document |
| GET | `/api/v1/invoices` | List Invoices |
| POST | `/api/v1/invoices` | Create Invoice |
| GET | `/api/v1/invoices/{invoice_id}` | Get Invoice |
| PATCH | `/api/v1/invoices/{invoice_id}` | Edit Invoice |
| GET | `/api/v1/invoices/{invoice_id}/html` | Invoice Html |
| POST | `/api/v1/invoices/{invoice_id}/paid` | Paid Invoice |
| POST | `/api/v1/invoices/{invoice_id}/send` | Send Invoice |
| POST | `/api/v1/invoices/{invoice_id}/void` | Void Invoice |
| POST | `/api/v1/money/alerts` | Import Alerts |
| GET | `/api/v1/money/budgets` | List Budgets |
| DELETE | `/api/v1/money/budgets/{category}` | Delete Budget |
| PUT | `/api/v1/money/budgets/{category}` | Put Budget |
| GET | `/api/v1/money/categories` | Money Categories |
| GET | `/api/v1/money/checkin` | Money Checkin |
| POST | `/api/v1/money/import` | Import Statement |
| GET | `/api/v1/money/summary` | Money Summary |
| GET | `/api/v1/money/transactions` | List Transactions |
| PATCH | `/api/v1/money/transactions/{txn_id}` | Recategorise |
| GET | `/api/v1/monitors` | List Monitors |
| POST | `/api/v1/monitors` | Add Monitor |
| DELETE | `/api/v1/monitors/{monitor_id}` | Delete Monitor |
| PATCH | `/api/v1/monitors/{monitor_id}` | Edit Monitor |
| POST | `/api/v1/monitors/{monitor_id}/check` | Check Monitor |
| POST | `/api/v1/study/cards` | Add Card |
| DELETE | `/api/v1/study/cards/{card_id}` | Delete Card |
| POST | `/api/v1/study/cards/{card_id}/grade` | Grade |
| GET | `/api/v1/study/due` | Due Cards |
| POST | `/api/v1/study/generate` | Generate Cards |

### `kernel` — 30

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/kernel/alerts/external` | Receive an alert from an external system and deliver it |
| POST | `/api/v1/kernel/chat/stream` | Stream a persona chat response (SSE) |
| POST | `/api/v1/kernel/classify` | Classify intent without routing |
| GET | `/api/v1/kernel/models` | List available LLM models for the persona picker |
| GET | `/api/v1/kernel/notifications` | List notifications |
| POST | `/api/v1/kernel/notifications/read-all` | Mark all notifications as read |
| PATCH | `/api/v1/kernel/notifications/{notification_id}/read` | Mark notification as read |
| GET | `/api/v1/kernel/personas` | List all personas for the current tenant |
| POST | `/api/v1/kernel/personas` | Create a new agent persona |
| DELETE | `/api/v1/kernel/personas/{persona_id}` | Deactivate (soft-delete) a persona |
| GET | `/api/v1/kernel/personas/{persona_id}` | Get full persona details |
| PATCH | `/api/v1/kernel/personas/{persona_id}` | Update a persona |
| GET | `/api/v1/kernel/projects` | List registered projects |
| POST | `/api/v1/kernel/projects` | Register a project codebase |
| DELETE | `/api/v1/kernel/projects/{project_id}` | Remove a project |
| GET | `/api/v1/kernel/projects/{project_id}` | Get project details |
| PATCH | `/api/v1/kernel/projects/{project_id}` | Update project settings |
| POST | `/api/v1/kernel/projects/{project_id}/learn` | Learn a project's conventions into preferences (background job) |
| POST | `/api/v1/kernel/projects/{project_id}/scan` | Re-scan a project |
| POST | `/api/v1/kernel/route` | Route a message to the best agent |
| GET | `/api/v1/kernel/schedules` | List scheduled jobs |
| POST | `/api/v1/kernel/schedules` | Create a scheduled job |
| DELETE | `/api/v1/kernel/schedules/{schedule_id}` | Delete (deactivate) a scheduled job |
| GET | `/api/v1/kernel/schedules/{schedule_id}` | Get schedule details |
| PATCH | `/api/v1/kernel/schedules/{schedule_id}` | Update a scheduled job |
| GET | `/api/v1/kernel/sessions` | List routing sessions |
| GET | `/api/v1/kernel/tasks` | List agent tasks with optional filters |
| POST | `/api/v1/kernel/tasks` | Create and queue a new agent task |
| GET | `/api/v1/kernel/tasks/{task_id}` | Get full task details |
| POST | `/api/v1/kernel/tasks/{task_id}/cancel` | Cancel a running task |

### `autonomy` — 28

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/autonomy/approvals` | List Approvals |
| POST | `/api/v1/autonomy/approvals/batch` | Batch Resolve |
| POST | `/api/v1/autonomy/approvals/{approval_id}/resolve` | Resolve Approval |
| GET | `/api/v1/autonomy/audit` | Query Audit Log |
| POST | `/api/v1/autonomy/audit/export` | Export Audit Log |
| POST | `/api/v1/autonomy/audit/{action_id}/rollback` | Rollback From Audit |
| GET | `/api/v1/autonomy/auto-actions` | List Auto Actions |
| POST | `/api/v1/autonomy/auto-actions` | Trigger Auto Action |
| POST | `/api/v1/autonomy/auto-actions/{action_id}/rollback` | Rollback Action |
| GET | `/api/v1/autonomy/levels/{project_id}` | Get Autonomy Level |
| POST | `/api/v1/autonomy/levels/{project_id}/set` | Set Autonomy Level |
| POST | `/api/v1/autonomy/safety/classify` | Classify Action |
| GET | `/api/v1/autonomy/safety/kill-switch` | Get Kill Switch |
| POST | `/api/v1/autonomy/safety/kill-switch/pause` | Pause Kill Switch |
| POST | `/api/v1/autonomy/safety/kill-switch/resume` | Resume Kill Switch |
| GET | `/api/v1/autonomy/safety/rules` | List Rules |
| POST | `/api/v1/autonomy/safety/rules` | Create Rule |
| DELETE | `/api/v1/autonomy/safety/rules/{rule_id}` | Delete Rule |
| GET | `/api/v1/autonomy/safety/rules/{rule_id}` | Get Rule |
| PATCH | `/api/v1/autonomy/safety/rules/{rule_id}` | Update Rule |
| POST | `/api/v1/autonomy/safety/seed` | Seed Defaults |
| GET | `/api/v1/autonomy/shadow/enrollments` | List Enrollments |
| GET | `/api/v1/autonomy/shadow/runs` | List Runs |
| POST | `/api/v1/autonomy/shadow/runs/{run_id}/grade` | Grade Run |
| POST | `/api/v1/autonomy/trust/decay` | Trigger Decay |
| POST | `/api/v1/autonomy/trust/override` | Override Trust |
| GET | `/api/v1/autonomy/trust/scores` | List Scores |
| GET | `/api/v1/autonomy/trust/scores/{score_id}` | Get Score |

### `self-improving` — 23

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/self-improving/dashboard/accuracy-trends` | Accuracy trends over time |
| GET | `/api/v1/self-improving/dashboard/auto-fixes` | Recent auto-fixes |
| GET | `/api/v1/self-improving/dashboard/cost-trends` | Eval cost trends |
| GET | `/api/v1/self-improving/dashboard/overview` | Dashboard overview |
| GET | `/api/v1/self-improving/dashboard/pending-reviews` | Pending optimization reviews |
| GET | `/api/v1/self-improving/dashboard/per-task-accuracy` | Per-task accuracy with status |
| GET | `/api/v1/self-improving/eval-runs/{run_id}` | Get eval run with results |
| GET | `/api/v1/self-improving/eval-runs/{run_id}/failures` | Failure analysis for eval run |
| GET | `/api/v1/self-improving/eval-suites` | List eval suites |
| POST | `/api/v1/self-improving/eval-suites` | Create an eval suite |
| POST | `/api/v1/self-improving/eval-suites/{suite_id}/cases` | Add eval case to suite |
| POST | `/api/v1/self-improving/eval-suites/{suite_id}/cases/bulk` | Bulk import eval cases |
| POST | `/api/v1/self-improving/eval-suites/{suite_id}/run` | Trigger eval run |
| POST | `/api/v1/self-improving/extraction/sync` | Rebuild the extraction eval suite from reviews now |
| GET | `/api/v1/self-improving/optimization-runs/{run_id}` | Get optimization run details |
| POST | `/api/v1/self-improving/optimization-runs/{run_id}/review` | Approve or reject an optimization |
| POST | `/api/v1/self-improving/optimize/{suite_id}` | Manually trigger optimization |
| GET | `/api/v1/self-improving/prompt-versions` | List prompt versions |
| POST | `/api/v1/self-improving/prompt-versions` | Create prompt version |
| POST | `/api/v1/self-improving/prompt-versions/deactivate` | Return a task to its built-in prompt |
| POST | `/api/v1/self-improving/prompt-versions/{version_id}/activate` | Activate a prompt version |
| POST | `/api/v1/self-improving/prompt-versions/{version_id}/rollback` | Rollback to a previous prompt version |
| GET | `/api/v1/self-improving/status` | How much the loop has to learn from |

### `drivers` — 22

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/kernel/drivers` | List registered drivers |
| GET | `/api/v1/kernel/drivers/compute` | Where queued coding work runs right now: local GPU, free cloud model, or later |
| PUT | `/api/v1/kernel/drivers/compute/presence` | Set the active/away switch (auto clears it) |
| POST | `/api/v1/kernel/drivers/dispatch` | Dispatch a task to a driver (testing) |
| GET | `/api/v1/kernel/drivers/failures` | Failed dev tasks with their primary cause |
| GET | `/api/v1/kernel/drivers/night-shift` | What the coding engines did: merged, waiting for you and why, failed and why |
| GET | `/api/v1/kernel/drivers/plans` | Plan tasks, each with its tasks counted by stage |
| GET | `/api/v1/kernel/drivers/plans/{plan_id}` | One plan: spec, criteria and its tasks in order |
| POST | `/api/v1/kernel/drivers/projects/bootstrap` | Idea to app: scaffold, version, register and optionally plan a new app |
| POST | `/api/v1/kernel/drivers/projects/{project_id}/findings` | Report a production failure; queues a fix task (de-duplicated) |
| GET | `/api/v1/kernel/drivers/scorecards` | Per driver and model: success, bounces, merges, cost |
| GET | `/api/v1/kernel/drivers/stats` | Driver performance stats |
| GET | `/api/v1/kernel/drivers/tasks` | List dev tasks with PR and merge state |
| POST | `/api/v1/kernel/drivers/tasks` | Start a dev task in the background |
| GET | `/api/v1/kernel/drivers/tasks/auto-merge-status` | Trust-gate numbers auto_open_pr/auto_merge actually check, per persona/project |
| GET | `/api/v1/kernel/drivers/tasks/dependency-audit-readiness` | Which registered projects can actually run no_vulnerable_deps_in_diff |
| GET | `/api/v1/kernel/drivers/tasks/stats` | Merge rate and timing per persona/project, from dev task history |
| GET | `/api/v1/kernel/drivers/tasks/{task_id}` | Get one dev task |
| POST | `/api/v1/kernel/drivers/tasks/{task_id}/conformance` | Re-check a task's spec against the project's current code |
| GET | `/api/v1/kernel/drivers/tasks/{task_id}/diff` | The change a landed dev task made, as a unified diff |
| GET | `/api/v1/kernel/drivers/tasks/{task_id}/steps` | Every recorded step of a dev task's driver runs, in order |
| GET | `/api/v1/kernel/drivers/templates` | App templates a new project can start from |

### `admin` — 20

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/admin/bulk/delete` | Bulk delete memories |
| POST | `/api/v1/admin/bulk/import` | Bulk import memories |
| POST | `/api/v1/admin/consolidate` | Run consolidation now |
| GET | `/api/v1/admin/export` | Export all memories as NDJSON stream |
| GET | `/api/v1/admin/gaps` | List knowledge gaps |
| POST | `/api/v1/admin/ingest` | Ingest raw text |
| GET | `/api/v1/admin/jobs` | List recent job runs |
| POST | `/api/v1/admin/jobs/cleanup-memories` | Enqueue one-time memory cleanup job |
| POST | `/api/v1/admin/jobs/consolidate` | Enqueue consolidation job |
| POST | `/api/v1/admin/micro-consolidate/{session_id}` | Run micro-consolidation for a session |
| GET | `/api/v1/admin/stats` | System statistics |
| POST | `/api/v1/admin/tenants/provision` | Provision a new tenant |
| DELETE | `/api/v1/admin/tenants/{tenant_id}` | Permanently delete a tenant |
| GET | `/api/v1/admin/tenants/{tenant_id}` | Get tenant summary |
| POST | `/api/v1/admin/tenants/{tenant_id}/deactivate` | Deactivate a tenant |
| POST | `/api/v1/admin/tenants/{tenant_id}/reactivate` | Reactivate a tenant |
| GET | `/api/v1/admin/webhooks` | List webhooks |
| POST | `/api/v1/admin/webhooks` | Register a webhook |
| DELETE | `/api/v1/admin/webhooks/{webhook_id}` | Delete a webhook |
| POST | `/api/v1/admin/webhooks/{webhook_id}/test` | Test a webhook |

### `connectors` — 15

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/connectors` | Connector catalogue and accounts |
| POST | `/api/v1/connectors/accounts` | Add an account |
| DELETE | `/api/v1/connectors/accounts/{account_id}` | Remove an account and its indexed items |
| PATCH | `/api/v1/connectors/accounts/{account_id}` | Change an account |
| PUT | `/api/v1/connectors/accounts/{account_id}/credential` | Replace an account's credential |
| POST | `/api/v1/connectors/accounts/{account_id}/import` | Replace an account's items from a file |
| POST | `/api/v1/connectors/accounts/{account_id}/oauth/start` | Begin Google sign-in |
| POST | `/api/v1/connectors/accounts/{account_id}/sync` | Sync now (background) |
| POST | `/api/v1/connectors/bills/rescan` | Look for bills in recent mail (background) |
| PUT | `/api/v1/connectors/google-client` | Store the Google OAuth client (Desktop app JSON) |
| POST | `/api/v1/connectors/items/{item_id}/bill` | Mark a bill from mail paid, dismiss it, or remind |
| POST | `/api/v1/connectors/items/{item_id}/dismiss-promise` | Hide a detected promise |
| POST | `/api/v1/connectors/items/{item_id}/remind` | Turn a promise from sent mail into a reminder |
| GET | `/api/v1/connectors/recommend` | Suggested auth method for an address |
| GET | `/api/v1/connectors/today` | Today's events and mail waiting on you (dashboard view) |

### `jarvis` — 15

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/jarvis/brief/latest` | The newest daily brief, with its audio |
| POST | `/api/v1/jarvis/chat` | Talk to Jarvis; the reply streams back (SSE) |
| GET | `/api/v1/jarvis/conversations` | Your conversations with Jarvis, newest first |
| GET | `/api/v1/jarvis/conversations/{conversation_id}/messages` | One conversation, oldest first |
| GET | `/api/v1/jarvis/memories/pending` | Memories waiting for your review, newest first |
| POST | `/api/v1/jarvis/memories/{memory_id}/approve` | Keep a memory |
| POST | `/api/v1/jarvis/memories/{memory_id}/reject` | Drop a memory |
| POST | `/api/v1/jarvis/memories/{memory_id}/undo` | Take back a memory Jarvis just saved |
| GET | `/api/v1/jarvis/notifications` | What Jarvis has to tell you, oldest first |
| POST | `/api/v1/jarvis/notifications/{notification_id}/action` | Tap a notification's button |
| POST | `/api/v1/jarvis/read-image` | The words in an image, read on this PC; nothing is stored |
| GET | `/api/v1/jarvis/reminders` | Your pending reminders, soonest first |
| POST | `/api/v1/jarvis/reminders/{reminder_id}/cancel` | Cancel a reminder |
| POST | `/api/v1/jarvis/voice` | Speak to Jarvis: audio in, spoken reply out |
| POST | `/api/v1/jarvis/warm` | Get Jarvis's local model ready |

### `judgment-engine` — 14

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/judgment/calibration` | Get calibration data |
| GET | `/api/v1/judgment/calibration/curve` | Get calibration curve data |
| POST | `/api/v1/judgment/calibration/recompute` | Recompute calibration snapshots now |
| POST | `/api/v1/judgment/challenge` | Create adversarial challenge |
| POST | `/api/v1/judgment/challenge/{challenge_id}/resolve` | Resolve a challenge |
| GET | `/api/v1/judgment/decisions` | List decisions |
| POST | `/api/v1/judgment/decisions` | Create a decision |
| GET | `/api/v1/judgment/decisions/{decision_id}` | Get decision with predictions |
| GET | `/api/v1/judgment/predictions` | List predictions |
| POST | `/api/v1/judgment/predictions` | Create a prediction |
| POST | `/api/v1/judgment/predictions/{prediction_id}/accept` | Accept a suggested prediction |
| POST | `/api/v1/judgment/predictions/{prediction_id}/dismiss` | Dismiss a suggested prediction |
| POST | `/api/v1/judgment/predictions/{prediction_id}/resolve` | Resolve a prediction |
| GET | `/api/v1/judgment/stats` | Judgment dashboard stats |

### `watchers` — 14

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/watchers/configs` | List all watcher configurations |
| PATCH | `/api/v1/watchers/configs/{watcher_name}` | Update a watcher configuration |
| GET | `/api/v1/watchers/events` | List watch events |
| POST | `/api/v1/watchers/events/acknowledge-all` | Bulk acknowledge events |
| GET | `/api/v1/watchers/events/summary` | Get event summary counts |
| POST | `/api/v1/watchers/events/{event_id}/acknowledge` | Acknowledge a single event |
| GET | `/api/v1/watchers/notification-channels` | List notification channels |
| POST | `/api/v1/watchers/notification-channels` | Create a notification channel |
| DELETE | `/api/v1/watchers/notification-channels/{channel_id}` | Delete a notification channel |
| PATCH | `/api/v1/watchers/notification-channels/{channel_id}` | Update a notification channel |
| GET | `/api/v1/watchers/notifications` | List notifications |
| GET | `/api/v1/watchers/runs` | List watcher runs |
| GET | `/api/v1/watchers/tech-radar` | List tech radar articles |
| POST | `/api/v1/watchers/{watcher_name}/run` | Trigger a manual watcher run |

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

### `procedures` — 7

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/procedures/` | List procedures |
| POST | `/api/v1/procedures/` | Create a procedure |
| GET | `/api/v1/procedures/match/{query}` | Find matching procedures |
| DELETE | `/api/v1/procedures/{procedure_id}` | Delete a procedure |
| GET | `/api/v1/procedures/{procedure_id}` | Get a procedure by ID |
| PATCH | `/api/v1/procedures/{procedure_id}` | Update a procedure |
| POST | `/api/v1/procedures/{procedure_id}/apply` | Record a procedure application |

### `conversations` — 6

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/conversations` | List Conversations |
| POST | `/api/v1/conversations` | Create Conversation |
| DELETE | `/api/v1/conversations/{conversation_id}` | Delete Conversation |
| GET | `/api/v1/conversations/{conversation_id}` | Get Conversation |
| POST | `/api/v1/conversations/{conversation_id}/distill` | Distill Conversation Endpoint |
| POST | `/api/v1/conversations/{conversation_id}/messages` | Post Message |

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

### `Agent Tasks` — 5

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/agent-tasks` | Create Task |
| PATCH | `/api/v1/agent-tasks/{task_id}` | Update Task |
| POST | `/api/v1/agent-tasks/{task_id}/cancel` | Cancel Task |
| GET | `/api/v1/agent-tasks/{task_id}/children` | Get Children |
| GET | `/api/v1/agent-tasks/{task_id}/tree` | Get Task Tree |

### `capture-spine` — 5

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/capture/` | List capture events |
| POST | `/api/v1/capture/` | Ingest a capture event |
| POST | `/api/v1/capture/correction` | Record a correction |
| GET | `/api/v1/capture/corrections` | List corrections |
| GET | `/api/v1/capture/corrections/export` | Export correction triples as NDJSON |

### `evidence` — 5

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/evidence/` | Add evidence to a preference |
| GET | `/api/v1/evidence/for-preference/{preference_id}` | List evidence for a preference |
| POST | `/api/v1/evidence/search` | Semantic evidence search |
| DELETE | `/api/v1/evidence/{evidence_id}` | Soft-delete evidence |
| GET | `/api/v1/evidence/{evidence_id}` | Get a single evidence item |

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

### `research` — 5

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/research` | Answer a question from web pages read now, with sources |
| GET | `/api/v1/research/runs` | List research runs |
| GET | `/api/v1/research/runs/{run_id}` | Get research run detail |
| POST | `/api/v1/research/trigger` | Trigger a research cycle |
| GET | `/api/v1/tech-watch` | What the tech watch found new on your topics |

### `sessions` — 5

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/sessions/` | List recent sessions |
| POST | `/api/v1/sessions/start` | Start a new session |
| GET | `/api/v1/sessions/{session_id}` | Get a session by ID |
| POST | `/api/v1/sessions/{session_id}/end` | End a session |
| POST | `/api/v1/sessions/{session_id}/heartbeat` | Update session context mid-conversation |

### `Agent Messages` — 4

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/agent-messages` | Send Message |
| GET | `/api/v1/agent-messages/inbox/{agent}` | Get Inbox |
| PATCH | `/api/v1/agent-messages/{message_id}/read` | Mark Read |
| POST | `/api/v1/agent-messages/{message_id}/reply` | Reply To Message |

### `advisor` — 4

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/advisor/ask` | Query multiple models for a recommendation |
| GET | `/api/v1/advisor/sessions` | List advisor sessions |
| GET | `/api/v1/advisor/sessions/{session_id}` | Get an advisor session by ID |
| POST | `/api/v1/advisor/sessions/{session_id}/choose` | Record which model's recommendation was chosen |

### `devices` — 4

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/devices` | Paired phones |
| POST | `/api/v1/devices/codes` | A one-time code to pair a phone |
| POST | `/api/v1/devices/pair` | Pair a phone with a one-time code (no API key) |
| DELETE | `/api/v1/devices/{device_id}` | Revoke a phone: its token stops working at once |

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

### `multi-modal` — 4

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/ingest/document` | Ingest a document |
| POST | `/api/v1/ingest/image` | Ingest an image for OCR |
| POST | `/api/v1/ingest/transcribe` | Transcribe a voice recording without storing it as a memory |
| POST | `/api/v1/ingest/voice` | Ingest a voice recording |

### `observability` — 4

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/kernel/observability/agents` | Every persona, its model, and tools it lists that do not exist |
| GET | `/api/v1/kernel/observability/budget` | Month-to-date spend against the cap, with the top tasks |
| GET | `/api/v1/kernel/observability/decision-gaps` | Topics discussed often with no recorded decision |
| GET | `/api/v1/kernel/observability/system` | Subsystems, dev-task runner, queue, drivers and local models |

### `push` — 4

| Method | Path | Summary |
|---|---|---|
| DELETE | `/api/v1/push/subscriptions` | Remove a browser push subscription |
| POST | `/api/v1/push/subscriptions` | Save a browser push subscription |
| POST | `/api/v1/push/test` | Send a test push notification to the caller's tenant |
| GET | `/api/v1/push/vapid-key` | Get the public VAPID key |

### `search` — 4

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/search/` | Search across memories (vector, hybrid, or tri-hybrid) |
| POST | `/api/v1/search/ask` | Ask a question — get a synthesized answer from memories |
| POST | `/api/v1/search/recall` | Proactive recall at session start |
| POST | `/api/v1/search/recall/event` | Mid-session event-driven recall |

### `telegram` — 4

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/integrations/telegram/bindings` | List the Telegram chats linked to this tenant |
| DELETE | `/api/v1/integrations/telegram/bindings/{binding_id}` | Revoke a Telegram binding |
| POST | `/api/v1/integrations/telegram/pair` | Mint a pairing code for a Telegram chat |
| GET | `/api/v1/integrations/telegram/status` | Report whether the Telegram bridge is running |

### `workflows` — 4

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/workflows/` | Create a workflow DAG |
| POST | `/api/v1/workflows/{workflow_id}/run` | Start a workflow run |
| GET | `/api/v1/workflows/{workflow_id}/runs/{run_id}` | Get workflow run with step details |
| POST | `/api/v1/workflows/{workflow_id}/runs/{run_id}/cancel` | Cancel a workflow run |

### `approvals` — 3

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/approvals` | List items awaiting a decision |
| POST | `/api/v1/approvals/{approval_id}/approve` | Approve an item (runs its side-effect) |
| POST | `/api/v1/approvals/{approval_id}/reject` | Reject an item |

### `interview` — 3

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/interview/pending` | Today's pending interview questions |
| POST | `/api/v1/interview/{question_id}/answer` | Answer an interview question |
| POST | `/api/v1/interview/{question_id}/skip` | Skip an interview question |

### `shared-context` — 3

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/shared-context/` | Create a shared context entry |
| GET | `/api/v1/shared-context/thread/{root_task_id}` | Get context from a task thread |
| GET | `/api/v1/shared-context/{project_id}` | Search shared context by project |

### `Internal Sync` — 2

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/internal/sync/analytics` | Receive Analytics |
| POST | `/api/v1/internal/sync/preferences` | Sync Preferences |

### `agent` — 2

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/agent/context` | Build agent context for a task |
| POST | `/api/v1/agent/learn` | Learn from a completed task |

### `brief` — 2

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/brief/compose` | Compose today's brief now |
| GET | `/api/v1/brief/today` | Latest composed daily brief |

### `llm-offers` — 2

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/llm-offers` | Free LLM models, tiers and credits found, with their evaluation |
| POST | `/api/v1/llm-offers/{offer_id}/evaluate` | Queue an offer for evaluation |

### `health` — 1

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/health/models` | Model Health |

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

84 tables. **Tenant** marks a `tenant_id` column — the multi-tenancy invariant requires every query to filter on it.

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
| `connector_accounts` | 18 | ✓ | `039_connectors` |
| `connector_items` | 25 | ✓ | `039_connectors` |
| `conversation_messages` | 8 | ✓ | `027_conversations` |
| `conversations` | 6 | ✓ | `027_conversations` |
| `cross_system_syncs` | 20 | ✓ | `017_agent_networks` |
| `device_pairing_codes` | 5 | ✓ | `052_devices` |
| `devices` | 7 | ✓ | `052_devices` |
| `documents` | 15 | ✓ | `045_documents` |
| `entities` | 7 | ✓ | `053_entities` |
| `eval_cases` | 10 | — | `015_self_improving` |
| `eval_results` | 14 | — | `015_self_improving` |
| `eval_runs` | 18 | — | `015_self_improving` |
| `eval_suites` | 14 | ✓ | `015_self_improving` |
| `evidence` | 16 | ✓ | `014_personal_ai` |
| `external_sessions` | 11 | ✓ | `030_external_sessions` |
| `extraction_traces` | 10 | ✓ | `038_extraction_traces` |
| `intentions` | 16 | ✓ | `001_initial_schema` |
| `invoices` | 21 | ✓ | `049_invoices` |
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
| `llm_catalog_snapshots` | 4 | — | `050_llm_offers` |
| `llm_offers` | 16 | ✓ | `050_llm_offers` |
| `memories` | 34 | ✓ | `001_initial_schema` |
| `memory_entities` | 3 | ✓ | `053_entities` |
| `memory_links` | 8 | ✓ | `—` |
| `memory_sessions` | 5 | — | `001_initial_schema` |
| `money_budgets` | 7 | ✓ | `046_money` |
| `money_category_rules` | 5 | ✓ | `046_money` |
| `money_transactions` | 14 | ✓ | `046_money` |
| `nightly_run_log` | 15 | ✓ | `015_self_improving` |
| `notification_channels` | 9 | ✓ | `016_ambient_ai` |
| `notifications` | 14 | ✓ | `013_projects_notifications` |
| `optimization_runs` | 28 | ✓ | `015_self_improving` |
| `page_monitors` | 17 | ✓ | `047_page_monitors` |
| `preferences` | 21 | ✓ | `014_personal_ai` |
| `procedures` | 14 | ✓ | `—` |
| `projects` | 18 | ✓ | `013_projects_notifications` |
| `prompt_versions` | 14 | ✓ | `015_self_improving` |
| `push_subscriptions` | 8 | ✓ | `028_push_subscriptions` |
| `research_runs` | 12 | ✓ | `014_personal_ai` |
| `review_cards` | 14 | ✓ | `048_review_cards` |
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
| `topic_findings` | 10 | ✓ | `051_topic_findings` |
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
| **jarvis** — The user's assistant and the lead: the one persona the user talks to. | `—` | — | — | 29 |

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

29 ARQ cron jobs (times are UTC).

| Job | Schedule | Function |
|---|---|---|
| `check_approval_timeouts` | every 5 min | `life_graph.workers.tasks.check_approval_timeouts` |
| `close_claude_code_sessions` | hourly at :04,:14,:24,:34,:44,:54 | `life_graph.workers.claude_code_sessions.close_claude_code_sessions` |
| `decay_trust_scores` | 05:00 | `life_graph.workers.tasks.decay_trust_scores` |
| `distill_idle_conversations` | every 15 min | `life_graph.workers.distill.distill_idle_conversations` |
| `failure_pattern_mining` | 02:30 | `life_graph.workers.tasks.failure_pattern_mining` |
| `purge_connector_items` | 04:40 | `life_graph.workers.tasks.purge_connector_items` |
| `purge_telegram_pairing_codes` | 04:30 | `life_graph.workers.telegram.purge_telegram_pairing_codes` |
| `run_all_consolidations` | 03:00 | `life_graph.workers.tasks.run_all_consolidations` |
| `run_all_decay_sweeps` | 04:00 | `life_graph.workers.decay.run_all_decay_sweeps` |
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
| `sweep_stuck_captures` | hourly at :07,:22,:37,:52 | `life_graph.workers.capture_sweep.sweep_stuck_captures` |
| `sync_connectors` | every 5 min | `life_graph.workers.tasks.sync_connectors` |
| `sync_dev_task_prs` | every 15 min | `life_graph.workers.tasks.sync_dev_task_prs` |
| `tick_scheduled_jobs` | every minute | `life_graph.workers.tasks.tick_scheduled_jobs` |
| `write_daily_episodes` | hourly at :41 | `life_graph.workers.episodes.write_daily_episodes` |
| `write_due_notifications` | hourly at :04,:19,:34,:49 | `life_graph.workers.due_notifications.write_due_notifications` |

---

## Dashboard

18 pages.

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
| `/calibration` | `dashboard/app/calibration/page.tsx` |
| `/decisions` | `dashboard/app/decisions/page.tsx` |
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
| `whatsapp-bot` | Not this product | — |

---

## Migrations

53 revisions, head `053_entities`.

`001_initial_schema` · `002_add_age_graph` · `003_multi_tenancy` · `004_webhooks_tenants_dedup` · `005_cold_start_config` · `006_confidence_decay` · `007_bm25_search` · `008_impact_scoring` · `009_memory_links` · `010_procedures` · `011_os_kernel` · `012_scheduled_jobs` · `013_projects_notifications` · `014_personal_ai` · `015_self_improving` · `016_ambient_ai` · `017_agent_networks` · `018_autonomous_ai` · `019_capture_spine` · `020_judgment_engine` · `021_agent_drivers` · `022_trust_tiers` · `023_budget_spend` · `024_shadow_mode` · `025_embedding_dim` · `026_approvals` · `027_conversations` · `028_push_subscriptions` · `029_conversation_last_distilled_at` · `030_external_sessions` · `031_add_kind_instruction_to_autonomy` · `032_autonomy_kill_switch` · `033_widen_evidence_stance` · `034_notification_channel_name` · `035_decay_horizon_six_months` · `036_backfill_memory_trust_tiers` · `037_telegram_bridge` · `038_extraction_traces` · `039_connectors` · `040_connector_contacts` · `041_connector_code` · `042_connector_tasks` · `043_assistant_message_surface` · `044_agent_run_steps` · `045_documents` · `046_money` · `047_page_monitors` · `048_review_cards` · `049_invoices` · `050_llm_offers` · `051_topic_findings` · `052_devices` · `053_entities`

---

## Tests

Counts `def test_*` declarations. pytest collects more cases than this — `@pytest.mark.parametrize` expands one function into many.

| Suite | Files | Functions |
|---|---:|---:|
| `tests/unit/` | 301 | 2816 |
| `tests/integration/` | 91 | 729 |
| `tests/ (root)` | 1 | 12 |
| **total** | **393** | **3557** |

---

## Configuration

264 settings, all overridable by environment variable.

| Environment variable | Default |
|---|---|
| `LIFE_GRAPH_APP_NAME` | `'Life Graph'` |
| `LIFE_GRAPH_VERSION` | `'1.0.0'` |
| `LIFE_GRAPH_ENVIRONMENT` | `'development'` |
| `LIFE_GRAPH_DEBUG` | `False` |
| `LIFE_GRAPH_LOG_LEVEL` | `'INFO'` |
| `LIFE_GRAPH_LOG_FORMAT` | `'text'` |
| `LIFE_GRAPH_API_KEY` | `—` |
| `LIFE_GRAPH_SERVICE_API_KEYS` | `''` |
| `LIFE_GRAPH_DEVICE_TOKEN_IDLE_DAYS` | `60` |
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
