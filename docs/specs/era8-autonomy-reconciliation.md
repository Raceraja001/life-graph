# Era-8 Autonomy — Model/Code Reconciliation — Remediation Spec

> 🚧 **STATUS: SPEC ONLY — NOT BUILT.** Discovered July 2026 while auditing the pre-existing
> `/autonomy/approvals` bug during the mobile-app build. Scope grew on inspection: the entire
> Era-8 autonomy execution path — pipeline, approvals, dispatcher producers, and their Pydantic
> schemas — was written against **field names and model classes that do not exist**. None of it
> can run. This spec captures the divergence and the remediation so it can be done on its own
> branch, off the mobile work.
>
> **Not to be confused with** `docs/specs/approvals-feed.md` / `api/approvals.py` (the new
> `/api/v1/approvals` mobile HITL feed backed by the `approvals` table). That feature is healthy,
> shipped, and **separate**. This spec is about the Era-8 `/api/v1/autonomy/*` subsystem backed by
> the `auto_actions` / `approval_queue` / `trust_scores` tables in `life_graph/autonomy/models.py`.
>
> **Multi-tenant**: every query filters by `tenant_id` (unchanged requirement).

---

## Problem

The Era-8 autonomy subsystem (migration for `auto_actions`, `approval_queue`, `action_safety_rules`,
`trust_scores`, `audit_log`, `autonomy_levels`, `shadow_*`) has real SQLAlchemy models in
`life_graph/autonomy/models.py`. But the **routers, services, dispatcher producers, and schemas**
that drive it reference a different, imaginary schema. Three independent failures compound:

1. **Phantom imports.** Every producer/consumer does
   `from life_graph.models.db import AutoAction` (or `ApprovalQueue`). Neither symbol exists in
   `models/db.py` — the "expose autonomy models" block at `models/db.py:2446` is an **empty
   comment**. The real classes are `life_graph.autonomy.models.AutoAction` and
   `life_graph.autonomy.models.ApprovalQueueEntry` (note the `Entry` suffix; there is no
   `ApprovalQueue`). Each import raises `ImportError` **at call time** (imports are function-local,
   so app startup survives — the endpoints simply 500 on first use).

2. **Wrong field names on `AutoAction`.** The code invents columns the model does not have.

3. **Wrong field names on `ApprovalQueueEntry`**, in **two mutually inconsistent** variants (the
   approvals service/router use one set; `drivers/dispatcher.py` invents yet another).

Because every path dead-ends at an `ImportError` or `AttributeError`, this code has **never
executed against the real database**. There are no live consumers to preserve — which makes the
rewrite low-risk, but also means it is a genuine build, not a patch.

### Affected mounted endpoints (all currently dead)

- `POST /api/v1/autonomy/pipeline` — `AutoFixService.process` (classify → route → execute/queue)
- `GET  /api/v1/autonomy/actions` — `pipeline/router.py::list_auto_actions`
- `GET  /api/v1/autonomy/approvals`, `POST …/{id}/resolve`, `POST …/batch`
- Producers: `drivers/dispatcher.py::_create_approval_entry` / `_create_dissent_approval_entry`

---

## Evidence — field divergence

### `AutoAction` (real model `autonomy/models.py:82`, table `auto_actions`)

| Code uses (`pipeline/schemas.py`, `pipeline/service.py`) | Real model field | Note |
|---|---|---|
| `action_type` | `action_name` | rename |
| `command` | `action_command` | rename |
| `description` | *(none)* | nearest is `trigger_detail` |
| `timeout_seconds` | *(none)* | executor timeout must live elsewhere |
| `metadata` | *(none)* | **`metadata` is reserved by SQLAlchemy declarative — cannot be a column** |
| `executed_at` | *(none)* | real: `queued_at` / `started_at` / `completed_at` |
| — (not supplied) | `trigger_type` **NOT NULL** | code never sets it → insert would fail |
| — (not supplied) | `trigger_detail` **NOT NULL** | code never sets it → insert would fail |
| *(unused)* | `before_state`, `after_state`, `is_reversible`, `rollback_action_id`, `error_message`, `approved_by`, `approved_at` | real columns the code ignores |

`rollback_command`, `risk_level`, `exit_code`, `stdout`, `stderr`, `duration_ms`, `approval_id`,
`status`, `agent_id`, `project_id`, `id`, `tenant_id`, `created_at` **do** line up.

### `ApprovalQueueEntry` (real model `autonomy/models.py:262`, table `approval_queue`)

| Code uses | Real model field | Note |
|---|---|---|
| `action_id` (approvals svc/router/schema) | *(none)* | link is **reverse**: `AutoAction.approval_id → approval_queue.id` |
| `action_type` | `action_name` | rename |
| `command` | `action_command` | rename |
| `description` | *(none)* | real: `trigger_detail` / `estimated_impact` |
| `decision_note` | `resolution_note` | rename |
| `escalation_level` (int) | `escalation_sent` (JSONB list) | different type + semantics |
| `action_description` (dispatcher) | *(none)* | dispatcher's private invention |
| `context` (dispatcher) | *(none)* | dispatcher's private invention |
| — (not supplied) | `trigger_type`, `trigger_detail` **NOT NULL** | producers never set them → insert fails |

`agent_id`, `project_id`, `risk_level`, `status`, `resolved_by`, `resolved_at`, `expires_at`,
`created_at`, `id`, `tenant_id` line up. `category` (NOT NULL, default `general`), `priority`,
`also_trust`, `batch_id`, `timeout_hours` are real columns the code ignores.

### PK type mismatch

Both real PKs are `Text` (uuid **string**), but the Pydantic schemas declare `id: UUID` /
`action_id: UUID` and `BatchResolveRequest.approval_ids: list[UUID]`. Comparisons like
`ApprovalQueueEntry.id.in_(uuid_objects)` against a `Text` column are fragile — switch schema id
fields to `str`.

---

## The one decision: which side is authoritative?

**Recommendation: the models win. Rewrite the code to the models; do not migrate the tables.**

Rationale:
- The models have a **migration and real tables**; changing them means a new Alembic revision plus
  risk to any rows already written by other Era-8 paths (safety rules, trust scores, shadow runs
  are all in the same module and may be populated).
- The code has **never run**, so rewriting it destroys no working behavior and needs no migration.
- `metadata` **cannot** be a declarative column name at all — so "make the model match the code" is
  not even fully possible without renaming the code's field too.

Everything below assumes models-authoritative.

---

## Scope

**In:**
- Fix the phantom imports: import `AutoAction` / `ApprovalQueueEntry` from `life_graph.autonomy.models`
  (or populate the `models/db.py:2446` re-export block and keep imports there — pick one, below).
- Rewrite `pipeline/schemas.py`, `pipeline/service.py`, `pipeline/router.py` to real `AutoAction` fields.
- Rewrite `approvals/schemas.py`, `approvals/service.py`, `approvals/router.py` to real
  `ApprovalQueueEntry` fields; wire the `AutoAction`↔approval link via `AutoAction.approval_id`.
- Fix `drivers/dispatcher.py` producers to real `ApprovalQueueEntry` fields (set the NOT NULL
  `trigger_type` / `trigger_detail`; drop `action_description` / `context` or map them into
  `trigger_detail` / a real JSON column).
- Integration tests for the pipeline route and the approvals resolve/list/batch paths (house
  convention: 500 acceptable when DB is down, never 422 for valid input).

**Out:**
- Any change to `autonomy/models.py` or the tables (unless a genuinely missing field surfaces —
  e.g. an executor-timeout column — in which case add it via a **new** migration, not by editing 026-era files).
- Trust/level/safety/shadow/audit modules, except where the pipeline calls them (verify those call
  signatures — `audit_service.log_approval`, `log_auto_execute`, `level_service.record_action` —
  actually exist and match; the same rot may be present there).

---

## Requirements

### Story 1: The pipeline can classify and record an action
- GIVEN a valid `POST /autonomy/pipeline` body WHEN processed THEN an `auto_actions` row is written
  with all NOT NULL columns populated (`action_name`, `action_command`, `trigger_type`,
  `trigger_detail`, `status`) and no `AttributeError`/`ImportError`.
- GIVEN the executor needs a timeout THEN it is sourced from a real place (request field mapped to a
  real column or passed through without persisting to a non-existent `timeout_seconds` column).

### Story 2: The approvals feed lists and resolves against the real table
- GIVEN pending `approval_queue` rows WHEN `GET /autonomy/approvals` THEN they return, tenant-scoped,
  newest first, serialized from real fields (no `action_id` / `decision_note` / `escalation_level`).
- GIVEN a pending approval WHEN `POST /autonomy/approvals/{id}/resolve` with `{decision, note, resolved_by}`
  THEN `status→approved|rejected`, `resolution_note`/`resolved_by`/`resolved_at` set, and the linked
  `AutoAction` (found via `AutoAction.approval_id == entry.id`) is updated to `approved`/`rejected`.
- GIVEN an already-resolved approval THEN re-resolve is rejected (guard on `status != 'pending'`).

### Story 3: Producers enqueue valid rows
- GIVEN the dispatcher needs human review WHEN it creates an approval THEN the row satisfies every
  NOT NULL column and is later listable/resolvable through Story 2.

---

## File-by-file remediation

1. **Import strategy (pick one, apply everywhere):**
   - *Preferred:* import directly from `life_graph.autonomy.models` in each site and delete the dead
     `models/db.py:2446` comment. Explicit, no indirection.
   - *Alternative:* fill the re-export block — `from life_graph.autonomy.models import AutoAction, ApprovalQueueEntry as ApprovalQueue` — to satisfy existing imports with the fewest edits. Rejected
     unless minimizing diff matters more than clarity, because the `ApprovalQueue` alias perpetuates a
     misleading name.

2. **`pipeline/schemas.py`** — `AutoFixRequest`: keep the caller-facing `action_type`/`command`/
   `description`/`timeout_seconds` as **API** fields (they are a reasonable external contract), but map
   them in the service to `action_name`/`action_command`/`trigger_detail` + `trigger_type`. `AutoActionResponse`: serialize from real fields; drop `metadata`; `id: str`.

3. **`pipeline/service.py`** — in `process`, construct `AutoAction(action_name=…, action_command=…,
   trigger_type=<request.action_type or "manual">, trigger_detail=<request.description>, …)`; set
   `queued_at`/`started_at`/`completed_at` instead of `executed_at`; stop passing `metadata` /
   `timeout_seconds` to the model (thread the timeout to the executor as a local). Fix every
   `auto_action.action_type/.command/.description` read in `_auto_execute`, `_notify_before_execute`,
   `_queue_for_approval`, `_record_shadow`, `_record_result`.

4. **`pipeline/router.py`** — `list_auto_actions` already selects on real-ish fields; fix its
   response mapping to the corrected `AutoActionResponse`.

5. **`approvals/schemas.py`** — `ApprovalResponse` → real fields (`action_name`, `action_command`,
   `trigger_detail`, `estimated_impact`, `category`, `priority`, `resolution_note`, `escalation_sent`,
   `timeout_hours`); ids `str`. `ResolveRequest`/`BatchResolve*` ids `str`.

6. **`approvals/service.py`** — import real models; `create` builds a valid `ApprovalQueueEntry`
   (all NOT NULL set); `resolve`/`batch_resolve` use `resolution_note`; the AutoAction side-effect
   finds the action by `AutoAction.approval_id == entry.id` (there is no `entry.action_id`);
   `check_expirations` likewise; `send_escalations` reworked around `escalation_sent` (append the
   crossed threshold to the JSONB list) instead of an integer `escalation_level`.

7. **`approvals/router.py`** — import `ApprovalQueueEntry`; fix the `list` serialization; endpoints
   otherwise fine.

8. **`drivers/dispatcher.py`** — `_create_approval_entry` / `_create_dissent_approval_entry`:
   construct `ApprovalQueueEntry(action_name=…, action_command=…, trigger_type="driver_review",
   trigger_detail=<the human sentence>, category="driver", agent_id=driver_name, status="pending", …)`;
   drop `action_description`/`context` (fold the concern/failures into `trigger_detail` or a real
   JSON column such as `estimated_impact`).

9. **Sibling call-signature audit** — before finishing, confirm `AuditService.log_approval` /
   `log_auto_execute`, `TrustService`, `AutonomyLevelService.record_action` signatures match their
   call sites; the same never-run rot may live there.

---

## Testing

- `tests/integration/test_autonomy_pipeline.py` — `POST /autonomy/pipeline` writes a valid row; list
  returns it; defensive (500 on DB down, never 422).
- `tests/integration/test_autonomy_approvals.py` — seed an `approval_queue` row → list → resolve →
  status flips + linked `AutoAction` updated; re-resolve guarded; batch resolve; tenant isolation.
- Reuse `tests/integration/conftest.py::skip_on_db_error`. **Gotcha (from the mobile build):**
  `conftest.py` swaps a fake Vector type when pgvector isn't pre-imported — irrelevant here (no
  embeddings) but keep tests embedding-free so they run under pytest.

## Tasks

1. Decide + apply the import strategy; delete/fill `models/db.py:2446`.
2. Rewrite pipeline schemas + service + router; verify NOT NULL coverage.
3. Rewrite approvals schemas + service + router; wire the reverse AutoAction link.
4. Fix dispatcher producers.
5. Audit sibling service signatures.
6. Add the two integration test modules.
7. `ruff check life_graph/autonomy life_graph/drivers`; `pytest tests/integration/test_autonomy_*.py -v`.
8. Manual smoke against a real DB (a running instance on a non-Apache port — 8080 is squatted):
   `POST /autonomy/pipeline` then `GET /autonomy/approvals`.

## Risks / notes

- **No live consumers** (everything currently 500s), so the rewrite breaks nothing — but also means
  no golden behavior to diff against; the models + these stories are the only contract.
- Watch the `metadata` trap: never reintroduce it as a column.
- Keep this **entirely separate** from `api/approvals.py` / the `approvals` table — same English word,
  different subsystem.
