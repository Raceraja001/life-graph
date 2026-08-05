# Jarvis Streaming Chat — Design Spec (Sub-project A)

> **Purpose.** Surface the *already-working* `jarvis` persona + multi-role delegation in a real,
> token-streaming chat experience. The backend coordination works today (verified live 2026-08-05);
> the only gap is that none of it reaches a chat UI. This spec designs the streaming surface.
>
> **This is Sub-project A** of the "talk to Jarvis" work. Ambient roles (scout/admin on a schedule →
> notifications) are **Sub-project B**, spec'd separately.
>
> **Refs:** `docs/specs/personal-roles.md` (the persona/delegation spec, already implemented & deployed),
> `KNOWLEDGE.md`, `docs/design/08_jarvis_roadmap_2026-08.md`. UI reference:
> `docs/design/mockups/jarvis-streaming-chat.html`.

## Verified starting point (what already works, live on the VM)

Confirmed by direct test on 2026-08-05 against `https://brain.raceraja001.in` (origin/master):

- All 13 personas seeded under tenant `personal`, including `jarvis, tutor, scout, admin, swe-lead`.
- `POST /api/v1/kernel/route` with `{"message": ..., "target_agent": "jarvis"}` bypasses classification
  (`classified_intent: "override"`) and spawns a `jarvis` `AgentTask`.
- Jarvis runs its agent loop, calls `delegate_to_persona`, and spawns child tasks (Era-7 task tree with
  `parent_task_id`/`root_task_id`/`depth`). Delegated personas produce real answers; Jarvis **synthesizes
  a final coherent result** and the root task completes (~4 min on free models).
- **The entire tree + results live only in the DB / task endpoints — no chat UI shows any of it.** The
  desktop `chat-bar` renders the route call's routing JSON; the mobile `m/chat` is memory-Q&A only.

**Design consequence:** we are *not* building or merging backend coordination. We are (1) making the
persona loop **stream tokens**, (2) **relaying** those tokens from the worker process to the browser,
(3) building the **chat surface** that renders it, and (4) a small **coordination-prompt tune-up**.

## Scope

**In scope (Sub-project A):**
- Streaming mode for persona/agent execution (token deltas, not one blocking result).
- A Redis pub/sub **relay** from the ARQ worker (where tasks run) to the web process.
- A new **SSE endpoint** the browser consumes.
- A **persona-addressable chat surface** (picker + streaming thread + collapsible delegation steps),
  matching `docs/design/mockups/jarvis-streaming-chat.html`.
- **Jarvis coordination tune-up**: its prompt over-delegated to `tutor` 4× and never used `swe-lead` in
  the live test — tighten role selection and stop redundant delegation.

**Out of scope (explicitly):**
- Ambient scout/admin scheduling + notifications → **Sub-project B**.
- Voice / STT / TTS.
- Auto-detection of compound requests (personal-roles V1 already descoped this — multi-role stays
  user-triggered via the picker/`target_agent`).
- Changing the delegation/verifier/task-tree mechanics — reused unchanged.

## Architecture — streaming relay

```
Browser (chat UI)
  │  1. POST /api/v1/kernel/route {message, target_agent:"jarvis"}  ──►  web process
  │                                                    ◄── {session_id, task_id}
  │  2. EventSource GET /api/v1/kernel/chat/stream?session_id=…      ──►  web process (SSE)
  │                                                                        │  subscribes
  ▼                                                                        ▼
 renders  ◄──────────── SSE events ────────────────────  Redis channel  chat:stream:{session_id}
                                                                         ▲  publishes
                                                                         │
                              ARQ worker: jarvis agent loop (streaming LLM) ──┐
                                 │  delegate_to_persona → child task           │ each token / event
                                 └─ child persona loops (streaming LLM) ───────┘
```

**Why a relay:** the persona loop runs in the **ARQ worker** process; the browser's SSE connection is
held by the **web** process. They can't share an in-memory generator. The worker (and each delegated
child) **publishes** structured stream events to a per-session Redis channel; the SSE endpoint in the web
process **subscribes** and forwards them. This reuses the existing EventBus→Redis bridge pattern and is
horizontally scalable (any web replica can serve the stream). It is infra-portable — no dependence on the
current Cloudflare/free-tier setup (the developer will host on dedicated infra).

### Components

1. **Streaming persona execution.** The agent/orchestrator loop gains a streaming path: LLM calls use
   `stream=True` and yield token deltas; tool-call handling is unchanged. Each yielded delta is published
   to the session channel. Non-streaming callers keep working (streaming is additive).
2. **Stream publisher.** A thin helper (e.g. `services/chat_stream.py`) that publishes typed events to
   `chat:stream:{session_id}` via Redis. Called by the jarvis loop and by each delegated child loop
   (children tag their events with `child_id` + `persona`).
3. **SSE endpoint** (`GET /api/v1/kernel/chat/stream?session_id=…`) in the web process: subscribes to the
   channel, forwards events as `text/event-stream`, closes on `done`/`error` or client disconnect.
   Tenant-scoped and auth'd like other endpoints; heartbeats to keep the connection alive.
4. **Chat frontend** — consumes the SSE, renders per the mockup.

## Event protocol (Redis channel → SSE)

Each event is JSON with a `type`. Ordered per session; the browser reconstructs the thread from them.

| `type` | payload | UI effect |
|--------|---------|-----------|
| `start` | `{session_id, task_id, persona:"jarvis"}` | begin assistant turn |
| `assistant_delta` | `{text}` | append to Jarvis's synthesis (streaming cursor) |
| `delegation_start` | `{child_id, persona, subtask}` | add a step chip with spinner |
| `child_delta` | `{child_id, persona, text}` | append into that chip's (hidden) buffer |
| `child_done` | `{child_id, persona, status}` | flip chip to `✓`; buffer is the expandable answer |
| `status` | `{label}` | header line ("coordinating…", "synthesizing…") |
| `done` | `{final_text}` | finalize; close stream |
| `error` | `{message, where}` | show inline error; close stream |

**Buffering rule:** `child_delta` tokens are accumulated per `child_id`; the compact view shows only the
chip, and expanding it reveals the accumulated text (the "collapsible — default steps, expand to nest"
choice). Jarvis's own `assistant_delta`/synthesis always streams visibly.

## API contracts

**`POST /api/v1/kernel/route`** — *unchanged* (already accepts `target_agent`). Returns
`{session_id, task_id, routed_to, task_status}`.

**`GET /api/v1/kernel/chat/stream?session_id=<uuid>`** — *new*. `Accept: text/event-stream`. Auth +
`X-Tenant-ID` as usual. Emits the events above as SSE (`event:` = type, `data:` = JSON). Server sends a
comment heartbeat every ~15s. Ends after `done`/`error`. Reconnect: client may re-open; server replays
from a short Redis-retained buffer if the `Last-Event-ID` header is present (best-effort; a missed tail
still resolves because the final result is also persisted on the task and fetchable).

## Frontend design

UI reference: **`docs/design/mockups/jarvis-streaming-chat.html`** (open in a browser; `↺ replay`).

- **Persona picker** (header): "Talking to → Jarvis · coordinator / Ask my memories / Tutor / SWE-Lead /
  Scout / Admin". Selecting a persona sets `target_agent` on the route call. Default = Jarvis.
- **Thread:** user bubble → assistant area = compact **step chips** (`Tutor · drafting…` spinner → `✓`)
  + Jarvis **synthesis streaming** with a live cursor. **Tap a chip to expand** that role's full answer.
- **Surface placement:** unify with the existing chat rather than a third surface — the picker's "Ask my
  memories" option preserves today's memory-Q&A chat; picking a persona switches to the streaming route.
  (Exact file wiring — extend `m/chat` + `chat-bar` vs a shared component — resolved in the plan.)
- **Controls:** a **Stop** button (aborts: closes SSE + best-effort cancels the task); graceful handling
  of disconnect/reconnect; render the final answer from the task if the stream is missed.

## Jarvis coordination tune-up

From the live run, Jarvis delegated to `tutor` 4× and skipped `swe-lead`. Tighten the `jarvis` system
prompt (in `kernel/personas.py`) to: pick the *minimum* set of roles that fit the request, delegate to a
given role **at most once** unless it explicitly needs a follow-up, and always include the role(s) the
user named. Add a coordination unit test asserting no duplicate-persona delegation for a two-role prompt.

## Error handling & edge cases

- **Worker dies / LLM errors mid-stream** → publish `error`; SSE forwards; UI shows inline error and the
  task's stored partial (never a silent hang).
- **Client disconnects** → SSE endpoint unsubscribes; the task keeps running (result still persisted).
- **Free-model throttling** (relevant until infra upgrade) → deltas simply arrive slower; `status`
  reflects waits; no protocol change.
- **Redis unavailable** → route still spawns the task (unchanged); SSE returns 503 and the UI falls back
  to polling the task tree for the final result.
- **Multiple tabs** → each opens its own SSE on the same `session_id`; pub/sub fan-out handles it.

## Testing strategy

- **Unit:** the stream publisher (correct event shapes/order); the persona loop's streaming path yields
  deltas and still returns the same final result as the non-streaming path; Jarvis coordination prompt
  test (no duplicate delegation).
- **Integration:** `httpx.AsyncClient` + `ASGITransport` — POST route then consume the SSE endpoint with a
  mocked LLM that emits known token deltas; assert the ordered event sequence
  (`start → delegation_start → child_delta* → child_done → assistant_delta* → done`). Redis mocked/faked.
- **Manual gate:** on the VM, open the chat, address Jarvis with a two-role prompt, watch chips + synthesis
  stream, expand a chip; confirm it matches the mockup and the final answer equals the task's stored result.

## Locked decisions

- SSE **token** streaming (not polling, not WS) — chosen deliberately; build proper, infra later.
- **Redis pub/sub relay** worker→web (not in-process; not per-request worker execution).
- **Collapsible steps**, default compact, expand-to-nest.
- Backend coordination/delegation/task-tree **reused unchanged**; only streaming + surfacing added.
- Unify the chat surface (persona picker) rather than a separate Jarvis page.

## Open questions (resolve in plan)

- Exact seam to add streaming in the agent loop (orchestrator vs driver) — pending the code map.
- Whether `child_delta` streams live into the hidden buffer or the child's full text is attached on
  `child_done` only (latency vs simplicity) — default to live buffering; fall back to on-done if the loop
  seam makes per-token child relay costly.
- Frontend: extend `m/chat` + `chat-bar` or introduce a shared `<PersonaChat>` component.
