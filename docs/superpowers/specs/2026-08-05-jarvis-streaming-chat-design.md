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

**Two code-verified facts that shape the design** (origin/master @ `6bee0fa`):
- Persona tasks run **in-process** — `ProcessManager.spawn` does `asyncio.create_task(_execute_task(...))`
  inside the **FastAPI web process** (`kernel/process_manager.py:159`). ARQ workers only run cron. So the
  persona loop and any SSE endpoint live in the **same process** — no cross-process bridge is required.
- The agent loop **already streams**: `AgentOrchestrator.run()` is an async generator that sets
  `stream=True` and yields SSE-formatted events (`token`, `tool_call`, `tool_result`, `status`, `done`)
  via `get_resilient_llm().acompletion(...)` (`agents/orchestrator.py:58,118,128`). Today
  `process_manager._run_agent` (`process_manager.py:452`) **consumes that stream and throws the tokens
  away**, keeping only the final text. We just need to *not* throw them away, and expose them.

**Design consequence:** we are *not* building or merging backend coordination, and *not* building
streaming from scratch. We are (1) **exposing** the orchestrator's existing token stream over HTTP SSE,
(2) making delegated child tokens reachable via an **in-process session bus** (an `asyncio.Queue` registry
keyed by `session_id` — Redis only if/when multiple web replicas exist), (3) building the **chat surface**
that renders it, and (4) a small **coordination-prompt tune-up**.

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

## Architecture — in-process streaming (single web process)

```
Browser (chat UI)
  │  POST /api/v1/kernel/chat/stream {message, target_agent:"jarvis"}   ──►  web process
  │      (fetch + ReadableStream reader — NOT EventSource; see Frontend)      │
  │                                                                           ▼
  │                                            resolve jarvis persona → build AgentOrchestrator
  ▼                                                        │  orchestrator.run() already yields tokens
 renders ◄─────── SSE (text/event-stream) ────────────────┤
   tokens/steps                                            │  delegate_to_persona → ProcessManager.spawn
                                                           │      child task (same process)
                                                           └─ child orchestrators publish deltas ──►
                                                              in-process session bus (asyncio.Queue
                                                              registry keyed by session_id); the SSE
                                                              handler merges Jarvis's stream + child deltas
```

**Why in-process (not a Redis relay):** persona execution and the SSE endpoint run in the **same FastAPI
process** (`ProcessManager` uses `asyncio.create_task`, `process_manager.py:159`), so Jarvis's own tokens
stream directly from `orchestrator.run()`. Delegated **children** are separate in-process tasks; to stream
*their* tokens live we add a lightweight **in-process session bus** — a registry of `asyncio.Queue`s keyed
by `session_id` that child orchestrators publish deltas to and the SSE handler drains. **No Redis is
required for a single instance.** For multi-replica infra later, the bus is a one-file swap to Redis
pub/sub (channel `stream:{tenant_id}:{session_id}`, modeled on the existing `RedisBridge`,
`core/events.py:270`) — designed for it, not dependent on it.

### Components

1. **Expose the orchestrator stream.** Reuse the exact orchestrator build that `_run_agent` already does
   (`process_manager.py:425-449` — model/temperature/max_tokens from persona, `allowed_tools` filtering),
   but instead of discarding tokens, forward `orchestrator.run()`'s yielded events to the HTTP response.
   The orchestrator already emits `token`/`tool_call`/`tool_result`/`status`/`done` — we **map** those to
   our chat event protocol (below): a `delegate_to_persona` `tool_call` → `delegation_start`; its
   `tool_result` → `child_done` (+ the child's answer for the expandable buffer).
2. **In-process session bus** (`services/chat_stream.py`): `publish(session_id, event)` /
   `subscribe(session_id) -> AsyncIterator`. Backed by per-session `asyncio.Queue`s. Child persona loops
   publish their `child_delta`s here (tagged `child_id`+`persona`); the SSE handler merges them with
   Jarvis's own token stream. Redis-backed implementation is an interface-compatible drop-in.
3. **SSE endpoint** `POST /api/v1/kernel/chat/stream` (web process): resolves the persona, runs the
   orchestrator, and returns `StreamingResponse(..., media_type="text/event-stream")` merging the
   orchestrator events + session-bus child deltas. Tenant-scoped + auth'd; heartbeats; also records an
   `AgentTask` (+ children via delegation) so the existing task-tree endpoints and history still work.
4. **Chat frontend** — consumes the stream via `fetch()` + `ReadableStream` reader, renders per the mockup.

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

**`POST /api/v1/kernel/chat/stream`** — *new, primary*. Body `{message, target_agent:"jarvis", session_id?,
project_id?}`. Auth `Authorization: Bearer` + `X-Tenant-ID` (normal headers — the client uses `fetch()`,
not `EventSource`, so headers work). Response `text/event-stream`: emits the chat events below
(`event:` = type, `data:` = JSON), heartbeats ~15s, ends on `done`/`error` or client disconnect. Records
an `AgentTask` (id returned in the `start` event) so the task-tree/history endpoints keep working.

**Existing endpoints reused unchanged:** `POST /api/v1/kernel/route` (accepts `target_agent`; still used
for the non-streaming/fire-and-forget path and by other callers), `GET /api/v1/kernel/tasks/{id}`
(fetch the persisted final `result.response` — the reconnect/missed-tail fallback), and the Era-7
`GET /api/v1/agent-tasks/{id}/tree` (`api/agent_tasks.py:57`) for the delegation tree view.

**Reconnect:** if the stream drops, the client re-POSTs with the same `session_id`; the server replays from
the session bus's short in-memory retained buffer, and if that's gone, the client falls back to
`GET /kernel/tasks/{id}` for the final answer — a missed tail never loses the result (it's persisted).

## Frontend design

UI reference: **`docs/design/mockups/jarvis-streaming-chat.html`** (open in a browser; `↺ replay`).

- **Persona picker** (header): "Talking to → Jarvis · coordinator / Ask my memories / Tutor / SWE-Lead /
  Scout / Admin". Selecting a persona sets `target_agent` on the route call. Default = Jarvis.
- **Thread:** user bubble → assistant area = compact **step chips** (`Tutor · drafting…` spinner → `✓`)
  + Jarvis **synthesis streaming** with a live cursor. **Tap a chip to expand** that role's full answer.
- **Surface placement:** unify with the existing chat rather than a third surface — the picker's "Ask my
  memories" option preserves today's memory-Q&A chat; picking a persona switches to the streaming route.
  (Exact file wiring — extend `m/chat` + `chat-bar` vs a shared component — resolved in the plan.)
- **Controls:** a **Stop** button (aborts: closes the stream + best-effort `POST /kernel/tasks/{id}/cancel`);
  graceful disconnect/reconnect; render the final answer from the task if the stream is missed.
- **Streaming client:** consume via **`fetch()` + `ReadableStream.getReader()`** (parse the SSE frames
  manually), **not `EventSource`** — EventSource can't send `Authorization`/`X-Tenant-ID` headers, and the
  app's auth is header-based (`dashboard/lib/api.ts:2-11`). Add a `kernel.chatStream(message, target_agent)`
  client and extend `api.kernel.route` to pass `target_agent` (today it sends only `{message}`,
  `api.ts:138`).

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
  (`start → delegation_start → child_delta* → child_done → assistant_delta* → done`). No Redis — the
  session bus is in-process; the LLM is the only thing mocked.
- **Manual gate:** on the VM, open the chat, address Jarvis with a two-role prompt, watch chips + synthesis
  stream, expand a chip; confirm it matches the mockup and the final answer equals the task's stored result.

## Locked decisions

- SSE **token** streaming (not polling, not WS) — chosen deliberately; build proper, infra later.
- **In-process session bus** (`asyncio.Queue` registry), *not* a Redis relay — because persona execution
  and the SSE endpoint share one process. Redis pub/sub is a designed-for, interface-compatible drop-in
  for multi-replica infra, not a V1 dependency.
- **Expose the orchestrator's existing stream** rather than building streaming anew.
- **Collapsible steps**, default compact, expand-to-nest.
- **Live child-token streaming** — child loops publish deltas to the session bus as they generate.
- Backend coordination/delegation/task-tree **reused unchanged**; only streaming + surfacing added.
- **Unify** the chat surface (one screen + persona picker, default Jarvis), mode-branched rendering.

## Open questions (resolve in plan)

- **(resolved)** Seam = a new endpoint mirroring `process_manager._run_agent`'s orchestrator build
  (`process_manager.py:425-449`) but forwarding `orchestrator.run()` events instead of discarding them.
- **(resolved — LIVE) `child_delta` streams live.** Child persona loops publish their token deltas to the
  session bus (tagged `child_id`+`persona`) as they generate, independent of the parent's poll. Note
  `delegate_to_persona` currently **busy-polls** the child every 2s (`tools/delegate.py:24`) for the *final
  result*; live streaming is a separate, additive publish from inside the child's orchestrator loop and does
  not change delegation semantics.
- **(resolved — UNIFY) One chat surface, mode-branched.** A single chat screen with the persona picker;
  default = **Jarvis**. Selecting "Ask my memories" uses the existing non-streaming `conversations`
  pipeline; selecting any persona uses `POST /kernel/chat/stream` with delegation-step rendering. Reuses
  `m/chat`/`chat-bar` rather than a separate Jarvis page. (Exact component factoring — shared
  `<PersonaChat>` vs. inline branch — is a plan detail.)
