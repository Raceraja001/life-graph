# Ask-Your-Memories Chat — a grounded conversation with your second brain

> **Date:** 2026-07-23
> **Status:** Approved design — ready for implementation planning
> **Scope:** `models/db.py` + Alembic migration, `services/synthesis.py`, `storage/hybrid.py` (reuse),
> new `api/conversations.py`, `services/conversation.py`, dashboard mobile chat surface + desktop
> ChatBar upgrade. Deployed at `brain.raceraja001.in`.
> **Roadmap:** workstream #1 of 4 (chat → notifications → reactive UI → chat distillation).
> **Depends on:** the memory approval gate (PR #12) — chat answers from `active` memories only.

## Problem

Life Graph captures well but gives little back on demand. The dashboard's "Conversation" panel
(`components/chat-bar.tsx`) is a stub: it posts to `POST /kernel/route` (regex intent classification)
and dumps the raw routing JSON into a bubble. There is no way to *ask* your second brain a plain-language
question — "when's my car insurance due?", "what did I decide about the Oracle box?" — and get a real,
grounded answer. Mobile (the primary device) has no chat surface at all.

Most of the backend already exists and is unused by the UI: `POST /search/ask` (`ask_brain`) +
`SynthesisService.synthesize()` already produce grounded, anti-hallucination answers from retrieved
memories. This feature finishes and upgrades that path, adds conversation memory, and gives it a real UI.

## Decisions (locked with user)

- **Multi-turn threaded.** Conversations are remembered; follow-ups ("when's *that* due?") resolve
  against prior turns. Needs new `conversations` + `conversation_messages` tables.
- **Wait-then-show.** No token streaming in v1 (none exists today). Thinking indicator → full answer
  (~2-6s on free models). Streaming is a deliberate future upgrade, not v1.
- **Approved-only answers.** Retrieval is `statuses=("active",)` — the chat never cites a memory the
  user hasn't approved. Consistent with the approval gate.
- **Both surfaces, mobile-first.** New mobile chat tab (none exists) + upgrade the desktop ChatBar
  stub to call the real endpoint. Desktop stays a **compact quick-ask** box that deep-links into the
  thread view — not a full threaded panel in v1.

## Non-goals (v1)

- No token streaming / typing effect (wait-then-show only).
- No full markdown rendering — plain-text answers + citation chips (avoid a new dashboard dependency).
- No thread editing, branching, regeneration, or message deletion (whole-conversation delete only).
- No agent tool-use / actions from chat (it answers; it doesn't *do*). No web search.
- No cross-conversation memory beyond retrieval (each turn retrieves fresh; history is LLM context only).
- Pending/rejected memories never appear in answers.

## Architecture

```
Mobile chat tab  /  desktop ChatBar quick-ask
        │  POST /api/v1/conversations/{id}/messages  { content }
        ▼
  ConversationService.ask(conversation_id, question)
        │
        ├─ 1. retrieve:  HybridQueryEngine.tri_search(question, limit=8, statuses=("active",))
        │       (upgrade from ask_brain's pure store.search_similar — better recall + graph signal)
        │
        ├─ 2. synthesize: SynthesisService.synthesize(question, memories, history=last_N_turns)
        │       grounded, anti-hallucination prompt, now CITATION-AWARE (emits [Memory N])
        │
        ├─ 3. map [Memory N] → memory ids; persist user turn + assistant turn
        │       (assistant turn stores cited_memory_ids[])
        ▼
  { message: {role, content, cited_memory_ids, model}, citations: [MemoryResponse...] }
        │
        ▼ citation chips ([Memory 1] tap → opens that memory in the existing memory sheet/detail)
```

## Components

### 1. Data model (`models/db.py` + Alembic migration)

- **`Conversation`** — `id` (UUID pk), `tenant_id` (NOT NULL, indexed), `title: str`
  (auto-generated from the first question, truncated ~60 chars), `created_at`, `updated_at`.
  Index `(tenant_id, updated_at)` for the recent-conversations list.
- **`ConversationMessage`** — `id`, `conversation_id` (FK, indexed), `tenant_id`, `role: str`
  (`'user' | 'assistant'`), `content: Text`, `cited_memory_ids: ARRAY(UUID)` (empty for user turns),
  `model: str | None` (which LLM answered), `created_at`. Index `(conversation_id, created_at)`.
- Alembic migration adds both tables (next revision after the approval branch's head — the plan
  resolves the exact `down_revision` at build time). Both tenant-scoped like every table.

### 2. Retrieval + synthesis upgrade

- **Retrieval:** `ConversationService` calls `HybridQueryEngine.tri_search(question, limit=8,
  statuses=("active",))` instead of `ask_brain`'s pure `store.search_similar`. Better recall (vector +
  BM25 + graph) and honors the approval gate explicitly.
- **Citation-aware synthesis:** extend `SynthesisService`. The system prompt already numbers memories
  in the context (`context_parts` 1..N). Add an instruction: *"When a fact comes from a memory, cite it
  inline as [Memory N] using its number. Only cite memories you actually used."* Parse `[Memory N]`
  tokens from the answer, map N → the retrieved memory's id, and return both the raw answer (chips
  rendered client-side from the tokens) and the ordered `cited_memory_ids`. Unmatched/hallucinated
  N values are dropped. The existing grounding rules ("answer only from provided memories", "say you
  don't have enough") and the `_rule_based_answer` fallback are preserved.
- **Multi-turn:** pass the last N (≈6) messages of the conversation to `synthesize(...)` as prior
  context so the model resolves references. Retrieval uses the current question text (v1: raw question;
  a future upgrade may rewrite it using history). History shapes understanding, not retrieval, in v1.

### 3. Conversation API (`api/conversations.py`, `services/conversation.py`)

- `POST /api/v1/conversations` → create empty conversation → `{id, title: null, created_at}`.
- `GET /api/v1/conversations` → recent conversations (id, title, updated_at), keyset-paginated.
- `GET /api/v1/conversations/{id}` → the full thread (messages in order, each with cited memory ids).
- `POST /api/v1/conversations/{id}/messages` `{content}` → **the ask**: retrieve → synthesize →
  persist both turns → set the conversation title from the first question if empty → bump `updated_at`
  → return the assistant message + resolved citation `MemoryResponse`s. 404 for another tenant's id.
- `DELETE /api/v1/conversations/{id}` → delete conversation + its messages (tenant-scoped).
- Envelope: existing `success_response`. Emits `CONVERSATION_MESSAGE` event (id + preview) on the bus
  so a future notification/live-update layer can hook in — optional for v1 UI.

### 4. Dashboard — mobile chat surface (new) + desktop upgrade

- **Mobile** (`dashboard/app/(mobile)/m/chat/*`): a new tab in `mobile-tabbar.tsx`. Conversation list
  (recent threads) → thread view (message bubbles + citation chips) → input box (disabled offline).
  Reuse the generic state cards (`LoadingCard`/`EmptyCard`/`ErrorCard`) and uzhavu tokens. A "thinking"
  bubble while the answer is in flight. Citation chip tap opens the memory in the existing
  `MemorySheet`.
- **Desktop** (`components/chat-bar.tsx`): repoint from `api.kernel.route` to
  `api.conversations.ask(...)`. Render the grounded answer + citation chips instead of raw JSON. Keep it
  a compact quick-ask box; "see full thread" deep-links to the (shared) thread view. Remove the
  fire-and-forget `capture.mutate` advisor call.
- **API client** (`lib/api.ts` + mobile hooks): `api.conversations.{create,list,get,ask,remove}`;
  hooks `useConversations`, `useConversation(id)`, `useAskConversation()` (invalidates the thread +
  conversation list on success). Citation chips rendered from `[Memory N]` tokens matched to the
  returned `citations[]`.

## Failure handling

| Case | Behaviour |
|---|---|
| No relevant memories | Synthesizer returns "I don't have enough memories to answer that" — no fabrication (existing prompt) |
| LLM unreachable | `_rule_based_answer` fallback lists the top retrieved memories, no invented facts; answer flagged `model: "fallback"` |
| Offline | Chat input disabled with a "needs connection" hint (mirrors capture) |
| Question about pending/unapproved info | Not retrieved (active-only) → treated as "not enough memories"; user can approve then re-ask |
| Another tenant's conversation id | 404 (tenant filter) |
| Model emits a bad `[Memory N]` | Dropped silently; answer text still shown, only valid citations become chips |

## Verification

1. Unit: citation parsing (`[Memory 1] [Memory 3]` → correct ids; bad N dropped); `ConversationService.ask`
   persists both turns with cited ids; title auto-set from first question; tenant isolation on get/delete.
   Retrieval called with `statuses=("active",)` (approved-only, asserted).
2. Migration up on a copy of live data: both tables created, existing data untouched.
3. Live E2E: approve a memory ("car insurance due Aug 15") → ask "when's my insurance due?" → grounded
   answer citing that memory → tap chip → memory opens. Ask a follow-up ("what about the car service?")
   → resolves in context. Ask about something not captured → "I don't have enough memories". Ask about a
   still-*pending* memory → not answered until approved.
4. Phone E2E: full thread on mobile — ask, get answer with chips, follow-up, revisit the thread later.
