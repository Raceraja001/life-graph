# Chat Distillation — turn conversations into durable memories

> **Date:** 2026-07-31
> **Status:** Approved design — ready for implementation planning
> **Scope:** `models/db.py` + Alembic migration (add `Conversation.last_distilled_at`),
> new `services/distillation.py`, new archive helper, `api/conversations.py` (+1 endpoint),
> new `workers/distill.py` (background job) + `workers/settings.py` (cron), a mobile chat
> "Distill" action. Deployed at `brain.raceraja001.in`.
> **Roadmap:** workstream #4 of 4 (chat → notifications → reactive UI → **chat distillation**).
> **Depends on:** the ask-your-memories chat feature (PR #13, merged — `Conversation`,
> `ConversationMessage`, `ConversationService`) and the approval gate (PR #12, merged —
> memories default `status="pending"`). Benefits from but does not require the memory-quality
> clean-capture path (PR #15, pending) — it reuses `manager.ingest`, which #15 improves.

## Problem

The ask-your-memories chat (`services/conversation.py`) is a read-only lens: it retrieves
approved memories and synthesizes grounded answers, but nothing a user says *during* a
conversation is ever captured back into the memory system. Chats are where corrections and new
facts surface most naturally — "actually my insurance renews the 20th, not the 15th", "I decided
to go with the Oracle box" — and today that signal evaporates when the thread scrolls away.

The full conversation *is* persisted (every turn lives in `conversation_messages`), so the raw
record survives. What's missing is (1) promoting the genuinely-new facts a user states into
durable, approvable memories, and (2) a portable backup snapshot of the whole thread for later
reuse outside the DB.

## Decisions (locked with user)

- **Two tiers.** Tier 1: extract new atomic facts from the user's turns → `status="pending"`
  memories (approval gate). Tier 2: export the whole conversation to a MinIO snapshot file.
- **Facts come from the user's turns only.** The assistant's answers are synthesized from
  existing approved memories, so they contain nothing new; extracting from user turns avoids
  re-deriving memories the user already has (and dedup would drop them anyway).
- **Incremental facts, whole-thread archive.** `Conversation.last_distilled_at` marks the last
  run. Fact extraction processes only user turns created *after* that marker (cheap, no duplicate
  LLM work, no duplicate facts). The archive file is *overwritten* each run with the complete
  current thread. The marker is **advanced on every run, including a no-op** (no new turns), so the
  idle cron cannot re-enqueue the same conversation forever; a new chat message bumps `updated_at`,
  which re-makes the conversation eligible.
- **Both triggers.** A manual "Distill this chat" action AND an auto cron that distills
  conversations idle >30 min with new activity since the last distill.
- **Facts are gated; the archive is not.** New facts wait for approval; the backup file is
  written directly (it's a backup, not a claim).
- **Reuse the cheap pipeline.** Extraction is the existing 3-tier `manager.ingest`
  (~85% local, LLM only on low confidence) — consistent with "LLM as advisor, not authority".

## Non-goals (v1)

- No distillation of the assistant's answers, and no "Q&A pair" memories (user chose new-facts-only).
- No per-turn / real-time distillation (only manual + idle-triggered whole-batch runs).
- No re-scan of already-distilled turns (incremental by `last_distilled_at`; dedup is the backstop).
- No approval gate on the archive file; no UI to browse archive files in v1 (they're a backup
  reachable via MinIO / later reprocessing, not a v1 surface).
- No editing/curation of distilled facts beyond the existing approve/reject gate.
- No cross-conversation deduplication beyond the standard memory dedup pipeline.
- No change to how chat retrieval/synthesis works.

## Architecture

```
 Trigger ─────────────────────────────────────────────────────────
   manual:  POST /api/v1/conversations/{id}/distill  → enqueue job, return 202-style ack
   auto:    cron distill_idle_conversations (every 15 min)
              per tenant: SELECT conversations WHERE updated_at < now()-30min
                          AND (last_distilled_at IS NULL OR last_distilled_at < updated_at)
              → enqueue distill_conversation(id) for each
        │
        ▼  ARQ job  distill_conversation(ctx, conversation_id, tenant_id)
 ConversationDistiller.distill(conversation_id):
   1. load Conversation + its messages (tenant-scoped); 404/skip if not owned
   2. new_user_turns = [m for m in messages
                        if m.role == "user"
                        and (conv.last_distilled_at is None or m.created_at > conv.last_distilled_at)]
   3. if not new_user_turns:  return {new_facts: 0, archived: False}   # clean no-op
   4. text = "\n".join(t.content for t in new_user_turns)
      memories = await manager.ingest(text, source="chat")   # 3-tier extract + dedup, status=pending
      tag each with "chat"; set properties.conversation_id = str(id)   # provenance
   5. archive = build_snapshot(conv, messages, [m.id for m in memories])
      minio.upload("conversations", f"{tenant_id}/{conversation_id}.json", archive)  # overwrite
   6. conv.last_distilled_at = now(); commit
   7. emit CONVERSATION_DISTILLED {conversation_id, new_facts: len(memories)}
        │
        ▼
   MEMORY_PENDING (per stored memory) live-refreshes the approvals list;
   CONVERSATION_DISTILLED drives the toast "→ N new facts pending your approval"
```

## Components

### 1. Data model (`models/db.py` + Alembic migration)

- Add `Conversation.last_distilled_at: Mapped[datetime | None]` (nullable, default `None`).
  It is the idempotency + re-distill marker. No new table.
- Alembic migration: `add_conversation_last_distilled_at` (next revision after the current head;
  the plan resolves the exact `down_revision` at build time). Tenant-agnostic column add.
- Distilled memories are ordinary memories: `source="chat"`, a `"chat"` tag appended to whatever
  tags extraction produced, and `properties["conversation_id"] = str(conversation_id)` for
  provenance and later linking. They default to `status="pending"` via the normal store path.

### 2. `ConversationDistiller` (`services/distillation.py`)

- `__init__(self, session_factory, memory_manager, minio)`.
- `async def distill(self, conversation_id: uuid.UUID) -> dict`:
  the flow above. Returns `{"new_facts": int, "archived": bool, "skipped": bool}`.
  - Ownership: load `Conversation`; if missing or wrong tenant → raise `ConversationNotFound`
    (reuse the existing exception from `conversation.py`, or a local mirror).
  - Incremental selection by `last_distilled_at` as shown; empty → no-op (no LLM call, no
    archive rewrite, `last_distilled_at` untouched).
  - Extraction via `await memory_manager.ingest(text, source="chat")`; tag + provenance applied
    to the returned rows. Dedup and the `pending` default come from the existing store path.
  - Archive best-effort: wrap the MinIO upload in try/except — a storage failure logs and sets
    `archived=False` but never discards the facts already created.
  - `last_distilled_at = _utcnow()` set only when at least one new user turn was processed.
  - Emit `CONVERSATION_DISTILLED` (best-effort, never breaks the job — mirror the `try/except`
    around event emits in `conversation.py`).

### 3. Archive snapshot (`services/distillation.py` helper or small `distill_archive.py`)

- `build_snapshot(conv, messages, created_memory_ids) -> bytes`: JSON, UTF-8, e.g.
  ```json
  {
    "conversation_id": "...", "tenant_id": "...", "title": "...",
    "distilled_at": "2026-07-31T...Z",
    "messages": [{"role": "user"|"assistant", "content": "...",
                  "cited_memory_ids": ["..."], "created_at": "...Z"}],
    "distilled_memory_ids": ["..."]
  }
  ```
- Bucket `conversations`, key `{tenant_id}/{conversation_id}.json`, overwritten each run
  (`minio.upload` calls `ensure_bucket` itself). JSON is chosen over Markdown for
  machine-reprocessability ("later we can use it if needed").

### 4. API (`api/conversations.py`)

- `POST /api/v1/conversations/{id}/distill`:
  - 404 (tenant filter) if the conversation isn't the caller's.
  - Enqueue `distill_conversation(conversation_id, tenant_id)` via the ARQ pool using the FULL
    dotted job name (`life_graph.workers.distill.distill_conversation`) — matching
    `WorkerSettings.functions`, per the repo's ARQ enqueue gotcha — and return the existing
    `success_response` envelope with `{"status": "distilling"}`. Fire-and-forget; results arrive
    via the live events. (If the ARQ pool is unavailable, fall back to running the distiller
    inline so a manual tap still works — mirror how capture ingest degrades.)

### 5. Workers (`workers/distill.py` + `workers/settings.py`)

- `async def distill_conversation(ctx, conversation_id, tenant_id) -> dict`: set the tenant
  context, build a `ConversationDistiller` from app state / a session factory, call `distill`.
- `async def distill_idle_conversations(ctx) -> dict`: the cron entry. For each tenant (reuse the
  per-tenant enumeration used by `run_tenant_consolidation`), select idle-with-new-activity
  conversations (query in the Architecture block) and enqueue `distill_conversation` for each.
  Bounded: log and cap the number enqueued per run (e.g. 200) so a backlog can't stampede.
- Register `distill_conversation` and `distill_idle_conversations` in
  `WorkerSettings.functions`, and add a `cron(distill_idle_conversations, minute={0,15,30,45})`
  entry (every 15 min) to `cron_jobs`. Idle threshold (30 min) and cron cadence are constants,
  overridable via `LIFE_GRAPH_`-prefixed config if trivially wired; hardcoded constants are
  acceptable for v1.

### 6. Events (`core/events.py`)

- Add `CONVERSATION_DISTILLED = "conversation:distilled"` to `EventType`. Payload
  `{conversation_id, tenant_id, new_facts}`. Bridges to WebSocket like other events.

### 7. Dashboard — mobile chat "Distill" action

- In the mobile chat thread view (`app/(mobile)/m/chat/*`), add a "Distill this chat" action
  (thread header/overflow). On tap → `POST /conversations/{id}/distill` → toast
  "Distilling…"; on the `conversation:distilled` WS event (wired via the reactive-UI completion
  pattern from PR #18 — `use-websocket.ts` EVENT_MAP + `capture-events`-style surface), show
  "→ N new facts pending your approval". Disabled while offline.
- The new pending memories appear in the existing approvals/memories surfaces (approval gate UI,
  unchanged). Distilled facts carry the `"chat"` tag so they're visually identifiable.
- API client: `api.conversations.distill(id)` + a `useDistillConversation()` mutation.

## Failure handling

| Case | Behaviour |
|---|---|
| No new user turns since last distill | Clean no-op: no LLM call, no archive rewrite; `last_distilled_at` still advanced to now (prevents cron re-enqueue); manual tap toast "Nothing new to distill" |
| Conversation continued after a prior distill | Only turns after `last_distilled_at` are extracted; archive rewritten with the full current thread |
| Duplicate fact already a memory | Dropped by the existing dedup pipeline (SHA-256 + pgvector ≥ 0.92); no duplicate pending memory |
| MinIO unreachable | Facts still created; archive upload failure logged, `archived=False`; job still succeeds |
| LLM unreachable during extraction | `manager.ingest` falls back (rules/nlp, then raw store) — existing `ingest_or_fallback` behaviour; no fabricated facts |
| ARQ pool unavailable on manual tap | Endpoint runs the distiller inline so the tap still works |
| Another tenant's conversation id | 404 (manual) / skipped (cron); all queries tenant-scoped |
| Cron re-enqueues a conversation already being distilled | Incremental selection + `last_distilled_at` make a double run idempotent (second run finds no new turns) |

## Verification

1. **Unit** (`tests/unit`, no DB — conftest mocks pgvector):
   - `distill` selects only user turns after `last_distilled_at` (first run = all; second run after
     new turns = only the new ones); asserts the text passed to a mocked `manager.ingest`.
   - No new user turns → returns `skipped/new_facts:0`, `manager.ingest` NOT called, `last_distilled_at`
     unchanged, no MinIO upload.
   - Distilled rows get `source="chat"`, `"chat"` tag, `properties.conversation_id` set.
   - `build_snapshot` emits the documented JSON shape (roles, cited ids, distilled ids).
   - MinIO upload failure → facts preserved, `archived=False`, no exception escapes.
   - Tenant isolation: distilling another tenant's id raises `ConversationNotFound`.
   - Enqueue uses the FULL dotted job name (regression-guard consistent with the existing
     `test_arq_enqueue_names` scan).
2. **Integration** (`tests/integration`, httpx ASGITransport + tenant headers):
   - `POST /conversations/{id}/distill` returns the envelope and enqueues (or runs inline);
     another tenant's id → 404; valid input never 422.
   - Migration up on a copy: `last_distilled_at` column added, existing conversations untouched.
3. **Live E2E (batched with the deploy):** ensure the `conversations` MinIO bucket exists; have a
   chat where you state a new fact → tap Distill → a pending "chat"-tagged memory appears in
   approvals with the right content → approve it → it's now retrievable by chat. Continue the same
   chat with another new fact, distill again → only the new fact becomes pending (no duplicate of
   the first). Confirm the archive object `conversations/{tenant}/{id}.json` exists and holds the
   full thread. Leave a chat idle >30 min → the cron distills it unattended.
