# Ambient Advisory Roles — Design (Sub-project A)

**Status:** Approved design, ready for implementation plan.
**Date:** 2026-08-06
**Author:** brainstormed with the developer (tolokanathan@gmail.com).

## Goal

Make Life Graph's advisory personas *ambient*: `scout`, `admin`, and `tutor` run
on a schedule without being asked, produce structured findings, and reach the
user the way they chose — **urgent items push to the phone immediately, everything
else rides the existing daily brief.** This is the "Jarvis reaches out to *you*"
layer, built on rails that already exist.

## Non-goals (this sub-project)

- **Autonomous *action* roles** (cody/ops/swe-lead running unprompted, gated by the
  approval queue). That is **Sub-project B** — it depends on the scheduler ticker
  this sub-project builds, and its autonomous-execution safety deserves its own
  spec + review. Not dropped; sequenced next.
- No new LLM model wiring; runs use the personas' existing model config on the VM
  (OpenRouter free models today).

## Context — what already exists (verified against master @ b64255a)

Almost every primitive exists and is production-shaped. The build is small.

- **`scout` 🧭, `admin` 🗂️, `tutor` 🎓 personas** — seeded in `_BUILTIN_PERSONAS`
  (`kernel/personas.py:189-230`), advisory-only, read-only `allowed_tools`. Live on the VM.
- **`ScheduledJob` model + `SchedulerService`** (`models/db.py:993`, `kernel/scheduler.py`):
  CRUD, a self-contained cron parser, `get_due_jobs()` (active jobs with
  `next_run_at <= now`), and `fire_job(tenant_id, job_id)` → `ProcessManager.spawn(agent_name, input_data, ...)`
  → records the run, recomputes `next_run_at`, auto-disables after N consecutive failures.
  **Fully built except one thing: nothing ever calls `get_due_jobs`/`fire_job`.**
- **Headless execution** (`kernel/process_manager.py`): `spawn` inserts an `AgentTask`
  and launches `asyncio.create_task(_execute_task)`; `_run_agent` runs `AgentOrchestrator`
  to completion and persists `AgentTask.result`. **`allowed_tools` is already enforced**
  here (`process_manager.py:504-529` filters the tool set; `orchestrator.py:84-87` makes the
  filter non-bypassable) — so a scheduled advisory run *cannot* call a write tool.
- **Kernel notifications** (`kernel/notification_engine.py`, `models/db.py:1196`):
  `NotificationEngine.create(...)` writes a `Notification` (priority `critical|important|info`,
  `deliver_at_brief` flag, `source_type`/`source_id`); dashboard reads
  `GET /api/v1/kernel/notifications`.
- **Daily brief** (`services/brief.py`): bundles held (`deliver_at_brief`) notifications,
  fires `BRIEF_COMPOSED`.
- **Web push** (`services/webpush.py` `PushService`, `services/push_delivery.py`,
  `models/db.py:2442` `PushSubscription`, `api/push.py`, VAPID in `config.py`): real transport.
  Today `PushDeliveryHandler` pushes **only** on `BRIEF_COMPOSED` — individual notifications
  are pull-only.

**The real gaps:** (1) no ticker fires scheduled jobs; (2) no bridge from a finished
advisory run to notifications; (3) no immediate-push path for a single urgent notification.

## Decisions (locked with the developer)

1. **Delivery = hybrid.** Urgent findings push immediately; the rest ride the daily brief.
2. **Scout input = watch-list (primary) + memory signals (enrichment).** The explicit
   list carries the run so a weak free model can't drift; memory only nudges/expands.
3. **Findings bridge = structured JSON result**, with a fallback that never loses a finding.
4. **Roster = scout + admin + tutor**, on a **generic** framework so any advisory persona
   is schedulable. Action personas stay interactive-only (→ Sub-project B).
5. **No deferral within A:** includes the fuller memory enrichment *and* a dashboard UI to
   manage watch-list / schedules / toggles and view findings.

## Architecture

```
ARQ cron  tick_scheduled_jobs  (every minute)
        │  for each tenant: SchedulerService.get_due_jobs() → fire_job()
        ▼
ProcessManager.spawn(scout|admin|tutor)   ← headless AgentTask, allowed_tools enforced (read-only)
        │   input: watch-list (scout) + memory-enrichment context + novelty context
        ▼
AgentTask.result  (persona ends with a JSON findings array)
        │
        ▼
FindingsBridge  (subscribes to TASK_COMPLETED, advisory personas only)
        │   parse JSON → N findings ; malformed → 1 "brief" digest (fallback)
        ├── urgency "now"   → Notification(priority=important)             → NOTIFICATION_CREATED
        └── urgency "brief" → Notification(priority=info, deliver_at_brief=True)
                                                                            │
NOTIFICATION_CREATED handler:  push immediately IF priority≥important AND not deliver_at_brief
BRIEF_COMPOSED handler (existing): bundles the "brief" ones into the daily brief push
```

## Components

### 1. Scheduler ticker (`workers/tasks.py` + `workers/settings.py`)
New ARQ cron `tick_scheduled_jobs`, `cron(minute=set(range(60)))` (every minute),
`run_at_startup=False`. For each tenant (same enumerate-tenants + `set_tenant_context`
pattern the 12 existing crons use): `due = await scheduler.get_due_jobs()`, then
`await scheduler.fire_job(tenant_id, job.id)` per due job, each wrapped so one failure
never blocks the others. No change to `SchedulerService` itself. Idempotency: `fire_job`
already recomputes `next_run_at`; a minute-granular tick with a `next_run_at <= now`
filter fires each job once per due window.

### 2. Ambient scheduled jobs + seeding (`kernel/scheduler.py` or a seed module)
An idempotent seeder (mirroring the persona seeder's "skip if exists" pattern,
`personas.py:seed`) creates, per tenant, three `ScheduledJob`s if absent:
- `scout-daily`  — `agent_name="scout"`, cron `0 7 * * *` (07:00 UTC; **must precede
  `settings.brief_hour_utc`** so the day's findings make that day's brief — verify the value
  during planning and adjust if needed), `input = {"topics": []}` (empty watch-list; user fills it).
- `admin-daily`  — `agent_name="admin"`, cron `0 7 * * *`, `input = {}`.
- `tutor-daily`  — `agent_name="tutor"`, cron `0 7 * * *`, `input = {}`, seeded **inactive**
  (tutor nudges are opt-in; user enables via the UI).
Seeding runs in the `lifespan` startup alongside persona seeding. Cadence + enabled
state are editable afterward through the existing scheduler CRUD API / the new UI.

### 3. Watch-list (no new table)
Scout's watch-list lives in `scout-daily.input.topics` (a JSONB array on the existing
`ScheduledJob` row). Read at run time by the input-builder; edited via the scheduler
CRUD API (`PATCH` job input) and the dashboard UI. No schema change.

### 4. Memory enrichment (`services/ambient_context.py`, new)
Before a scout run, build the persona `input_data` the orchestrator sees:
- **Watch-list topics** (primary) from the job input.
- **Memory signals** (enrichment): query the tenant's recent high-salience memories
  (last ~14 days, ranked by the existing importance/recall scoring), extract their
  dominant tags/topics, and surface the top few as *suggested* adjacent areas — clearly
  labelled secondary so the model treats the watch-list as the spine.
- **Novelty context** (see §6): titles of this persona's own findings from the last 7 days.
Composed into a single system/user preamble; the persona prompt already says "surface
genuinely new findings, never restate."

Admin and tutor use the same builder minus the watch-list: admin gets recent
commitment-type memories + novelty; tutor gets recent learning-tagged memories + novelty.

### 5. Findings bridge (`services/findings_bridge.py`, new)
Subscribes to `TASK_COMPLETED`. Acts **only** when the task's persona is advisory
(scout/admin/tutor — gate on persona name / an `is_ambient_advisory` marker). Reads
`AgentTask.result["response"]`, extracts the trailing JSON array
`[{title, detail, urgency}]` (tolerant extraction: last fenced/`[...]` block). For each
finding, `NotificationEngine.create(title, body=detail, priority=map(urgency),
deliver_at_brief=(urgency=="brief"), source_type=persona_name, source_id=task_id)`.
**Fallback:** if no valid JSON, create a single `Notification` with the whole result as
the body, `urgency="brief"` — a finding is never silently dropped. Persona prompts get a
short appended contract describing the exact JSON shape and the `now`/`brief` urgency rule.

### 6. Hybrid delivery
- **Brief path** (exists): `deliver_at_brief=True` → bundled by `BriefComposer` → the daily
  `BRIEF_COMPOSED` push. Zero new code.
- **Immediate path** (new, event-driven per the codebase invariant): `NotificationEngine.create`
  emits a `NOTIFICATION_CREATED` event. A new handler (sibling of `PushDeliveryHandler`,
  subscribed in `lifespan`) pushes via `PushService.send_to_tenant(tenant_id, title, body, "/m")`
  **iff** `priority in (critical, important)` **and** `deliver_at_brief` is False. Push
  failures are swallowed (never break the flow), matching the brief handler.
- **Novelty:** the input-builder (§4) queries `Notification` rows with
  `source_type=persona_name` from the last 7 days and injects their titles as
  "already reported — don't repeat." Reuses the `Notification` table; no new store.

### 7. Advisory safety
Already guaranteed: the headless path enforces `allowed_tools`
(`process_manager.py:504-529` + `orchestrator.py:84-87`), and scout/admin/tutor carry
read-only tool lists. This spec adds a **test** asserting a scheduled advisory run cannot
invoke a write tool, so the guarantee is pinned against regression. No new enforcement code.

### 8. Dashboard UI (`dashboard/`, mobile surface)
A "Roles" / ambient settings surface in the mobile app:
- List the three ambient roles with enable/disable toggles (→ scheduler CRUD `is_active`).
- Edit Scout's **watch-list** (add/remove topics → `PATCH` job `input.topics`).
- Edit each role's **schedule** (a simple cadence picker → cron string).
- Show recent **findings** (reads the existing notifications feed, filtered by
  `source_type in {scout,admin,tutor}`), so the user sees what ambient roles surfaced.
Built on the existing `lib/api.ts` client pattern; new endpoints only if the scheduler
CRUD API lacks a needed shape (prefer reusing `GET/POST/PATCH /api/v1/kernel/schedules`).

## Data model & events

- **No new tables.** Watch-list → existing `ScheduledJob.input`; findings + novelty →
  existing `Notification`.
- **New event type** `NOTIFICATION_CREATED` (`core/events.py` `EventType`), emitted by
  `NotificationEngine.create`. (Emit is additive; existing callers unaffected.)
- Optional tiny marker so the bridge/UI can identify ambient-advisory personas without a
  hardcoded name set — e.g. an `intent_tags` check (`"digest"`/`"scout"`/`"reminder"`/`"study"`)
  or a small constant `AMBIENT_ADVISORY = {"scout","admin","tutor"}`. Constant preferred for clarity.

## API surface

- **Reuse** the existing kernel scheduler CRUD (`api/kernel.py:700-844`) for job list/create/update/toggle
  and the notifications feed (`api/kernel.py:998`). Add convenience endpoints only if the UI needs a
  shape the CRUD can't express (e.g. a dedicated `PATCH /schedules/{id}/topics`); decide during planning.

## Error handling

- Ticker: per-job try/except; a failing job is isolated and (via existing `fire_job` logic)
  auto-disabled after N consecutive failures, emitting `SCHEDULE_DISABLED`.
- Bridge: malformed JSON → digest fallback; bridge exceptions logged, never propagate to the task.
- Push: swallowed with a warning (delivery must never break the run).
- Empty findings (`[]`): create no notification — silence is valid; the user isn't pinged for nothing.

## Testing

- **Unit:** ticker due-selection + per-job isolation; JSON bridge parse (happy path, malformed
  fallback, empty array); urgency→(priority, deliver_at_brief) mapping; novelty-context builder
  (dedups against recent same-source notifications); memory-enrichment builder (watch-list primary).
- **Integration:** seed job → ticker fires → advisory task completes with a JSON result →
  correct Notifications created with correct delivery routing; `NOTIFICATION_CREATED` handler pushes
  an urgent one and skips a brief one; advisory run cannot call a write tool.
- Follows the repo pattern: `httpx.AsyncClient` + `ASGITransport`, tenant headers, `conftest` pgvector mock.

## Scope

**In (Sub-project A):** scheduler ticker; seeded scout/admin/tutor jobs; watch-list in job input;
memory enrichment; JSON findings bridge + fallback; hybrid delivery (immediate push + brief);
novelty; advisory-safety regression test; dashboard UI (toggles, watch-list, schedule, findings view).

**Out (→ Sub-project B, brainstormed next):** autonomous *action* personas on schedules, wired
through the safety classifier + trust + approval queue + executor, plus an approvals UI.

## Open questions / risks

- **Free-model JSON reliability.** Weak OpenRouter models may emit imperfect JSON; the tolerant
  extractor + digest fallback contain this, but early real-world runs should be eyeballed. Better
  models (planned infra) sharpen it.
- **Cadence vs. cost.** Daily scout runs = daily web-research LLM calls. 07:00 UTC daily is the
  default; the UI lets the user dial frequency down. Cost-conscious by design.
- **Timezone.** Schedules are UTC (matching all existing crons); the UI should show the user's
  local equivalent to avoid confusion.
