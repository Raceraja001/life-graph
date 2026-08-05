# Jarvis Streaming Chat — Implementation Plan (Sub-project A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the already-working `jarvis` persona + multi-role delegation as a live, SSE token-streaming chat with collapsible delegation steps.

**Architecture:** Persona tasks run in-process (`ProcessManager` uses `asyncio.create_task`), and `AgentOrchestrator.run()` already streams SSE events (`token`/`tool_call`/`tool_result`/`done`) but `_run_agent` discards them. We add an **in-process session bus** (`asyncio.Queue` registry keyed by the task's `root_task_id`); make `_run_agent` **publish** each orchestrator event (tagged with `task_id`/`agent_name`/`depth`) to that bus; and add a `POST /kernel/chat/stream` endpoint that spawns the persona, subscribes to the bus, **maps** the raw events to the chat protocol, and returns a `StreamingResponse`. Because delegated children also run through `_run_agent`, their tokens stream too. Frontend consumes via `fetch()` + `ReadableStream`.

**Tech Stack:** Python 3.11 (`/c/Python314/python.exe`), FastAPI, SQLAlchemy async, litellm via `ResilientLLM`, pytest + `httpx.AsyncClient`/`ASGITransport` (LLM mocked). Frontend: Next.js 16 / React 19 (`dashboard/`).

## Global Constraints

- Worktree `scratchpad/jarvis-wt`, branch `feat/jarvis-streaming-chat`, off `origin/master` @ `6bee0fa`.
- Backend API prefix `/api/v1` (`life_graph/main.py:273`). Every DB query is tenant-scoped; tenant from `get_current_tenant_id()` (contextvar).
- Ruff line-length 100, double quotes; type-only imports under `TYPE_CHECKING`. Run `ruff check` on modified files; do NOT bare `ruff format` large existing files (`process_manager.py`, `api/kernel.py`) — hand-match style for added lines.
- Backend coordination/delegation/task-tree **reused unchanged** — only add streaming + surfacing.
- Distilled/persona behavior unchanged; no new migration (no schema changes).
- Commit trailer exactly: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Tests from the worktree root: `cd /c/Users/admin/AppData/Local/Temp/claude/d--DevTools-Projects-life-graph/50a1450a-757b-4355-854f-3591f2d0f5be/scratchpad/jarvis-wt && /c/Python314/python.exe -m pytest <path> -v`.
- **Verified existing interfaces (do not reimplement):**
  - `AgentOrchestrator(model, temperature, max_tokens).run(messages, system_prompt, tools) -> AsyncGenerator[str]` yielding `data: {json}\n\n` SSE strings; event `type`s: `token{content}`, `tool_call{name,arguments,status}`, `tool_result{name,result}`, `usage`, `done`, `error` (`agents/orchestrator.py:56`).
  - `ProcessManager._run_agent(tenant_id, agent_name, input_data, persona) -> {"response": str, "token_count": int}` (`kernel/process_manager.py:405`); builds the orchestrator at `:430-446` and consumes/discards the stream at `:452-465`.
  - `ProcessManager._execute_task(task_id, tenant_id, agent_name, input_data, persona, timeout)` calls `set_task_context(task_id, tenant_id)` then `_run_agent` (`process_manager.py:339-367`).
  - `ProcessManager.spawn(tenant_id, agent_name, input_data, task_name=?, parent_task_id=?, root_task_id=?, depth=?, project_id=?, max_retries=?, session_id=?) -> {"task_id": str, ...}` (`process_manager.py:79`).
  - `TaskContext(task_id: uuid.UUID, tenant_id: str)` + `set_task_context(task_id, tenant_id)` + `get_current_task_context()` (`core/task_context.py`).
  - `delegate_to_persona` spawns a child with `parent_task_id`/`root_task_id`/`depth`, busy-polls, returns JSON `{"status":"completed","result":{"response","token_count"}}` (`tools/delegate.py`).
  - Route: `RouteRequest{message, project_id?, target_agent?}` → `route_message` → `success_response(data=...)` on `router` (`api/kernel.py:547,584`). `jarvis` persona at `kernel/personas.py:248-262` (`allowed_tools=["delegate_to_persona"]`).
  - `get_process_manager()`, `get_persona_service()`, `get_chief_router()` are `@lru_cache` singletons (`api/dependencies.py:200-216`).

---

## File Structure

**Created:**
- `life_graph/services/chat_stream.py` — the in-process session bus + the raw→chat event mapper.
- `tests/unit/test_chat_stream_bus.py`, `tests/unit/test_chat_stream_mapper.py`, `tests/integration/test_chat_stream_endpoint.py`.

**Modified:**
- `life_graph/core/task_context.py` — add `root_task_id`/`depth` to `TaskContext`.
- `life_graph/kernel/process_manager.py` — thread `root_task_id`/`depth` into context; publish orchestrator events to the bus in `_run_agent`.
- `life_graph/api/kernel.py` — add `POST /chat/stream` endpoint.
- `life_graph/kernel/personas.py` — Jarvis coordination prompt tune-up.
- `dashboard/lib/api.ts` — `kernel.chatStream()` + `target_agent` on `kernel.route`.
- `dashboard/app/(mobile)/m/chat/page.tsx` (+ a small `dashboard/components/persona-chat.tsx`) — unified streaming chat surface.

---

## Task 1: In-process session bus

**Files:**
- Create: `life_graph/services/chat_stream.py`
- Test: `tests/unit/test_chat_stream_bus.py`

**Interfaces:**
- Produces:
  - `class ChatStreamBus` with `publish(stream_key: str, event: dict) -> None`, `async subscribe(stream_key: str) -> AsyncIterator[dict]`, and an internal per-key retained buffer (default 200 events) replayed to new subscribers.
  - `get_chat_stream_bus() -> ChatStreamBus` (module singleton).
  - A sentinel `_STREAM_END = {"type": "__end__"}` published to close subscribers.

- [ ] **Step 1: Write the failing tests** (`tests/unit/test_chat_stream_bus.py`)

```python
"""Unit tests for the in-process chat session bus."""
from __future__ import annotations

import asyncio

import pytest

from life_graph.services.chat_stream import ChatStreamBus


@pytest.mark.asyncio
async def test_publish_reaches_subscriber():
    bus = ChatStreamBus()
    got = []

    async def consume():
        async for ev in bus.subscribe("k1"):
            got.append(ev)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)  # let subscribe register
    bus.publish("k1", {"type": "token", "content": "hi"})
    bus.close("k1")
    await asyncio.wait_for(task, timeout=1)
    assert got == [{"type": "token", "content": "hi"}]


@pytest.mark.asyncio
async def test_buffer_replays_events_published_before_subscribe():
    bus = ChatStreamBus()
    bus.publish("k2", {"type": "token", "content": "a"})
    bus.publish("k2", {"type": "token", "content": "b"})
    got = []

    async def consume():
        async for ev in bus.subscribe("k2"):
            got.append(ev)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    bus.close("k2")
    await asyncio.wait_for(task, timeout=1)
    assert [e["content"] for e in got] == ["a", "b"]


@pytest.mark.asyncio
async def test_two_subscribers_both_receive():
    bus = ChatStreamBus()
    a, b = [], []

    async def consume(sink):
        async for ev in bus.subscribe("k3"):
            sink.append(ev)

    ta = asyncio.create_task(consume(a))
    tb = asyncio.create_task(consume(b))
    await asyncio.sleep(0)
    bus.publish("k3", {"type": "done"})
    bus.close("k3")
    await asyncio.wait_for(asyncio.gather(ta, tb), timeout=1)
    assert a == b == [{"type": "done"}]


def test_publish_with_no_subscriber_is_noop_but_buffered():
    bus = ChatStreamBus()
    bus.publish("k4", {"type": "token", "content": "x"})  # must not raise
    assert bus.buffer_len("k4") == 1
```

- [ ] **Step 2: Run to verify fail**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_chat_stream_bus.py -v`
Expected: FAIL — `ModuleNotFoundError: life_graph.services.chat_stream`.

- [ ] **Step 3: Implement `life_graph/services/chat_stream.py` (bus portion)**

```python
# life_graph/services/chat_stream.py
"""In-process chat session bus for streaming persona/delegation events.

Persona execution and the SSE endpoint run in the same process (ProcessManager
uses asyncio.create_task), so a per-session asyncio.Queue registry is enough —
no Redis. The stream key is the task tree's ``root_task_id`` (shared by a jarvis
task and all its delegated children). A short retained buffer lets a subscriber
that connects just after spawn still receive the earliest events.

For multi-replica infra later, swap the queue registry for Redis pub/sub on
channel ``stream:{tenant_id}:{root_task_id}`` — same publish/subscribe surface.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator

_END = {"type": "__end__"}
_BUFFER_MAX = 200


class ChatStreamBus:
    def __init__(self, buffer_max: int = _BUFFER_MAX) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=buffer_max))
        self._closed: set[str] = set()

    def publish(self, stream_key: str, event: dict) -> None:
        self._buffers[stream_key].append(event)
        for q in list(self._subscribers.get(stream_key, [])):
            q.put_nowait(event)

    def close(self, stream_key: str) -> None:
        """Signal end-of-stream to all current + future subscribers."""
        self._closed.add(stream_key)
        self._buffers[stream_key].append(_END)
        for q in list(self._subscribers.get(stream_key, [])):
            q.put_nowait(_END)

    def buffer_len(self, stream_key: str) -> int:
        return len(self._buffers.get(stream_key, ()))

    async def subscribe(self, stream_key: str) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue()
        # Replay anything already buffered (events fired before we subscribed).
        for ev in list(self._buffers.get(stream_key, ())):
            q.put_nowait(ev)
        self._subscribers[stream_key].append(q)
        try:
            while True:
                ev = await q.get()
                if ev is _END or ev == _END:
                    return
                yield ev
        finally:
            subs = self._subscribers.get(stream_key)
            if subs and q in subs:
                subs.remove(q)
            if not subs and stream_key in self._closed:
                self._buffers.pop(stream_key, None)
                self._closed.discard(stream_key)
                self._subscribers.pop(stream_key, None)


_bus: ChatStreamBus | None = None


def get_chat_stream_bus() -> ChatStreamBus:
    global _bus
    if _bus is None:
        _bus = ChatStreamBus()
    return _bus
```

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_chat_stream_bus.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Lint + commit**

```bash
ruff check life_graph/services/chat_stream.py tests/unit/test_chat_stream_bus.py
ruff format life_graph/services/chat_stream.py tests/unit/test_chat_stream_bus.py
git add life_graph/services/chat_stream.py tests/unit/test_chat_stream_bus.py
git commit -m "feat(chat): in-process session bus for streaming persona events

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Publish orchestrator events from `_run_agent`

**Files:**
- Modify: `life_graph/core/task_context.py`
- Modify: `life_graph/kernel/process_manager.py`
- Test: `tests/unit/test_run_agent_publishes.py`

**Interfaces:**
- Consumes: `get_chat_stream_bus()` (Task 1).
- Produces: every task's orchestrator events are published to `bus[str(root_task_id)]` as
  `{"task_id": str, "agent_name": str, "depth": int, "event": <raw orchestrator dict>}`. `TaskContext`
  gains `root_task_id: uuid.UUID` and `depth: int`.

- [ ] **Step 1: Extend `TaskContext`** (`core/task_context.py`)

```python
@dataclass(frozen=True, slots=True)
class TaskContext:
    """The kernel task the current coroutine is executing under."""

    task_id: uuid.UUID
    tenant_id: str
    root_task_id: uuid.UUID | None = None
    depth: int = 0


def set_task_context(
    task_id: uuid.UUID,
    tenant_id: str,
    root_task_id: uuid.UUID | None = None,
    depth: int = 0,
) -> None:
    _task_context_var.set(
        TaskContext(task_id=task_id, tenant_id=tenant_id, root_task_id=root_task_id, depth=depth)
    )
```

- [ ] **Step 2: Thread root/depth into `_execute_task`** (`process_manager.py:339`)

Change the signature to accept `root_task_id`/`depth` and pass them to `set_task_context`. At the `spawn` call site that does `asyncio.create_task(self._execute_task(...))` (`process_manager.py:159`), pass the task's `root_task_id` (falling back to `task_id`) and `depth` (both are already computed there for the insert).

```python
    async def _execute_task(
        self,
        task_id: uuid.UUID,
        tenant_id: str,
        agent_name: str,
        input_data: dict[str, Any],
        persona: dict[str, Any],
        timeout: int,
        root_task_id: uuid.UUID | None = None,
        depth: int = 0,
    ) -> None:
        async with self._semaphore:
            from life_graph.core.task_context import set_task_context

            set_task_context(
                task_id=task_id,
                tenant_id=tenant_id,
                root_task_id=root_task_id or task_id,
                depth=depth,
            )
            ...  # rest unchanged
```

At the spawn site (`process_manager.py:159`), update the call:
```python
            asyncio.create_task(
                self._execute_task(
                    task_id, tenant_id, agent_name, input_data, persona, timeout,
                    root_task_id=root_task_id or task_id, depth=depth,
                )
            )
```
(`root_task_id` and `depth` are the same local values spawn already inserts into the `AgentTask` row.)

- [ ] **Step 3: Write the failing test** (`tests/unit/test_run_agent_publishes.py`)

```python
"""_run_agent must publish each orchestrator event to the session bus."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from life_graph.core.task_context import set_task_context
from life_graph.kernel.process_manager import ProcessManager
from life_graph.services.chat_stream import get_chat_stream_bus


async def _fake_run(self, messages, system_prompt=None, tools=None):
    yield 'data: {"type": "token", "content": "he"}\n\n'
    yield 'data: {"type": "token", "content": "llo"}\n\n'
    yield 'data: {"type": "done", "model": "m"}\n\n'


@pytest.mark.asyncio
async def test_run_agent_publishes_events_to_bus():
    root = uuid.uuid4()
    mgr = ProcessManager.__new__(ProcessManager)  # bypass __init__/DI
    set_task_context(task_id=root, tenant_id="t1", root_task_id=root, depth=0)

    with patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run):
        result = await mgr._run_agent(
            "t1", "jarvis", {"message": "hi"}, {"allowed_tools": None}
        )

    assert result["response"] == "hello"
    published = list(get_chat_stream_bus()._buffers[str(root)])
    types = [p["event"]["type"] for p in published]
    assert types == ["token", "token", "done"]
    assert all(p["agent_name"] == "jarvis" and p["depth"] == 0 for p in published)
```

- [ ] **Step 4: Run to verify fail**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_run_agent_publishes.py -v`
Expected: FAIL — bus buffer empty (no publishing yet).

- [ ] **Step 5: Publish in `_run_agent`** (`process_manager.py:405`)

Replace the stream-consumption loop (`:452-465`) so it publishes each event while still accumulating the response. Add imports at top of the method body:

```python
        import json as _json

        from life_graph.core.task_context import get_current_task_context
        from life_graph.services.chat_stream import get_chat_stream_bus

        ctx = get_current_task_context()
        bus = get_chat_stream_bus()
        stream_key = str(ctx.root_task_id or ctx.task_id) if ctx else None
        meta = (
            {"task_id": str(ctx.task_id), "agent_name": agent_name, "depth": ctx.depth}
            if ctx else None
        )

        response_parts: list[str] = []
        token_count = 0

        async for event_str in orchestrator.run(messages, system_prompt=system_prompt, tools=tools):
            try:
                data = _json.loads(event_str.removeprefix("data: ").strip())
            except (ValueError, KeyError):
                continue
            if stream_key is not None:
                bus.publish(stream_key, {**meta, "event": data})
            if data.get("type") == "token":
                response_parts.append(data.get("content", ""))
                token_count += 1

        return {"response": "".join(response_parts), "token_count": token_count}
```

(Publishing is a cheap dict append when no subscriber exists, so tasks spawned via `/route` are unaffected. The bus is `close()`d by the endpoint, not here — a task doesn't own the stream lifecycle.)

- [ ] **Step 6: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_run_agent_publishes.py -v`
Expected: PASS.

- [ ] **Step 7: Regression — kernel unit tests still pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/ -k "process_manager or personas or task_context" -q`
Expected: PASS (no regressions from the signature/context change).

- [ ] **Step 8: Lint + commit**

```bash
ruff check life_graph/core/task_context.py life_graph/kernel/process_manager.py tests/unit/test_run_agent_publishes.py
git add life_graph/core/task_context.py life_graph/kernel/process_manager.py tests/unit/test_run_agent_publishes.py
git commit -m "feat(kernel): publish orchestrator events to the chat session bus

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Chat event mapper + SSE endpoint

**Files:**
- Modify: `life_graph/services/chat_stream.py` (add the mapper)
- Modify: `life_graph/api/kernel.py` (add `POST /chat/stream`)
- Test: `tests/unit/test_chat_stream_mapper.py`, `tests/integration/test_chat_stream_endpoint.py`

**Interfaces:**
- Consumes: bus events `{task_id, agent_name, depth, event}` (Task 2), `ProcessManager.spawn`, `ChiefRouter`/`AgentSession` creation as `route_message` does.
- Produces:
  - `map_bus_event(raw: dict, seen_children: set[str]) -> dict | None` — pure fn mapping one bus event to a chat-protocol event (or `None` to drop). Chat events: `start`, `assistant_delta{text}`, `delegation_start{child_id,persona}`, `child_delta{child_id,persona,text}`, `child_done{child_id,persona}`, `done{}`, `error{message}`.
  - `POST /api/v1/kernel/chat/stream` body `{message, target_agent?, project_id?, session_id?}` → `text/event-stream`.

- [ ] **Step 1: Write the mapper test** (`tests/unit/test_chat_stream_mapper.py`)

```python
from __future__ import annotations

from life_graph.services.chat_stream import map_bus_event


def ev(depth, persona, etype, **payload):
    return {"task_id": f"tid-{persona}", "agent_name": persona, "depth": depth,
            "event": {"type": etype, **payload}}


def test_depth0_token_is_assistant_delta():
    seen = set()
    out = map_bus_event(ev(0, "jarvis", "token", content="hi"), seen)
    assert out == {"type": "assistant_delta", "text": "hi"}


def test_child_first_token_emits_delegation_start_then_child_delta():
    seen = set()
    first = map_bus_event(ev(1, "tutor", "token", content="A"), seen)
    assert first == {"type": "delegation_start", "child_id": "tid-tutor", "persona": "tutor"}
    assert "tid-tutor" in seen
    second = map_bus_event(ev(1, "tutor", "token", content="B"), seen)
    assert second == {"type": "child_delta", "child_id": "tid-tutor", "persona": "tutor", "text": "B"}


def test_child_done_maps_to_child_done():
    seen = {"tid-tutor"}
    out = map_bus_event(ev(1, "tutor", "done"), seen)
    assert out == {"type": "child_done", "child_id": "tid-tutor", "persona": "tutor"}


def test_depth0_done_maps_to_done():
    assert map_bus_event(ev(0, "jarvis", "done"), set()) == {"type": "done"}


def test_tool_call_and_usage_are_dropped():
    assert map_bus_event(ev(0, "jarvis", "tool_call", name="delegate_to_persona"), set()) is None
    assert map_bus_event(ev(0, "jarvis", "usage"), set()) is None
```

Note the design: we detect delegation from a **child task appearing on the stream** (depth ≥ 1, first
event) rather than parsing the parent's `tool_call` — simpler and it's where the child's tokens actually
originate. The parent's `tool_call`/`tool_result`/`usage` are dropped.

- [ ] **Step 2: Run to verify fail** → `pytest tests/unit/test_chat_stream_mapper.py -v` (ImportError).

- [ ] **Step 3: Add `map_bus_event` to `services/chat_stream.py`**

```python
def map_bus_event(raw: dict, seen_children: set[str]) -> dict | None:
    """Map one raw bus event to a chat-protocol event, or None to drop it.

    seen_children is caller-owned mutable state tracking which child task_ids
    have already emitted their delegation_start.
    """
    depth = raw.get("depth", 0)
    persona = raw.get("agent_name", "")
    child_id = raw.get("task_id", "")
    event = raw.get("event", {})
    etype = event.get("type")

    if etype == "error":
        return {"type": "error", "message": event.get("error") or event.get("message", "error")}

    if depth == 0:
        if etype == "token":
            return {"type": "assistant_delta", "text": event.get("content", "")}
        if etype == "done":
            return {"type": "done"}
        return None  # tool_call/tool_result/usage on the top-level task are dropped

    # depth >= 1 : a delegated child
    if etype == "token":
        if child_id not in seen_children:
            seen_children.add(child_id)
            return {"type": "delegation_start", "child_id": child_id, "persona": persona}
        return {"type": "child_delta", "child_id": child_id, "persona": persona,
                "text": event.get("content", "")}
    if etype == "done":
        return {"type": "child_done", "child_id": child_id, "persona": persona}
    return None
```

Edge note: a child whose first streamed event is `done` (no tokens) still needs a `delegation_start`
before `child_done`. Handle in `done`:
```python
    if etype == "done":
        out = []
        if child_id not in seen_children:
            seen_children.add(child_id)
            # emit both via the endpoint; return a compound marker
            return {"type": "delegation_start+done", "child_id": child_id, "persona": persona}
        return {"type": "child_done", "child_id": child_id, "persona": persona}
```
The endpoint expands `delegation_start+done` into two SSE frames.

- [ ] **Step 4: Run mapper test → PASS.** Add a test for the no-token child:

```python
def test_child_done_without_prior_token_signals_both():
    out = map_bus_event(ev(1, "scout", "done"), set())
    assert out == {"type": "delegation_start+done", "child_id": "tid-scout", "persona": "scout"}
```

- [ ] **Step 5: Add the SSE endpoint to `api/kernel.py`**

Add near `route_message` (`api/kernel.py:579`). Reuse the same session-creation the router uses; simplest is to `spawn` directly through the process manager and create the `AgentSession` inline like `ChiefRouter.route` does. Import `StreamingResponse` and the bus helpers.

```python
from fastapi.responses import StreamingResponse

from life_graph.services.chat_stream import get_chat_stream_bus, map_bus_event


class ChatStreamRequest(BaseModel):
    message: str = Field(..., min_length=1)
    target_agent: str = Field(default="jarvis")
    project_id: uuid.UUID | None = None


@router.post("/chat/stream", summary="Stream a persona chat response (SSE)")
async def chat_stream(
    body: ChatStreamRequest,
    pm: Any = Depends(get_process_manager),
    personas: Any = Depends(get_persona_service),
):
    tenant_id = get_current_tenant_id()

    persona = await personas.get_by_name(tenant_id, body.target_agent)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"Unknown persona: {body.target_agent!r}")

    spawn = await pm.spawn(
        tenant_id=tenant_id,
        agent_name=body.target_agent,
        input_data={"message": body.message},
        task_name=f"chat:{body.target_agent}",
        project_id=body.project_id,
    )
    task_id = spawn["task_id"]  # == root_task_id for a top-level task
    bus = get_chat_stream_bus()

    async def gen():
        import json as _json

        def sse(obj: dict) -> str:
            return f"data: {_json.dumps(obj)}\n\n"

        yield sse({"type": "start", "task_id": task_id, "persona": body.target_agent})
        seen: set[str] = set()
        try:
            async for raw in bus.subscribe(task_id):
                mapped = map_bus_event(raw, seen)
                if mapped is None:
                    continue
                if mapped["type"] == "delegation_start+done":
                    yield sse({"type": "delegation_start", "child_id": mapped["child_id"],
                               "persona": mapped["persona"]})
                    yield sse({"type": "child_done", "child_id": mapped["child_id"],
                               "persona": mapped["persona"]})
                    continue
                yield sse(mapped)
                if mapped["type"] == "done":
                    break
        finally:
            bus.close(task_id)

    return StreamingResponse(gen(), media_type="text/event-stream")
```

**Important ordering:** `spawn` returns before the `asyncio.create_task`'d `_execute_task` runs, so
`bus.subscribe(task_id)` inside `gen()` registers before any event fires; the retained buffer covers any
race. The top-level task's `_run_agent` will publish a `done` event → the endpoint maps it to `done` and
stops. (The bus is closed by the endpoint's `finally`.)

- [ ] **Step 6: Write the integration test** (`tests/integration/test_chat_stream_endpoint.py`)

```python
"""End-to-end: POST /chat/stream returns a mapped SSE token stream (LLM mocked)."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app

HEADERS = {"X-Tenant-ID": "test-chat", "Authorization": "Bearer test"}


async def _fake_run(self, messages, system_prompt=None, tools=None):
    for t in ["Hel", "lo"]:
        yield f'data: {{"type": "token", "content": "{t}"}}\n\n'
    yield 'data: {"type": "done"}\n\n'


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


@pytest.mark.asyncio
async def test_chat_stream_emits_start_deltas_done(client):
    with patch("life_graph.agents.orchestrator.AgentOrchestrator.run", _fake_run):
        async with client.stream(
            "POST", "/api/v1/kernel/chat/stream",
            headers=HEADERS, json={"message": "hi", "target_agent": "jarvis"},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            events = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
                    if events[-1]["type"] == "done":
                        break

    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert "assistant_delta" in types
    assert types[-1] == "done"
    text = "".join(e["text"] for e in events if e["type"] == "assistant_delta")
    assert text == "Hello"
```

This test is defensive per repo convention: it accepts a 500 only if the DB is unreachable, but must not
accept a 422 for the valid body. If persona seeding requires a DB, gate with the same skip pattern other
integration tests use (`conftest.py` mocks pgvector; persona `get_by_name` may need a DB — if so, mark
`@pytest.mark.integration` and mock `get_persona_service` to return a stub persona dict, and
`get_process_manager().spawn` to a stub that schedules a coroutine publishing `_fake_run`'s events).

- [ ] **Step 7: Run to verify fail then pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_chat_stream_mapper.py tests/integration/test_chat_stream_endpoint.py -v`
Expected: PASS (add the mapper implementation + endpoint until green).

- [ ] **Step 8: Lint + commit**

```bash
ruff check life_graph/services/chat_stream.py life_graph/api/kernel.py tests/unit/test_chat_stream_mapper.py tests/integration/test_chat_stream_endpoint.py
git add life_graph/services/chat_stream.py life_graph/api/kernel.py tests/unit/test_chat_stream_mapper.py tests/integration/test_chat_stream_endpoint.py
git commit -m "feat(api): POST /kernel/chat/stream — SSE token stream with delegation steps

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Jarvis coordination prompt tune-up

**Files:**
- Modify: `life_graph/kernel/personas.py:253-258`
- Test: `tests/unit/test_jarvis_prompt.py`

**Interfaces:** none new — edits the `jarvis` built-in persona's `system_prompt`.

- [ ] **Step 1: Write the failing test** (`tests/unit/test_jarvis_prompt.py`)

```python
from life_graph.kernel.personas import _BUILTIN_PERSONAS  # adjust import to the actual constant name


def _jarvis():
    return next(p for p in _BUILTIN_PERSONAS if p["name"] == "jarvis")


def test_jarvis_prompt_discourages_redundant_delegation():
    sp = _jarvis()["system_prompt"].lower()
    assert "at most once" in sp or "do not delegate to the same" in sp
    assert "named" in sp  # must honor roles the user named


def test_jarvis_still_only_delegates():
    assert _jarvis()["allowed_tools"] == ["delegate_to_persona"]
```

(If the built-ins list has a different symbol name, use that — verify with
`grep -n "name.*jarvis" life_graph/kernel/personas.py`.)

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Update the `jarvis` `system_prompt`** (`personas.py:253`)

```python
        "system_prompt": (
            "You are Jarvis, the orchestrator. The user selected you explicitly"
            " because their request spans more than one role. First decide the"
            " MINIMUM set of personas needed. Always include any role the user"
            " named. Delegate to each chosen persona AT MOST ONCE via"
            " delegate_to_persona with a clear, self-contained subtask — do not"
            " delegate to the same persona repeatedly. Wait for their results,"
            " then synthesize a single coherent answer. If the request needs only"
            " one role, delegate once; never fan out redundantly."
        ),
```

- [ ] **Step 4: Run → pass.**

- [ ] **Step 5: Commit**

```bash
ruff check life_graph/kernel/personas.py tests/unit/test_jarvis_prompt.py
git add life_graph/kernel/personas.py tests/unit/test_jarvis_prompt.py
git commit -m "feat(personas): tighten Jarvis coordination prompt (no redundant delegation)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Frontend API client — streaming + target_agent

**Files:**
- Modify: `dashboard/lib/api.ts`
- Test: `dashboard` build + lint (no JS unit harness for streaming here).

**Interfaces:**
- Consumes: `POST /api/v1/kernel/chat/stream` (Task 3).
- Produces:
  - `api.kernel.route(message, target_agent?)` — adds optional `target_agent`.
  - `api.kernel.chatStream(message, target_agent, onEvent, signal)` — `async` fn that POSTs and parses the SSE frames off `fetch().body` via a `ReadableStream` reader, invoking `onEvent(evt)` per chat event; abortable via `signal`.

- [ ] **Step 1: Extend `kernel.route`** (`dashboard/lib/api.ts:138`)

```ts
    route: (message: string, target_agent?: string) =>
      POST<any>("/kernel/route", target_agent ? { message, target_agent } : { message }),
```

- [ ] **Step 2: Add `kernel.chatStream`** (same `kernel` object in `api.ts`)

```ts
    chatStream: async (
      message: string,
      target_agent: string,
      onEvent: (e: any) => void,
      signal?: AbortSignal,
    ): Promise<void> => {
      const res = await fetch(`${BASE_URL}/kernel/chat/stream`, {
        method: "POST",
        headers: { ...getHeaders(), Accept: "text/event-stream" },
        body: JSON.stringify({ message, target_agent }),
        signal,
      });
      if (!res.ok || !res.body) throw new Error(`chat stream failed: ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";
        for (const frame of frames) {
          const line = frame.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          try {
            onEvent(JSON.parse(line.slice(6)));
          } catch {
            /* ignore keep-alive/comment frames */
          }
        }
      }
    },
```

(`BASE_URL` and `getHeaders` already exist in `api.ts:1-11`; reuse them. Do not use `EventSource` — it
cannot send the `Authorization`/`X-Tenant-ID` headers.)

- [ ] **Step 3: Verify build + lint**

```bash
cd dashboard && npm run lint && npm run build
```
Expected: passes (types resolve; no unused-var/any-rule violations beyond the file's existing `any` usage).

- [ ] **Step 4: Commit**

```bash
git add dashboard/lib/api.ts
git commit -m "feat(dashboard): kernel.chatStream SSE client + target_agent on route

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Frontend — unified streaming chat surface

**Files:**
- Create: `dashboard/components/persona-chat.tsx`
- Modify: `dashboard/app/(mobile)/m/chat/page.tsx` (mount the persona picker + streaming view)
- Reference: `docs/design/mockups/jarvis-streaming-chat.html` (exact layout/behavior)
- Test: `dashboard` build + manual.

**Interfaces:**
- Consumes: `api.kernel.chatStream` (Task 5).
- Produces: `<PersonaChat />` — a chat thread with a persona picker (default `jarvis`), collapsible
  delegation step chips, and a live-streaming synthesis bubble, matching the mockup.

- [ ] **Step 1: Create `dashboard/components/persona-chat.tsx`**

State model driven by the chat events. Each assistant turn holds:
`{ synthesis: string; steps: Record<childId, {persona, text, done}>; order: childId[]; done: boolean }`.

```tsx
"use client";
import { useRef, useState } from "react";
import { api } from "@/lib/api";

type Step = { persona: string; text: string; done: boolean };
type Turn = { user: string; synthesis: string; steps: Record<string, Step>; order: string[]; done: boolean };

const PERSONAS = [
  { id: "jarvis", label: "Jarvis · coordinator" },
  { id: "tutor", label: "Tutor" }, { id: "swe-lead", label: "SWE-Lead" },
  { id: "scout", label: "Scout" }, { id: "admin", label: "Admin" },
];

export function PersonaChat() {
  const [persona, setPersona] = useState("jarvis");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const abort = useRef<AbortController | null>(null);

  function patchLast(fn: (t: Turn) => Turn) {
    setTurns((ts) => ts.map((t, i) => (i === ts.length - 1 ? fn(t) : t)));
  }

  async function send() {
    const msg = input.trim();
    if (!msg || streaming) return;
    setInput("");
    setTurns((ts) => [...ts, { user: msg, synthesis: "", steps: {}, order: [], done: false }]);
    setStreaming(true);
    abort.current = new AbortController();
    try {
      await api.kernel.chatStream(msg, persona, (e) => {
        if (e.type === "assistant_delta") patchLast((t) => ({ ...t, synthesis: t.synthesis + e.text }));
        else if (e.type === "delegation_start")
          patchLast((t) => t.steps[e.child_id] ? t
            : { ...t, order: [...t.order, e.child_id], steps: { ...t.steps, [e.child_id]: { persona: e.persona, text: "", done: false } } });
        else if (e.type === "child_delta")
          patchLast((t) => ({ ...t, steps: { ...t.steps, [e.child_id]: { ...t.steps[e.child_id], text: (t.steps[e.child_id]?.text ?? "") + e.text } } }));
        else if (e.type === "child_done")
          patchLast((t) => ({ ...t, steps: { ...t.steps, [e.child_id]: { ...t.steps[e.child_id], done: true } } }));
        else if (e.type === "done") patchLast((t) => ({ ...t, done: true }));
        else if (e.type === "error") patchLast((t) => ({ ...t, synthesis: t.synthesis + `\n[error: ${e.message}]`, done: true }));
      }, abort.current.signal);
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="persona-chat">
      <header>
        <span>Talking to</span>
        <select value={persona} onChange={(e) => setPersona(e.target.value)}>
          {PERSONAS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
      </header>
      <div className="thread">
        {turns.map((t, i) => (
          <div key={i} className="turn">
            <div className="user">{t.user}</div>
            <div className="steps">
              {t.order.map((cid) => (
                <div key={cid} className={`chip ${open[cid] ? "open" : ""}`}>
                  <button onClick={() => setOpen((o) => ({ ...o, [cid]: !o[cid] }))}>
                    {t.steps[cid].done ? "✓" : "…"} {t.steps[cid].persona}
                  </button>
                  {open[cid] && <pre className="chip-body">{t.steps[cid].text}</pre>}
                </div>
              ))}
            </div>
            <div className="synthesis">{t.synthesis}{!t.done && streaming && i === turns.length - 1 ? "▍" : ""}</div>
          </div>
        ))}
      </div>
      <div className="composer">
        <input value={input} onChange={(e) => setInput(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && send()} placeholder={`Message ${persona}…`} />
        {streaming
          ? <button onClick={() => abort.current?.abort()}>Stop</button>
          : <button onClick={send}>Send</button>}
      </div>
    </div>
  );
}
```

(Styling: reuse the mockup's CSS classes — port `docs/design/mockups/jarvis-streaming-chat.html`'s styles
into the dashboard's styling system, or a co-located CSS module. Match the collapsible-chip + streaming
look exactly.)

- [ ] **Step 2: Mount it in the chat surface** (`dashboard/app/(mobile)/m/chat/page.tsx`)

Add a mode/persona toggle: the existing "Ask my memories" `conversations` view stays; when a persona
other than the memory option is selected, render `<PersonaChat />`. Minimal wiring: import and render
`<PersonaChat />` as the default tab; keep the memory chat reachable via the picker's "Ask my memories"
entry (which continues to use `useSendMessage`/`conversations`). Do not delete the memory-chat code.

- [ ] **Step 3: Build**

```bash
cd dashboard && npm run lint && npm run build
```
Expected: passes.

- [ ] **Step 4: Commit**

```bash
git add dashboard/components/persona-chat.tsx "dashboard/app/(mobile)/m/chat/page.tsx"
git commit -m "feat(dashboard): unified streaming persona chat (Jarvis picker + delegation steps)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (after all tasks)

- [ ] **Backend unit + integration green:** `/c/Python314/python.exe -m pytest tests/unit/ tests/integration/test_chat_stream_endpoint.py -q`.
- [ ] **Lint clean:** `ruff check life_graph/services/chat_stream.py life_graph/api/kernel.py life_graph/kernel/process_manager.py life_graph/core/task_context.py life_graph/kernel/personas.py`.
- [ ] **Dashboard builds:** `cd dashboard && npm run build`.
- [ ] **The real gate (manual, controller-run):** deploy the branch to the VM (rebuild app + reconnect `web` network — no worker rebuild needed since it's the web process; no migration), open the chat, select Jarvis, send a two-role prompt, and confirm: step chips appear and complete, Jarvis's synthesis streams token-by-token, expanding a chip shows that role's answer, and the final text matches the task's stored `result.response`. Confirm Jarvis no longer over-delegates to one role. If the stream feel needs tuning, iterate on the mapper/UI before merging.

---

## Self-Review notes (author)

- **Spec coverage:** in-process session bus (T1), streaming persona execution via publish (T2), SSE endpoint + event-protocol mapping (T3), Jarvis coordination tune-up (T4), frontend streaming client (T5) + unified chat UI with collapsible steps (T6), manual gate (final). Live child streaming = T2 publishes for every task incl. children + T3 maps depth≥1 → child events. All spec sections map to a task.
- **Type consistency:** chat events (`assistant_delta{text}`, `delegation_start{child_id,persona}`,
  `child_delta{child_id,persona,text}`, `child_done{child_id,persona}`, `done`, `error{message}`) identical
  across mapper (T3), endpoint (T3), and frontend (T5/T6). Bus event shape `{task_id,agent_name,depth,event}`
  identical in T2 (publish) and T3 (map). `TaskContext.root_task_id/depth` defined T2, read T2.
- **Reused unchanged:** `ProcessManager.spawn`, `delegate_to_persona`, orchestrator, task-tree — no edits to
  delegation semantics; streaming is purely additive (a publish call + a new endpoint + frontend).
- **No Redis:** the bus is in-process; the only mock in tests is the LLM (`AgentOrchestrator.run`).
