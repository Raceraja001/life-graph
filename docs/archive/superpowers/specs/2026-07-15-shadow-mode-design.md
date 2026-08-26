# Shadow Mode — Dry-Run Rung on the Autonomy Ladder (Track 3, Increment 1)

> **Date:** 2026-07-15
> **Status:** Approved — ready for implementation planning
> **Backlog:** `docs/design/09_operational_hardening_backlog.md` Track 3
> **Strategic basis:** `docs/design/07_strategic_direction_2026-07.md` §D7.4 (Shadow Mode)

## Problem

The Era-8 autonomy ladder lets an actor act for real as soon as its project reaches
the right autonomy level (`pipeline/service.py` routes `auto_executed` when
`risk == safe and autonomy_level >= 1`). A **brand-new** persona or pipeline can
therefore take real, side-effecting actions before it has ever demonstrated it would
do the right thing. There is no dry-run rung: nothing forces a new actor to prove
itself on "would-have-done" reports first.

## Goal

No **new** autonomous actor acts for real until it has accumulated a **graded shadow
track record**. New actors run in dry-run (Shadow Mode): the pipeline records what they
*would have done* instead of executing it. The user grades each would-have-done; grades
feed the Era-8 trust calculator and drive graduation. Already-proven actors are
grandfathered and unaffected.

**Decisions locked in brainstorming:**
- **Enrollment**: new actors only (default-deny for actors with no track record);
  actors with prior successful history are grandfathered.
- **Graduation**: soak + samples + good-rate (all three required).

## Design

### 1. Pure policy — `life_graph/core/shadow.py` (single source of truth)

No DB/IO (mirrors `core/trust.py`, `core/budget.py`):

- `class ShadowGrade(str, Enum)`: `GOOD = "good"`, `BAD = "bad"`.
- **`should_graduate(days_enrolled, graded_good, graded_bad, *, min_days=14, min_samples=5,
  good_rate_threshold=0.8) -> bool`** — true only when ALL hold:
  - `days_enrolled >= min_days`
  - `graded_good >= min_samples`
  - `good_rate >= good_rate_threshold`, where
    `good_rate = graded_good / (graded_good + graded_bad)` (0.0 when ungraded).
- `good_rate(graded_good, graded_bad) -> float` helper.

### 2. Data model — migration `024_shadow_mode`

**`shadow_enrollments`** (public schema):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | String(64) | |
| `agent_id` | Text | the shadowed actor (persona/agent/pipeline) |
| `status` | String(16) | `shadow` \| `graduated` |
| `enrolled_at` | timestamptz | |
| `graduated_at` | timestamptz? | |
| `graded_good` | Integer | running tally |
| `graded_bad` | Integer | running tally |

Unique `(tenant_id, agent_id)`; index `(tenant_id, status)`.

**`shadow_runs`** (public schema) — the would-have-done records:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | String(64) | |
| `agent_id` | Text | |
| `enrollment_id` | UUID FK → shadow_enrollments | |
| `action_type` | Text | |
| `command` | Text | what it WOULD have run |
| `risk_level` | Text? | |
| `project_id` | Text? | |
| `would_have_routed` | String(32) | e.g. `auto_executed` |
| `rationale` | JSONB | classification / metadata snapshot |
| `grade` | String(8)? | null \| `good` \| `bad` |
| `graded_at` | timestamptz? | |
| `graded_by` | Text? | |
| `created_at` | timestamptz | |

Index `(tenant_id, agent_id)`, `(tenant_id, grade)`.

### 3. Service — `life_graph/autonomy/shadow/service.py`

- `intercept(tenant_id, agent_id) -> ShadowDecision(shadow: bool, enrollment)`:
  - Look up the `(tenant_id, agent_id)` enrollment.
  - If none: decide grandfather vs shadow. **Grandfather** (create `status=graduated`) when
    the actor has ≥1 prior `AutoAction` with `status="success"`; otherwise create
    `status=shadow`. Records the decision so it is stable thereafter.
  - Return `shadow = (enrollment.status == "shadow")`.
- `record_would_have_done(enrollment, *, action_type, command, risk_level, project_id,
  would_have_routed, rationale) -> ShadowRun` — writes the dry-run record; **no execution**.
- `grade(shadow_run_id, grade: ShadowGrade, graded_by) -> GradeResult`:
  - Set `grade`, `graded_at`, `graded_by` on the run (idempotent — re-grading adjusts tallies).
  - Bump `graded_good`/`graded_bad` on the enrollment.
  - **Feed the Era-8 trust calculator**: `TrustService.record_success` (good) /
    `record_failure` (bad) for the actor.
  - Call `should_graduate(...)`; on pass → set `status=graduated`, `graduated_at`, emit
    `SHADOW_GRADUATED` event + a notification.
- `list_runs(tenant_id, status="ungraded", limit)` — the grading queue.

### 4. Pipeline integration — the one gate (`autonomy/pipeline/service.py`)

In the routing block, the `auto_executed` branch (pure-autonomous, no human) first calls
`shadow.intercept(tenant_id, agent_id)`. If shadowed:
- `routing = "shadow_recorded"`,
- `record_would_have_done(...)` with the classified action,
- set `AutoAction.status = "shadow"`,
- **skip `_auto_execute` entirely** — no `CommandExecutor` call, no side effects.

Otherwise, existing behavior. The approval/notify routes already have a human in the loop,
so this increment shadows only the autonomous-execute path.

Shadow interception is gated by `settings.shadow_mode_enabled` (default True); when off,
behavior is exactly as today.

### 5. Config

`shadow_mode_enabled: bool = True`, `shadow_min_days: int = 14`,
`shadow_min_samples: int = 5`, `shadow_good_rate: float = 0.8`.

### 6. Grading surface — `autonomy/shadow/router.py`

- `POST /autonomy/shadow/runs/{id}/grade` body `{grade: good|bad}` → grades a run.
- `GET /autonomy/shadow/runs?status=ungraded&limit=` → the queue.
- `GET /autonomy/shadow/enrollments` → actor states + progress toward graduation.

Router registered in `main.py`. The one-tap dashboard button is out of scope (API only).

### 7. Testing (unit now; live DB deferred per agreement)

`tests/unit/test_shadow.py` (pure `should_graduate`):
1. All-criteria-met graduates; each single unmet criterion blocks (days short, samples
   short, rate short).
2. Boundaries: exactly `min_days`, exactly `min_samples`, exactly `good_rate_threshold`.
3. Ungraded (`good = bad = 0`) never graduates; `good_rate` division-by-zero → 0.0.

`tests/unit/test_shadow_service.py` (fake session):
4. `intercept`: new actor → shadow; actor with a prior successful AutoAction → grandfathered.
5. `grade`: updates tallies, calls the trust calculator, fires graduation at the bar.

`tests/unit/test_pipeline_shadow.py`:
6. **Enforcement invariant**: a shadowed actor's `auto_executed` route records a
   would-have-done and **never calls `CommandExecutor.execute`**; a graduated actor does execute.

## Files touched (estimate)

- New: `life_graph/core/shadow.py`, `life_graph/autonomy/shadow/` (service, router, schemas,
  `__init__`), `alembic/versions/024_shadow_mode.py`, 3 test files.
- Edited: `life_graph/autonomy/models.py` (2 models) or `models/db.py`, `config.py` (4 settings),
  `autonomy/pipeline/service.py` (the gate), `main.py` (router), `core/events.py`
  (`SHADOW_GRADUATED`).

## Out of scope (later increments)

Dashboard one-tap grading UI; demotion back to shadow on a post-graduation failure;
shadowing the approval/notify routes; auto-expiry of ungraded runs; per-action-type
(rather than per-actor) shadow scoping.
