# Memory Approval Gate — every memory waits for the user's yes

> **Date:** 2026-07-23
> **Status:** Approved design — ready for implementation planning
> **Scope:** `models/db.py` + Alembic migration 022, `storage/postgres.py`, `storage/hybrid.py`,
> `core/memory_manager.py`, `api/memories.py`, `api/multimodal.py` (indirect), agent/recall
> call sites, `dashboard/` (minimal pending UI). Deployed at `brain.raceraja001.in`.
> **Sequence:** first of three workstreams (C approval gate → A reactive UI → B chat distillation).

## Problem

Everything that lands in Life Graph today becomes canonical immediately — captures,
extraction facts, fallback rows, and (soon) bulk-distilled knowledge from AI chat
conversations. The user wants control: **no memory becomes trusted without explicit
approval**. With bulk distillation coming (workstream B), an unreviewed pipeline would
pollute the graph; the gate must exist first.

## Decisions (locked with user)

- **Everything is gated.** Every new memory from every source starts `pending` —
  including the user's own text/voice/photo captures. Maximum control over less tapping.
- **Visible but marked.** Pending memories appear in the user's own lists and searches
  with a clear pending badge; **agents, recall context, watchers, daily brief, and any
  automation consume approved memories only.**
- **No auto-expiry.** Pending memories wait indefinitely; the daily brief mentions the
  backlog count. (Kernel approval timeouts remain for agent actions — unrelated.)
- **Reject is soft.** Rejected rows keep `status='rejected'`, excluded everywhere; no
  hard delete in v1.

## Non-goals (v1)

- No swipe gestures / batch-sweep UX polish — that is workstream A, designed on top of this model.
- No per-source auto-approve rules (the user chose "everything"; a rules layer can come later).
- No purge job for rejected rows (cheap to keep; revisit if volume demands).
- No re-approval flow for edits (editing an approved memory does not re-gate it).

## Design

### Data model

- `memories.status: str` — `'pending' | 'approved' | 'rejected'`, server default `'pending'`,
  NOT NULL. Alembic migration 022 adds the column with default, backfills **all existing
  rows to `'approved'`** (they predate the gate), and adds index `(tenant_id, status)`.
- No new table. The memory row *is* the approval item; approval is a status transition.

### Ingest paths (all create `pending`)

- `MemoryManager.ingest` → extracted-fact rows: `pending`.
- Raw-text fallbacks (`api/memories.py`, `workers/ingest_capture.py` via
  `ingest_or_fallback`): `pending`.
- Direct `POST /memories/` rows: `pending`.
- Dedup keeps running at ingest across **pending + approved** rows (a duplicate of a
  pending memory must not create a second pending copy). Rejected rows are excluded
  from dedup (rejecting something must not block re-capturing it later).
- Embeddings unchanged — pending memories are fully formed (content, tags, embedding),
  just not trusted.

### Read paths

- **User-facing** (`GET /memories/`, search endpoints used by the dashboard): include
  `pending` + `approved` by default; each row carries `status`. Optional
  `?status=` filter. `rejected` returned only when explicitly requested.
- **Automation-facing** (agent recall context, `storage/hybrid.py` search when called by
  agents/kernel, watchers, daily brief, consolidation, contradiction detection):
  `approved` only. Implementation: the store/search layer gains an explicit
  `statuses: list[str]` parameter; automation call sites pass `["approved"]`;
  dashboard-serving endpoints pass `["pending", "approved"]`. **No implicit global
  default that automation could forget to override** — the parameter is required at the
  hybrid/store search layer so every call site states its intent.
- Consolidation/decay workers operate on approved rows only; pending rows neither decay
  nor consolidate while waiting.

### API

- `POST /api/v1/memories/{id}/approve` → sets `approved` (404 outside tenant; idempotent).
- `POST /api/v1/memories/{id}/reject` → sets `rejected` (idempotent).
- `POST /api/v1/memories/approvals/bulk` → `{"approve": [ids], "reject": [ids]}` for
  batch action (distillation will need it; trivial to add now).
- `GET /api/v1/memories/pending/count` → `{count}` for the nav badge.
- Events: `MEMORY_PENDING` emitted at creation (payload: memory id, source, preview);
  `MEMORY_APPROVED` / `MEMORY_REJECTED` on transition. All ride the existing
  EventBus → Redis → WebSocket relay, so the UI badge updates live for free.

### Dashboard (minimal for this workstream)

- Memory cards render a **pending badge** (uzhavu tokens, amber accent) with two
  inline actions: ✓ approve, ✕ reject. Optimistic update, existing query invalidation.
- Nav shows pending count badge (from `/memories/pending/count`, refreshed on
  `MEMORY_PENDING`/`MEMORY_APPROVED` WebSocket events if the socket is already wired;
  otherwise poll on navigation — polish belongs to workstream A).
- Mobile capture success chip copy becomes "Captured — pending your approval".

### Failure handling

| Case | Behaviour |
|---|---|
| Approve/reject a memory in another tenant | 404 (tenant filter, as everywhere) |
| Approve an already-approved memory | 200 no-op (idempotent) |
| Reject then re-capture identical text | New pending row allowed (rejected rows excluded from dedup) |
| Migration on live DB | Column add with server default + backfill in one revision; existing rows → approved |
| Automation call site missed in sweep | Impossible-by-design goal: search layer requires explicit `statuses` argument — grep-verifiable at review |

## Verification

1. Unit: ingest (all paths) creates `pending`; approve/reject transitions; bulk endpoint;
   dedup pending-vs-new and rejected-vs-new semantics; automation search called with
   `["approved"]` excludes pending rows.
2. Migration up on a copy of live data: existing rows all `approved`, new writes `pending`.
3. Live E2E: capture text on the phone → appears with pending badge → agent
   conversation/recall does NOT surface it → approve → recall surfaces it.
4. Daily brief mentions pending count (spot-check the generated brief payload).
