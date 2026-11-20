# Approvals Feed — Unified Human-in-the-Loop Queue — Feature Spec

> **Status: Built.** Implemented in `life_graph/api/approvals.py`. This document records the design as it was specified; for what the code actually does now, see [docs/STATE.md](../STATE.md) — it is generated from the code.

> 🚧 **STATUS: SPEC / PHASE 4 of the mobile app build (July 2026).** New migration `026_approvals.py`; new `models/db.py` `Approval`; new `services/approvals.py`; new `api/approvals.py` (prefix `/approvals`); tests `tests/integration/test_approvals.py`. Frontend consumed by the mobile app's Approvals tab (`dashboard/app/(mobile)/m/approvals`). **Scope for this phase: the durable table + API + events + tests, populated from ONE real source (`self_improving` promotions awaiting review). The other three sources are specified as follow-up producers and are NOT built in this phase.**
>
> **Purpose**: Give the human one place to see and resolve everything the system has queued for their decision. Today there is no such place — pending items are scattered: `self_improving` promotions sit in `optimization_runs.status='needs_review'`; dedup merges and contradiction resolutions happen automatically with no gate; weekly-review drafts are generated on demand. This feature introduces a **polymorphic `approvals` table** that any subsystem can enqueue into, plus a small API to list and resolve items, with the resolution triggering the source's real side-effect.
>
> **Architecture ref**: `KNOWLEDGE.md`. **Not to be confused with** `autonomy/models.py::ApprovalQueueEntry` (table `approval_queue`) — that is the Era-8 autonomous-shell-command HITL queue and stays as-is. This new `approvals` table is for *content* decisions (memory/judgment/self-improvement/brief). (Note: the mounted `/autonomy/approvals` router has a pre-existing model-mismatch bug — out of scope here, tracked separately.)
>
> **Multi-tenant**: All data scoped by `tenant_id`. Every query filters by it.

---

## Scope

**In (this phase):**
- `approvals` table + `Approval` model + migration `026`.
- `GET /approvals`, `POST /approvals/{id}/approve`, `POST /approvals/{id}/reject`.
- `APPROVAL_REQUESTED` / `APPROVAL_RESOLVED` events + WebSocket fan-out.
- **One producer**: enqueue an approval when a `self_improving` optimization run enters `needs_review`; approving activates the candidate prompt version, rejecting marks the run rejected.
- Reconcile-on-list backfill so pre-existing `needs_review` runs appear (idempotent by `source` + `source_ref`).
- Mobile Approvals tab wired to the API (replaces mock).

**Out (follow-up producers, specified but not built):**
- **Curator merges** — requires changing dedup from auto-merge to gated; new producer at the dedup decision point in `core/memory_manager.py`.
- **Judgment contradictions** — requires persisting `services/contradiction.py` results when resolution is `ask_user`.
- **Scribe weekly review** — requires a draft-before-send flow in `services/brief.py` / `watchers/digest.py`.
  Each writes an `approvals` row with the appropriate `kind`; the table and API are designed to receive them with no schema change.

---

## Requirements

### Story 1: A single feed of what needs me

As a **user**, I want one list of everything awaiting my decision, newest first, so I never have to hunt across subsystems.

#### Acceptance Criteria

- GIVEN pending items exist WHEN I `GET /api/v1/approvals?status=pending` THEN I get them tenant-scoped, newest first, each with `{id, kind, title, detail, status, source, created_at}`.
- GIVEN I pass `?status=all` or omit it THEN resolved items are included (for history); default is `pending`.
- GIVEN the backend is unreachable WHEN the mobile tab loads THEN it shows the error card (never a 422 for a valid request — 500 acceptable when the DB is down, per test convention).
- GIVEN `self_improving` has runs in `needs_review` that predate this feature WHEN I list approvals THEN they appear exactly once (reconcile is idempotent on `(tenant_id, source, source_ref)`).

### Story 2: Resolve in one tap, with the real side-effect

As a **user**, I want Approve/Reject to actually do the thing, not just mark a row.

#### Acceptance Criteria

- GIVEN a pending approval WHEN I `POST /approvals/{id}/approve` with optional `{note, resolved_by}` THEN its status becomes `approved`, `resolved_at`/`resolved_by`/`resolution_note` are set, and the **kind-specific side-effect runs**.
- GIVEN a `kind='promotion'` approval is approved THEN the candidate prompt version is activated (via `self_improving` prompt-version service) and the linked `optimization_run` is marked reviewed/approved.
- GIVEN I `POST /approvals/{id}/reject` THEN status becomes `rejected`, no activation happens, and a `promotion` rejection marks the `optimization_run` rejected.
- GIVEN I resolve an already-resolved approval WHEN I call approve/reject again THEN it returns 409 (idempotent guard — no double activation).
- GIVEN any resolution WHEN it completes THEN `APPROVAL_RESOLVED` is emitted (payload `{id, kind, status, tenant_id}`); the WebSocket bridge relays it so the mobile tab and badge refresh.

---

## Data model — migration `026_approvals.py`

```sql
CREATE TABLE approvals (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     VARCHAR(64) NOT NULL DEFAULT 'legacy',
    kind          VARCHAR(32) NOT NULL,        -- 'promotion' | 'merge' | 'contradiction' | 'weekly_review'
    title         TEXT        NOT NULL,        -- "Promote synthesizer v6 to active"
    detail        TEXT,                        -- "optimizer · +3.1% vs v5 across 48 judged cases"
    status        VARCHAR(16) NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','approved','rejected')),
    source        VARCHAR(32) NOT NULL,        -- producing subsystem: 'self_improving' | 'curator' | 'judgment' | 'scribe'
    source_ref    VARCHAR(128),                -- id of the originating record (e.g. optimization_run id)
    payload       JSONB       NOT NULL DEFAULT '{}'::jsonb,  -- kind-specific data (candidate_version_id, similarity, …)
    priority      INTEGER     NOT NULL DEFAULT 0,
    resolved_by   VARCHAR(128),
    resolution_note TEXT,
    resolved_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_approvals_tenant_status ON approvals (tenant_id, status);
CREATE UNIQUE INDEX uq_approvals_source_ref ON approvals (tenant_id, source, source_ref)
    WHERE source_ref IS NOT NULL;  -- idempotent producer/reconcile
```

`Approval` model in `models/db.py` follows the core convention: `UUID` PK (`default=uuid.uuid4`), `tenant_id` `String(64)`, timestamps `DateTime(timezone=True)` with `_utcnow`, `JSONB` payload. `CheckConstraint` on status. Indexes in `__table_args__`.

---

## API — `api/approvals.py` (prefix `/approvals`, mounted on v1_router)

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/approvals` | `?status=pending\|all&limit=100` | `success_response([{id,kind,title,detail,status,source,created_at}])` |
| POST | `/approvals/{id}/approve` | `{note?, resolved_by?, retry?}` | `success_response({id,status:'approved'})` |
| POST | `/approvals/{id}/reject` | `{note?, resolved_by?}` | `success_response({id,status:'rejected'})` |

- Tenant via `Depends(get_current_tenant_id)`; DB via `async_session()`; responses via `success_response`.
- `GET` runs the promotions **reconcile** first (upsert `needs_review` runs → approvals) then returns the list.
- Resolve endpoints: load tenant-scoped row → 404 if missing, 409 if already resolved → set fields → run `kind` side-effect → commit → `event_bus.emit(APPROVAL_RESOLVED, …)`.

---

## Service — `services/approvals.py`

- `ApprovalService(session, event_bus)`.
- `list_pending(tenant_id, status, limit)`.
- `reconcile_promotions(tenant_id)` — read `optimization_runs` where `status='needs_review'`; for each, `INSERT … ON CONFLICT (tenant_id,source,source_ref) DO NOTHING` an approval with `kind='promotion'`, `source='self_improving'`, `source_ref=run.id`, title/detail from run fields, `payload={candidate_version_id, previous_version_id, candidate_accuracy_pct}`. **Verify real column names against `self_improving/models.py` at build time** (the explorer flagged a field/method mismatch in the existing review router — do not trust it; read the model).
- `resolve(tenant_id, approval_id, decision, note, resolved_by)` — guard already-resolved (409); on approve+`kind='promotion'` call the prompt-version activate method (confirm its real name — `activate` vs `activate_version`) and mark the run; emit event.
- Side-effect dispatch keyed by `kind` so follow-up producers slot in.

### At-most-once execution (added 2026-11-20, audit P0)

Kinds whose approve side effect lives outside the approval's transaction
(`driver_pr`, `driver_merge`, `driver_deploy`, `driver_plan`,
`autonomous_action`) commit an execution claim before the effect runs:
`payload.execution = {state: "started", attempt_id, attempt, started_at, by}`.
`status` stays `pending` until the effect finishes, so every client keeps
listing the item. Then:

- success: `status='approved'`, `execution.state='done'`;
- the effect raised `ApprovalActionError`: `state='failed'` (with `error`);
  anything else: `state='unknown'`; the item stays pending;
- the process died before the commit: `state` stays `started`; the 15-minute
  `sync_dev_task_prs` job (`flag_stale_claims`) turns a claim older than the
  longest possible run (1 h; more for a deploy with a long smoke timeout) into
  `unknown` and notifies the owner.

While `started` (not stale), approve and reject both answer 409 "being
applied". After `failed`/`unknown`, reject is allowed; approve runs again only
if that is harmless (`driver_pr`, `driver_merge`: re-runs find the PR open or
already merged; `driver_plan` after a `failed` pre-check), otherwise 409 until
the owner sends `{"retry": true}`. The auto-merge sweep never retries a row
whose claim is `started` or `unknown`. Kinds that only change rows in the same
transaction (memory merges, archives, contradictions, promotions, entity
aliases, model adoption) take no claim: a crash rolls their effect back with
the status.

### Which store is authoritative per kind (added 2026-11-20, audit H9)

Three tables hold approval-shaped state. Each kind has exactly one place
where its decision is made and one where its side effect runs:

| Kind / item | Decision recorded in | Side effect runs from | Copy elsewhere |
|---|---|---|---|
| `promotion`, `merge`, `archive`, `contradiction`, `entity_alias`, `model_adoption` | `approvals` | `approvals` resolve, same transaction | none |
| `driver_pr`, `driver_merge`, `driver_deploy`, `driver_plan` | `approvals` | `approvals` resolve, with the execution claim | none |
| autonomy action with an `AutoAction` (pipeline queue, notify-before) | `approval_queue` (the decision of record; the `approvals` copy says the same) | **only** the `approvals` approve of its `kind="autonomous_action"` copy (claim + command pin + kill switch, `AutoFixService.execute_pending`) | `approvals` row, `source_ref` = queue id |
| autonomy queue entry with no action (dev-task "review task …", driver verification failed/unavailable) | `approval_queue` | nothing runs | none |
| errand step mandates | `capabilities` (autonomy/approvals/capability.py) | the errand executor spends them | none |

Rules that keep the two copies of an autonomy action in step:

- **Queue → feed.** Every resolution on the queue side closes the copy in the
  same transaction: `ApprovalService.resolve`, `batch_resolve`,
  `expire_stale` (status mapping: approved/batch_approved → `approved`;
  rejected/expired/stale → `rejected`; `resolved_by` copied; the note starts
  "Resolved in autonomy queue (<status>)"). Lock order is copy first, then
  queue row, the same order the feed side takes, so the two cannot deadlock.
  If the copy is locked or carries a running execution claim, the queue side
  answers 409 (single/batch) or leaves the entry for the next pass (cron).
- **Feed → queue.** Resolving the copy resolves the queue entry
  (`_apply_autonomous_action`, with `close_feed=False` because the copy is the
  row being resolved), then on approve runs the action.
- **The queue routes hand off.** `POST /autonomy/approvals/{id}/resolve` and
  `/batch` decide an entry that has a pending copy naming an `AutoAction`
  through the copy (`resolve_feed_copy`), so approving from either list runs
  the action the same way. Before 2026-11-20 approving in the queue marked it
  approved and ran nothing, and the copy stayed pending. In a batch, such
  entries are decided one by one after the plain entries' single
  transaction; per-entry failures come back in `failed`.
- **Disagreement is a conflict, not a success.** Deciding the copy when the
  queue already decided the other way answers 409
  (`ApprovalConflictError`): approve after the queue rejected or went stale,
  or reject after the queue approved. One exception: rejecting a copy whose
  own earlier attempt approved the queue and then failed or never reported
  (it carries an execution claim) is the owner abandoning that attempt, as
  in the at-most-once rules above; the queue entry stays approved as that
  attempt left it. Deciding the same way again is a harmless repeat.
- **No timer approves anything.** A notify-before entry's window
  (`expires_at`, 5 min) ending no longer auto-approves it: the window is
  cleared, the entry and its copy stay pending, and the owner is notified
  (CHARTER.md §5, fail-closed). The 14-day stale rule still applies.
- **Repair.** `reconcile_feed_copies` (every 5 min, with the timeout cron)
  closes copies left pending by entries resolved before these rules,
  except an approved entry whose action is still `pending`: approving its
  copy runs it.
- **Stops revoke mandates.** Pausing autonomy and cancelling a dev task
  revoke the live capabilities of that tenant / task
  (`revoke_live_capabilities`). The stop is committed first; if the
  capability store is down the route answers 503 saying the stop happened
  and the revocation did not (pause/cancel again to retry).

---

## Events — `core/events.py`

- Add `APPROVAL_REQUESTED = "approval:requested"`, `APPROVAL_RESOLVED = "approval:resolved"` to `EventType`.
- Emit via `await event_bus.emit(...)` (note: `emit`, not `publish`).
- Frontend `use-websocket.ts` `EVENT_MAP`: add `"approval": ["approvals"]` so the mobile query invalidates on resolve.

---

## Frontend wiring — mobile Approvals tab

- `lib/api.ts`: add `approvals.list(status)`, `approvals.approve(id, body)`, `approvals.reject(id, body)`.
- `lib/mobile-api.ts`: `useApprovals()` (GET pending) + `useResolveApproval()` mutation; map to the existing `ApprovalMock` shape (`{id, title, detail}`) plus `status`.
- `app/(mobile)/m/approvals/page.tsx`: replace mock list with `useApprovals()`; Approve/Reject call the mutation; keep the resolved-pill UI; loading/empty/error states.
- `mobile-state.tsx`: `openApprovalsCount` derives from the live pending query (via queryClient cache) instead of the mock array; the tab badge stays live.

---

## Tasks

1. `models/db.py`: add `Approval` (+ `CheckConstraint`, indexes).
2. `alembic/versions/026_approvals.py` (`down_revision="025"`): create table + indexes.
3. `services/approvals.py`: service (list, reconcile_promotions, resolve + promotion side-effect).
4. `core/events.py`: add the two `EventType` members.
5. `api/approvals.py`: router; mount on `v1_router` in `main.py`.
6. `tests/integration/test_approvals.py`: list (empty ok / 500 ok, never 422), approve transitions + 409 on re-resolve, reject, tenant isolation.
7. Frontend: `api.ts`, `mobile-api.ts` hooks, approvals page, badge source.
8. Verify: `pytest tests/integration/test_approvals.py -v`; `npm run build`; Playwright smoke of `/m/approvals`.

---

## Follow-up (out of scope, for later specs/producers)

- **Merges** — ✅ IMPLEMENTED (additive, July 2026): nightly `services/merge_suggestions.py` + `workers/tasks.run_all_merge_suggestions` (cron 03:45) scans active memory pairs whose similarity lands in `[merge_review_low, dedup_threshold)` — near-dupes below the auto-merge line — and queues `kind='merge'` approvals (idempotent per pair). Approve merges them (`ApprovalService._apply_merge`: higher importance wins, tags unioned, loser superseded); reject dismisses. Changes no existing auto-merge behavior. Tests: `tests/integration/test_merge_suggestions.py`.
- **Contradictions** — ✅ IMPLEMENTED (additive review/undo, July 2026): ingest still auto-supersedes, but `MemoryManager._queue_contradiction_approval` records each as a `kind='contradiction'` approval. Approve confirms (no-op); reject UNDOES the supersede (restores the old memory to active, clears the chain) via `ApprovalService._apply_contradiction`. No change to auto-resolution. Tests: `tests/integration/test_contradiction_producer.py`.
- **Weekly review** — ⏭️ deferred by decision (July 2026): the weekly digest already auto-delivers as a notification, so a producer would be redundant (additive) or a behavior change (draft-before-send). The `approvals` table stays ready to receive `kind='weekly_review'` if a review-before-send gate is wanted later.
