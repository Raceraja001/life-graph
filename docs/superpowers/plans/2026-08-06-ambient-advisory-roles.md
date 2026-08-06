# Ambient Advisory Roles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scout`/`admin`/`tutor` run on a daily schedule, emit structured findings, and reach the user as immediate push (urgent) or via the existing daily brief (everything else).

**Architecture:** A per-minute ARQ cron ticks the existing `SchedulerService` (which already spawns persona tasks) — the one missing primitive. For advisory jobs the ticker composes an enriched prompt (watch-list + novelty + memory signal) and fires with an input override. A `FindingsBridge`, subscribed on `TASK_COMPLETED` **in the ARQ worker** (where scheduled tasks run) and in the web lifespan, parses each advisory run's trailing JSON findings into `Notification`s and pushes the urgent ones directly. No new tables; reuses `ScheduledJob.input`, `Notification`, `PushService`, and the daily brief.

**Tech Stack:** Python 3.11+ (tests via `/c/Python314/python.exe`), FastAPI, SQLAlchemy 2.0 async, ARQ (cron + worker), pgvector/AGE Postgres, Next.js 16 / React 19 dashboard.

## Global Constraints

- Repo is off `origin/master @ b64255a`. Run backend tests with `/c/Python314/python.exe -m pytest`.
- **Every DB query filters by `tenant_id`.** Set tenant context in worker loops via `set_tenant_context(tenant_id, "system")`.
- **Advisory personas stay read-only.** scout/admin/tutor `allowed_tools` must contain only read tools; the headless path already enforces `allowed_tools` (`process_manager.py:504-509`, `orchestrator.py:84-87`) — do not weaken it.
- **Ambient cron must run before `settings.brief_hour_utc` (= 2, i.e. 02:00 UTC)** so findings make that day's brief. Use `0 1 * * *` (01:00 UTC).
- **No new database tables or migrations.** Watch-list → `ScheduledJob.input`; findings + novelty → `Notification`.
- `Event` attribute is `.type` and `.payload` (NOT `.event_type`). Handler shape: `async def handler(event: Event) -> None`.
- `NotificationEngine.create(...)` keyword is `metadata=` (stored to the `extra_metadata` column). Valid `priority`: `{"critical","important","info"}`. `source_id` must be a UUID string or `None`.
- `SchedulerService` methods return **plain dicts**; `id`/`next_run_at` in those dicts are **strings**.
- Persona seeding **skips personas that already exist** — code prompt changes do NOT reach live DB rows; a deploy-time DB re-sync of scout/admin/tutor prompts is required (documented in Task 8, out-of-band at deploy like the jarvis prompt sync).
- Lint: `ruff` line-length 100, double quotes. Public APIs get type hints + docstrings.
- Commit trailer, exactly:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## File Structure

- `life_graph/kernel/ambient.py` **(new)** — `AMBIENT_ADVISORY` constant, ambient `ScheduledJob` definitions, `seed_ambient_jobs()`.
- `life_graph/services/findings_bridge.py` **(new)** — `FindingsBridge` (parse findings JSON → notifications + urgent push) and its `TASK_COMPLETED` handler + `subscribe()`.
- `life_graph/services/ambient_context.py` **(new)** — `AmbientContextBuilder.build()` composing the enriched prompt (watch-list + novelty + memory signal).
- `life_graph/kernel/scheduler.py` **(modify)** — `fire_job` gains `input_override`.
- `life_graph/workers/tasks.py` **(modify)** — `tick_scheduled_jobs` cron.
- `life_graph/workers/settings.py` **(modify)** — register the cron (functions + cron entry) and add `on_startup` wiring the FindingsBridge in the worker.
- `life_graph/main.py` **(modify)** — seed ambient jobs at startup; subscribe FindingsBridge in the web lifespan.
- `life_graph/kernel/personas.py` **(modify)** — append the findings-JSON output contract to scout/admin/tutor prompts.
- `dashboard/lib/api.ts` **(modify)** — add `kernel.schedules` client group.
- `dashboard/app/(mobile)/m/schedules/page.tsx` **(new)** + `dashboard/components/ambient-roles.tsx` **(new)** — ambient settings UI.
- Tests: `tests/unit/test_findings_bridge.py`, `tests/unit/test_scheduler_tick.py`, `tests/unit/test_ambient_seed.py`, `tests/unit/test_ambient_context.py`, `tests/unit/test_ambient_personas.py`, `tests/integration/test_ambient_advisory_safety.py`, `tests/integration/test_ambient_end_to_end.py`.

---

### Task 1: FindingsBridge core (parse → notifications + urgent push)

Pure logic first: given a task-result string, produce notifications and push urgent ones. No event wiring yet.

**Files:**
- Create: `life_graph/services/findings_bridge.py`
- Test: `tests/unit/test_findings_bridge.py`

**Interfaces:**
- Consumes: `NotificationEngine.create(tenant_id, title, body=None, *, priority="info", channel="terminal", source_type=None, source_id=None, metadata=None, deliver_at_brief=False) -> dict`; `PushService.send_to_tenant(tenant_id, title, body, url="/m") -> int`.
- Produces: `parse_findings(result_text: str) -> list[dict]` (each `{"title","detail","urgency"}`, `urgency ∈ {"now","brief"}`); `class FindingsBridge` with `async def process_result(self, tenant_id: str, agent_name: str, task_id: str, result_text: str) -> int` (returns count of notifications created).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_findings_bridge.py
import pytest
from life_graph.services.findings_bridge import parse_findings


def test_parse_findings_extracts_trailing_json_array():
    text = 'Here is what I found.\n[{"title":"A","detail":"d1","urgency":"now"},{"title":"B","detail":"d2","urgency":"brief"}]'
    out = parse_findings(text)
    assert out == [
        {"title": "A", "detail": "d1", "urgency": "now"},
        {"title": "B", "detail": "d2", "urgency": "brief"},
    ]


def test_parse_findings_handles_fenced_json():
    text = "prose\n```json\n[{\"title\":\"A\",\"detail\":\"d\",\"urgency\":\"brief\"}]\n```"
    assert parse_findings(text) == [{"title": "A", "detail": "d", "urgency": "brief"}]


def test_parse_findings_malformed_returns_empty_list():
    assert parse_findings("no json here at all") == []


def test_parse_findings_bad_urgency_coerced_to_brief():
    text = '[{"title":"A","detail":"d","urgency":"whenever"}]'
    assert parse_findings(text) == [{"title": "A", "detail": "d", "urgency": "brief"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_findings_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: life_graph.services.findings_bridge`.

- [ ] **Step 3: Implement `parse_findings`**

```python
# life_graph/services/findings_bridge.py
"""Turn an advisory persona's finished run into notifications.

scout/admin/tutor end their reply with a JSON array of findings; this module
extracts them and (Task 2) creates a Notification per finding, pushing urgent
ones immediately. Malformed/absent JSON falls back to a single digest so a
finding is never silently dropped.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)

_VALID_URGENCY = {"now", "brief"}
# Last ``[ ... ]`` block in the text, across newlines.
_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def parse_findings(result_text: str) -> list[dict[str, Any]]:
    """Extract the trailing JSON findings array from a persona's reply.

    Returns a list of ``{"title","detail","urgency"}`` dicts. Unknown urgency
    values coerce to ``"brief"``. Returns ``[]`` when no valid array is found.
    """
    if not result_text:
        return []
    match = _ARRAY_RE.search(result_text)
    if not match:
        return []
    try:
        raw = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    findings: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or "title" not in item:
            continue
        urgency = item.get("urgency", "brief")
        if urgency not in _VALID_URGENCY:
            urgency = "brief"
        findings.append(
            {
                "title": str(item["title"])[:200],
                "detail": str(item.get("detail", "")),
                "urgency": urgency,
            }
        )
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_findings_bridge.py -v`
Expected: PASS.

- [ ] **Step 5: Add `FindingsBridge.process_result` with a failing test**

```python
# add to tests/unit/test_findings_bridge.py
import pytest
from unittest.mock import AsyncMock
from life_graph.services.findings_bridge import FindingsBridge


@pytest.mark.asyncio
async def test_process_result_creates_notifications_and_pushes_urgent():
    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n1"})
    push = AsyncMock()
    push.send_to_tenant = AsyncMock(return_value=1)
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    text = '[{"title":"Urgent","detail":"do x","urgency":"now"},{"title":"Later","detail":"fyi","urgency":"brief"}]'
    n = await bridge.process_result("t1", "scout", "11111111-1111-1111-1111-111111111111", text)

    assert n == 2
    # brief finding: held for brief, no push
    engine.create.assert_any_await(
        "t1", "Later", body="fyi", priority="info",
        source_type="scout", source_id="11111111-1111-1111-1111-111111111111",
        deliver_at_brief=True,
    )
    # urgent finding: important + immediate push
    engine.create.assert_any_await(
        "t1", "Urgent", body="do x", priority="important",
        source_type="scout", source_id="11111111-1111-1111-1111-111111111111",
        deliver_at_brief=False,
    )
    push.send_to_tenant.assert_awaited_once_with("t1", "Urgent", "do x", "/m")


@pytest.mark.asyncio
async def test_process_result_malformed_falls_back_to_single_brief_digest():
    engine = AsyncMock()
    engine.create = AsyncMock(return_value={"id": "n1"})
    push = AsyncMock()
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    n = await bridge.process_result("t1", "admin", "22222222-2222-2222-2222-222222222222", "free-text, no json")

    assert n == 1
    args, kwargs = engine.create.call_args
    assert kwargs["deliver_at_brief"] is True
    assert kwargs["priority"] == "info"
    push.send_to_tenant.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_result_empty_array_creates_nothing():
    engine = AsyncMock()
    engine.create = AsyncMock()
    push = AsyncMock()
    bridge = FindingsBridge(notification_engine=engine, push_service=push)
    n = await bridge.process_result("t1", "scout", "33333333-3333-3333-3333-333333333333", "[]")
    assert n == 0
    engine.create.assert_not_awaited()
```

- [ ] **Step 6: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_findings_bridge.py -v`
Expected: FAIL — `FindingsBridge` not defined.

- [ ] **Step 7: Implement `FindingsBridge.process_result`**

```python
# append to life_graph/services/findings_bridge.py

_PRIORITY = {"now": "important", "brief": "info"}


class FindingsBridge:
    """Convert an advisory run's findings into notifications (+ urgent push)."""

    def __init__(self, notification_engine: Any, push_service: Any) -> None:
        self._notifications = notification_engine
        self._push = push_service

    async def process_result(
        self, tenant_id: str, agent_name: str, task_id: str, result_text: str
    ) -> int:
        """Parse findings and create a notification per finding.

        Urgent (``urgency="now"``) findings are created at ``important`` and
        pushed to the phone immediately; the rest are held for the daily brief.
        Malformed/absent JSON becomes one held digest notification. Returns the
        number of notifications created.
        """
        findings = parse_findings(result_text)
        if not findings and result_text.strip():
            findings = [{"title": f"{agent_name} update", "detail": result_text.strip(), "urgency": "brief"}]

        created = 0
        for f in findings:
            urgent = f["urgency"] == "now"
            try:
                await self._notifications.create(
                    tenant_id,
                    f["title"],
                    body=f["detail"] or None,
                    priority=_PRIORITY[f["urgency"]],
                    source_type=agent_name,
                    source_id=task_id,
                    deliver_at_brief=not urgent,
                )
                created += 1
            except Exception:  # one bad finding must not drop the rest
                logger.warning("Findings bridge: notification create failed", exc_info=True)
                continue
            if urgent:
                try:
                    await self._push.send_to_tenant(tenant_id, f["title"], f["detail"], "/m")
                except Exception:  # delivery must never break the flow
                    logger.warning("Findings bridge: urgent push failed", exc_info=True)
        return created
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_findings_bridge.py -v`
Expected: PASS (all).

- [ ] **Step 9: Commit**

```bash
git add life_graph/services/findings_bridge.py tests/unit/test_findings_bridge.py
git commit -m "feat(ambient): findings bridge core — parse JSON findings, create notifications, push urgent

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Wire FindingsBridge to TASK_COMPLETED (worker + web)

Subscribe the bridge on `TASK_COMPLETED`, gated to advisory personas, loading the `AgentTask` by id.

**Files:**
- Modify: `life_graph/services/findings_bridge.py` (add module singleton + `_on_task_completed` + `subscribe`)
- Create: `life_graph/kernel/ambient.py` (the `AMBIENT_ADVISORY` constant — imported here and by Tasks 5/7)
- Test: `tests/unit/test_findings_bridge.py` (add handler tests)

**Interfaces:**
- Consumes: `EventType.TASK_COMPLETED` payload `{"task_id","tenant_id","agent_name","token_usage"}`; `AgentTask` columns `id`, `tenant_id`, `agent_name`, `status`, `result` (`result["response"]`); `get_notification_engine()`; `PushService(async_session)`; `event_bus.subscribe(EventType.TASK_COMPLETED, handler)`.
- Produces: `AMBIENT_ADVISORY: frozenset[str]`; module singleton `findings_bridge_handler` with `subscribe() -> None`.

- [ ] **Step 1: Create the constant module**

```python
# life_graph/kernel/ambient.py
"""Ambient advisory roles: the personas that run on a schedule and only report."""

from __future__ import annotations

AMBIENT_ADVISORY: frozenset[str] = frozenset({"scout", "admin", "tutor"})
```

- [ ] **Step 2: Write the failing handler test**

```python
# add to tests/unit/test_findings_bridge.py
import uuid as _uuid
from unittest.mock import AsyncMock, patch
from life_graph.core.events import Event, EventType


@pytest.mark.asyncio
async def test_handler_ignores_non_advisory_persona():
    from life_graph.services.findings_bridge import FindingsBridgeHandler
    handler = FindingsBridgeHandler()
    handler._bridge = AsyncMock()
    ev = Event(type=EventType.TASK_COMPLETED,
               payload={"task_id": str(_uuid.uuid4()), "tenant_id": "t1", "agent_name": "cody"})
    await handler._on_task_completed(ev)
    handler._bridge.process_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_processes_advisory_task_result():
    from life_graph.services import findings_bridge as fb
    handler = fb.FindingsBridgeHandler()
    handler._bridge = AsyncMock()
    tid = str(_uuid.uuid4())
    ev = Event(type=EventType.TASK_COMPLETED,
               payload={"task_id": tid, "tenant_id": "t1", "agent_name": "scout"})

    class _Row:
        result = {"response": "[]"}
    with patch.object(fb, "_load_task_result", AsyncMock(return_value="[]")):
        await handler._on_task_completed(ev)
    handler._bridge.process_result.assert_awaited_once_with("t1", "scout", tid, "[]")
```

- [ ] **Step 3: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_findings_bridge.py -k handler -v`
Expected: FAIL — `FindingsBridgeHandler` not defined.

- [ ] **Step 4: Implement handler + subscribe + singleton**

```python
# append to life_graph/services/findings_bridge.py
import uuid
from sqlalchemy import select

from life_graph.core.events import Event, EventType, event_bus
from life_graph.kernel.ambient import AMBIENT_ADVISORY


async def _load_task_result(tenant_id: str, task_id: str) -> str | None:
    """Load a completed AgentTask's response text, tenant-scoped."""
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as session:
        row = (
            await session.execute(
                select(AgentTask).where(
                    AgentTask.id == uuid.UUID(task_id),
                    AgentTask.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    if row is None or not isinstance(row.result, dict):
        return None
    return row.result.get("response")


class FindingsBridgeHandler:
    """Subscribes TASK_COMPLETED and bridges advisory runs to notifications."""

    def __init__(self) -> None:
        self._subscribed = False
        self._bridge: FindingsBridge | None = None

    def _get_bridge(self) -> FindingsBridge:
        if self._bridge is None:
            from life_graph.api.dependencies import get_notification_engine
            from life_graph.services.webpush import PushService
            from life_graph.storage.database import async_session

            self._bridge = FindingsBridge(
                notification_engine=get_notification_engine(),
                push_service=PushService(async_session),
            )
        return self._bridge

    def subscribe(self) -> None:
        if self._subscribed:
            return
        event_bus.subscribe(EventType.TASK_COMPLETED, self._on_task_completed)
        self._subscribed = True

    async def _on_task_completed(self, event: Event) -> None:
        try:
            data = event.payload
            agent_name = data.get("agent_name", "")
            if agent_name not in AMBIENT_ADVISORY:
                return
            tenant_id = data.get("tenant_id")
            task_id = data.get("task_id")
            if not tenant_id or not task_id:
                return
            result_text = await _load_task_result(tenant_id, task_id)
            if result_text is None:
                return
            await self._get_bridge().process_result(tenant_id, agent_name, task_id, result_text)
        except Exception:  # a bridge failure must never break task completion
            logger.warning("FindingsBridge handler failed", exc_info=True)


findings_bridge_handler = FindingsBridgeHandler()
```

(Note the test patches `handler._bridge` directly, so `_get_bridge` isn't exercised there.)

- [ ] **Step 5: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_findings_bridge.py -v`
Expected: PASS.

- [ ] **Step 6: Subscribe in the web lifespan**

In `life_graph/main.py`, next to the existing `push_delivery_handler.subscribe()` block (around line 176-182), add:

```python
    # Startup — wire advisory runs -> notifications/push
    try:
        from life_graph.services.findings_bridge import findings_bridge_handler
        findings_bridge_handler.subscribe()
        logger.info("Ambient findings bridge enabled (web)")
    except Exception:
        logger.warning("Findings bridge not available", exc_info=True)
```

- [ ] **Step 7: Subscribe in the ARQ worker on_startup**

In `life_graph/workers/settings.py`, add an `on_startup` to `WorkerSettings` (the class currently has none). If an `on_startup` already exists, append to it instead.

```python
    @staticmethod
    async def on_startup(ctx: dict) -> None:
        # Scheduled advisory tasks run in THIS worker process; the bridge must be
        # subscribed here (worker-emitted events don't reach web subscribers).
        from life_graph.services.findings_bridge import findings_bridge_handler
        findings_bridge_handler.subscribe()
```

- [ ] **Step 8: Verify nothing broke**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_findings_bridge.py -v`
Expected: PASS. (main.py / settings.py wiring is import-only; no test asserts on it directly here — Task 11 integration covers end-to-end.)

- [ ] **Step 9: Commit**

```bash
git add life_graph/services/findings_bridge.py life_graph/kernel/ambient.py life_graph/main.py life_graph/workers/settings.py tests/unit/test_findings_bridge.py
git commit -m "feat(ambient): wire findings bridge to TASK_COMPLETED in worker + web

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Scheduler ticker cron

The missing trigger: a per-minute cron that fires due scheduled jobs.

**Files:**
- Modify: `life_graph/workers/tasks.py` (add `tick_scheduled_jobs`)
- Modify: `life_graph/workers/settings.py` (register in `functions` + `cron_jobs`)
- Test: `tests/unit/test_scheduler_tick.py`

**Interfaces:**
- Consumes: `get_scheduler_service()` → `SchedulerService`; `scheduler.get_due_jobs(None) -> list[dict]` (each dict has `"id"`, `"tenant_id"`, `"agent_name"`); `scheduler.fire_job(tenant_id, job_id) -> dict | None`; `set_tenant_context(tenant_id, "system")`.
- Produces: `async def tick_scheduled_jobs(ctx: dict) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_scheduler_tick.py
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_tick_fires_each_due_job_and_isolates_failures():
    from life_graph.workers import tasks

    scheduler = AsyncMock()
    scheduler.get_due_jobs = AsyncMock(return_value=[
        {"id": "j1", "tenant_id": "t1", "agent_name": "scout"},
        {"id": "j2", "tenant_id": "t2", "agent_name": "admin"},
    ])
    # j1 raises, j2 must still fire
    scheduler.fire_job = AsyncMock(side_effect=[RuntimeError("boom"), {"task_id": "x"}])

    with patch.object(tasks, "get_scheduler_service", return_value=scheduler), \
         patch.object(tasks, "set_tenant_context") as set_ctx:
        out = await tasks.tick_scheduled_jobs({})

    assert scheduler.fire_job.await_count == 2
    assert out["fired"] == 1
    assert out["failed"] == 1
    set_ctx.assert_any_call("t1", "system")
    set_ctx.assert_any_call("t2", "system")
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_scheduler_tick.py -v`
Expected: FAIL — `tick_scheduled_jobs` not defined (or `get_scheduler_service` not importable in `tasks`).

- [ ] **Step 3: Implement the cron task**

Add to `life_graph/workers/tasks.py` (module already imports `set_tenant_context` at the top; add a lazy import of the scheduler provider inside the function per the file's convention):

```python
async def tick_scheduled_jobs(ctx: dict) -> dict:
    """Per-minute cron: fire every kernel ScheduledJob whose next_run_at has passed.

    Uses the ProcessManager singleton belonging to THIS worker (advisory tasks
    then run + emit TASK_COMPLETED here, where the findings bridge is subscribed).
    Each job is fired in isolation so one failure never blocks the rest.
    """
    from life_graph.api.dependencies import get_scheduler_service

    scheduler = get_scheduler_service()
    due = await scheduler.get_due_jobs(None)
    fired = 0
    failed = 0
    for job in due:
        try:
            set_tenant_context(job["tenant_id"], "system")
            await scheduler.fire_job(job["tenant_id"], job["id"])
            fired += 1
        except Exception:
            logger.exception("tick_scheduled_jobs: fire failed for job %s", job.get("id"))
            failed += 1
    if due:
        logger.info("tick_scheduled_jobs: %d fired, %d failed", fired, failed)
    return {"due": len(due), "fired": fired, "failed": failed}
```

For the test's `patch.object(tasks, "get_scheduler_service", ...)` to work, add `from life_graph.api.dependencies import get_scheduler_service` at module import time is NOT desired (the file lazy-imports). Instead, the test patches the name where it is looked up — so import it at module top of `tasks.py`:

```python
# near the other imports at the top of life_graph/workers/tasks.py
from life_graph.api.dependencies import get_scheduler_service
```

(If a top-level import causes a circular import at worker start, keep the import inside the function and change the test to `patch("life_graph.api.dependencies.get_scheduler_service", ...)`. Verify which works when implementing; prefer the top-level import if it loads cleanly.)

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_scheduler_tick.py -v`
Expected: PASS.

- [ ] **Step 5: Register the cron**

In `life_graph/workers/settings.py`:
- Add `"life_graph.workers.tasks.tick_scheduled_jobs"` to the `functions` list.
- Add to `cron_jobs`:

```python
        cron(
            "life_graph.workers.tasks.tick_scheduled_jobs",
            minute=set(range(60)),  # every minute
            run_at_startup=False,
        ),
```

- [ ] **Step 6: Sanity-import the worker settings**

Run: `/c/Python314/python.exe -c "import life_graph.workers.settings as s; assert any('tick_scheduled_jobs' in str(j) for j in s.WorkerSettings.cron_jobs)"`
Expected: no error.

- [ ] **Step 7: Commit**

```bash
git add life_graph/workers/tasks.py life_graph/workers/settings.py tests/unit/test_scheduler_tick.py
git commit -m "feat(ambient): per-minute scheduler ticker fires due jobs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `fire_job` input override

Let the ticker pass an enriched prompt without persisting it to the job.

**Files:**
- Modify: `life_graph/kernel/scheduler.py` (`fire_job` signature + spawn call, ~`:436-476`)
- Test: `tests/unit/test_scheduler_tick.py` (add)

**Interfaces:**
- Produces: `fire_job(self, tenant_id: str, job_id: str, input_override: dict[str, Any] | None = None) -> dict | None` — passes `input_override` to `spawn(input_data=...)` when provided, else `job["input"]`. All existing bookkeeping unchanged.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/unit/test_scheduler_tick.py
@pytest.mark.asyncio
async def test_fire_job_uses_input_override(monkeypatch):
    from life_graph.kernel.scheduler import SchedulerService

    svc = SchedulerService.__new__(SchedulerService)  # bypass __init__
    svc._max_failures = 3
    pm = AsyncMock()
    pm.spawn = AsyncMock(return_value={"task_id": "tk", "status": "queued"})
    svc._process_manager = pm

    async def fake_get(tenant_id, job_id):
        return {"id": job_id, "name": "scout-daily", "agent_name": "scout",
                "is_active": True, "input": {"topics": ["x"]},
                "timeout_seconds": 600, "max_retries": 3}
    monkeypatch.setattr(svc, "get_by_id", fake_get)
    monkeypatch.setattr(svc, "_record_run", AsyncMock())

    await svc.fire_job("t1", "j1", input_override={"message": "ENRICHED"})

    _, kwargs = pm.spawn.call_args
    assert kwargs["input_data"] == {"message": "ENRICHED"}
```

(Adjust the monkeypatched internals to match `fire_job`'s actual reads — inspect `scheduler.py:436-476` first; it emits `SCHEDULE_FIRED`, loads the job, spawns, and calls `_record_run`. Patch only what the method touches.)

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_scheduler_tick.py -k input_override -v`
Expected: FAIL — `fire_job()` got an unexpected keyword `input_override`.

- [ ] **Step 3: Add the parameter**

In `life_graph/kernel/scheduler.py`, change the `fire_job` signature to add `input_override: dict[str, Any] | None = None`, and in the `spawn` call change:

```python
            input_data=job.get("input", {}),
```
to:
```python
            input_data=input_override if input_override is not None else job.get("input", {}),
```

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_scheduler_tick.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add life_graph/kernel/scheduler.py tests/unit/test_scheduler_tick.py
git commit -m "feat(ambient): fire_job accepts input_override for enriched ambient prompts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Ambient job definitions + seeding

Seed `scout-daily`, `admin-daily`, `tutor-daily` (tutor inactive) per tenant, idempotently.

**Files:**
- Modify: `life_graph/kernel/ambient.py` (add job defs + `seed_ambient_jobs`)
- Modify: `life_graph/main.py` (call seeding at startup)
- Test: `tests/unit/test_ambient_seed.py`

**Interfaces:**
- Consumes: `SchedulerService.create(tenant_id, data: dict) -> dict` (raises `ValueError` "already exists" on duplicate name); `SchedulerService.list_all(tenant_id, include_inactive=True) -> tuple[list[dict], int]`; `SchedulerService.update(tenant_id, job_id, {"is_active": False}) -> dict | None`.
- Produces: `AMBIENT_JOBS: list[dict]`; `async def seed_ambient_jobs(scheduler, tenant_id: str) -> int` (count created).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_ambient_seed.py
import pytest
from unittest.mock import AsyncMock
from life_graph.kernel.ambient import seed_ambient_jobs, AMBIENT_JOBS


@pytest.mark.asyncio
async def test_seed_creates_missing_jobs_and_deactivates_tutor():
    scheduler = AsyncMock()
    scheduler.list_all = AsyncMock(return_value=([], 0))  # nothing exists yet
    created_rows = {j["name"]: {"id": j["name"], "name": j["name"]} for j in AMBIENT_JOBS}
    scheduler.create = AsyncMock(side_effect=lambda t, d: created_rows[d["name"]])
    scheduler.update = AsyncMock(return_value={"id": "tutor-daily"})

    n = await seed_ambient_jobs(scheduler, "default")

    assert n == 3
    names = [c.args[1]["name"] for c in scheduler.create.await_args_list]
    assert set(names) == {"scout-daily", "admin-daily", "tutor-daily"}
    # tutor deactivated after creation
    scheduler.update.assert_awaited_once()
    assert scheduler.update.await_args.args[1] == "tutor-daily"


@pytest.mark.asyncio
async def test_seed_is_idempotent_when_jobs_exist():
    scheduler = AsyncMock()
    scheduler.list_all = AsyncMock(return_value=(
        [{"name": "scout-daily"}, {"name": "admin-daily"}, {"name": "tutor-daily"}], 3))
    scheduler.create = AsyncMock()
    n = await seed_ambient_jobs(scheduler, "default")
    assert n == 0
    scheduler.create.assert_not_awaited()
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_ambient_seed.py -v`
Expected: FAIL — `AMBIENT_JOBS` / `seed_ambient_jobs` not defined.

- [ ] **Step 3: Implement job defs + seeder**

```python
# append to life_graph/kernel/ambient.py
# NOTE: `from __future__ import annotations` already sits at the top from Task 2 — do
# NOT re-add it (it must be the first statement). Add `import logging` and
# `from typing import Any` up near the top of the file, below the __future__ import.
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Cron 01:00 UTC — before settings.brief_hour_utc (=2) so findings make the brief.
AMBIENT_JOBS: list[dict[str, Any]] = [
    {
        "name": "scout-daily",
        "cron_expression": "0 1 * * *",
        "agent_name": "scout",
        "description": "Ambient research on your watch-list; surfaces new findings.",
        "input": {"topics": []},
        "active": True,
    },
    {
        "name": "admin-daily",
        "cron_expression": "0 1 * * *",
        "agent_name": "admin",
        "description": "Surfaces work/life admin items needing attention.",
        "input": {},
        "active": True,
    },
    {
        "name": "tutor-daily",
        "cron_expression": "0 1 * * *",
        "agent_name": "tutor",
        "description": "Proactive learning nudges (opt-in).",
        "input": {},
        "active": False,
    },
]


async def seed_ambient_jobs(scheduler: Any, tenant_id: str) -> int:
    """Create the ambient ScheduledJobs for a tenant if absent. Idempotent.

    Mirrors PersonaService.seed_builtins: diff by name, create only the missing.
    tutor-daily is created then deactivated (create has no is_active field).
    Returns the number of jobs created.
    """
    existing, _ = await scheduler.list_all(tenant_id, include_inactive=True)
    existing_names = {j["name"] for j in existing}
    created = 0
    for defn in AMBIENT_JOBS:
        if defn["name"] in existing_names:
            continue
        try:
            row = await scheduler.create(
                tenant_id,
                {
                    "name": defn["name"],
                    "cron_expression": defn["cron_expression"],
                    "agent_name": defn["agent_name"],
                    "description": defn["description"],
                    "input": defn["input"],
                },
            )
            created += 1
            if not defn["active"] and row and row.get("id"):
                await scheduler.update(tenant_id, row["id"], {"is_active": False})
        except ValueError:
            # Raced with another seeder for the same name — fine.
            logger.debug("Ambient job %s already exists for %s", defn["name"], tenant_id)
    return created
```

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_ambient_seed.py -v`
Expected: PASS.

- [ ] **Step 5: Wire seeding into the web lifespan**

In `life_graph/main.py`, next to the persona seeding block (`main.py:138-147`), add:

```python
    # Startup — seed ambient scheduled jobs for default tenant
    try:
        from life_graph.api.dependencies import get_scheduler_service
        from life_graph.kernel.ambient import seed_ambient_jobs

        seeded_jobs = await seed_ambient_jobs(get_scheduler_service(), "default")
        if seeded_jobs:
            logger.info("Seeded %d ambient scheduled jobs for default tenant", seeded_jobs)
    except Exception:
        logger.warning("Failed to seed ambient scheduled jobs", exc_info=True)
```

- [ ] **Step 6: Commit**

```bash
git add life_graph/kernel/ambient.py life_graph/main.py tests/unit/test_ambient_seed.py
git commit -m "feat(ambient): seed scout/admin/tutor daily jobs (tutor opt-in) idempotently

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Ambient context builder

Compose the enriched prompt: watch-list (primary) + novelty (no repeats) + best-effort memory signal.

**Files:**
- Create: `life_graph/services/ambient_context.py`
- Test: `tests/unit/test_ambient_context.py`

**Interfaces:**
- Consumes: `Notification` rows (`source_type`, `title`, `created_at`) for novelty; the `Memory` model for the memory signal (verify its recency + tags columns in Step 3).
- Produces: `async def build_ambient_input(agent_name: str, job_input: dict, tenant_id: str, *, novelty_days: int = 7) -> dict` — returns `{"message": <composed prompt str>}`.

- [ ] **Step 1: Write the failing test** (novelty + watch-list, memory signal mocked out)

```python
# tests/unit/test_ambient_context.py
import pytest
from unittest.mock import AsyncMock, patch
from life_graph.services import ambient_context as ac


@pytest.mark.asyncio
async def test_build_scout_input_includes_topics_and_novelty():
    with patch.object(ac, "_recent_finding_titles", AsyncMock(return_value=["Old thing"])), \
         patch.object(ac, "_memory_signal_tags", AsyncMock(return_value=["pgvector"])):
        out = await ac.build_ambient_input("scout", {"topics": ["Caddy", "local LLMs"]}, "t1")
    msg = out["message"]
    assert "Caddy" in msg and "local LLMs" in msg      # watch-list present
    assert "Old thing" in msg                          # novelty (do-not-repeat) present
    assert "pgvector" in msg                           # memory signal present
    assert "JSON" in msg                               # output contract reminder present


@pytest.mark.asyncio
async def test_build_admin_input_has_no_topics_section():
    with patch.object(ac, "_recent_finding_titles", AsyncMock(return_value=[])), \
         patch.object(ac, "_memory_signal_tags", AsyncMock(return_value=[])):
        out = await ac.build_ambient_input("admin", {}, "t1")
    assert "watch-list" not in out["message"].lower()
    assert "message" in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_ambient_context.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Inspect the Memory model before writing `_memory_signal_tags`**

Open `life_graph/models/db.py`, find the `Memory` model. Confirm the column holding tags (dynamic tag array) and the recency column (`created_at` / `updated_at`). Use those exact names in Step 4. If tags are stored inside the JSONB `properties` rather than a dedicated array column, adapt the query to read from there. The memory signal is best-effort — wrap it so any mismatch degrades to `[]` (watch-list still carries the run).

- [ ] **Step 4: Implement the builder**

```python
# life_graph/services/ambient_context.py
"""Compose the enriched prompt an ambient advisory persona runs on.

Watch-list topics are primary; recent memory tags are a secondary nudge; the
persona's own recent finding titles are injected so it does not repeat itself.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from life_graph.models.db import Notification
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)


async def _recent_finding_titles(agent_name: str, tenant_id: str, days: int) -> list[str]:
    """Titles of this persona's own notifications from the last `days` days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Notification.title).where(
                    Notification.tenant_id == tenant_id,
                    Notification.source_type == agent_name,
                    Notification.created_at >= since,
                )
            )
        ).all()
    return [r[0] for r in rows][:30]


async def _memory_signal_tags(tenant_id: str, limit: int = 5) -> list[str]:
    """Best-effort: a few salient recent memory tags to nudge research. Degrades to []."""
    try:
        from life_graph.models.db import Memory  # verify columns in Step 3

        async with async_session() as session:
            rows = (
                await session.execute(
                    select(Memory)
                    .where(Memory.tenant_id == tenant_id)
                    .order_by(Memory.created_at.desc())
                    .limit(40)
                )
            ).scalars().all()
        counts: dict[str, int] = {}
        for m in rows:
            for tag in (getattr(m, "tags", None) or []):
                counts[tag] = counts.get(tag, 0) + 1
        return [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:limit]
    except Exception:
        logger.debug("Memory signal unavailable; continuing with watch-list only", exc_info=True)
        return []


_CONTRACT = (
    "End your reply with ONLY a JSON array of findings, each "
    '{"title": str, "detail": str, "urgency": "now" | "brief"}. Use "now" only '
    "for genuinely time-sensitive items. Return [] if you have nothing new."
)


async def build_ambient_input(
    agent_name: str, job_input: dict, tenant_id: str, *, novelty_days: int = 7
) -> dict:
    """Build the {"message": ...} input for an ambient advisory run."""
    parts: list[str] = []
    if agent_name == "scout":
        topics = job_input.get("topics") or []
        if topics:
            parts.append("Your watch-list topics: " + ", ".join(str(t) for t in topics) + ".")
        else:
            parts.append("You have no watch-list topics yet; use recent memory signals below.")
    already = await _recent_finding_titles(agent_name, tenant_id, novelty_days)
    if already:
        parts.append(
            "You have ALREADY reported these recently — do not repeat them: "
            + "; ".join(already)
            + "."
        )
    tags = await _memory_signal_tags(tenant_id)
    if tags:
        parts.append("Recent interest signals from the user's memory: " + ", ".join(tags) + ".")
    parts.append(_CONTRACT)
    return {"message": "\n\n".join(parts)}
```

- [ ] **Step 5: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_ambient_context.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add life_graph/services/ambient_context.py tests/unit/test_ambient_context.py
git commit -m "feat(ambient): context builder — watch-list + novelty + memory signal

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Ticker enriches advisory jobs

Connect Tasks 3+4+6: the ticker composes enriched input for advisory jobs.

**Files:**
- Modify: `life_graph/workers/tasks.py` (`tick_scheduled_jobs`)
- Test: `tests/unit/test_scheduler_tick.py` (extend)

**Interfaces:**
- Consumes: `AMBIENT_ADVISORY`; `build_ambient_input(agent_name, job_input, tenant_id) -> dict`; `fire_job(tenant_id, job_id, input_override=...)`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/unit/test_scheduler_tick.py
@pytest.mark.asyncio
async def test_tick_enriches_advisory_jobs_only():
    from life_graph.workers import tasks

    scheduler = AsyncMock()
    scheduler.get_due_jobs = AsyncMock(return_value=[
        {"id": "j1", "tenant_id": "t1", "agent_name": "scout", "input": {"topics": ["x"]}},
        {"id": "j2", "tenant_id": "t1", "agent_name": "dependency-updater", "input": {}},
    ])
    scheduler.fire_job = AsyncMock(return_value={"task_id": "x"})

    with patch.object(tasks, "get_scheduler_service", return_value=scheduler), \
         patch.object(tasks, "set_tenant_context"), \
         patch.object(tasks, "build_ambient_input", AsyncMock(return_value={"message": "ENRICHED"})):
        await tasks.tick_scheduled_jobs({})

    # advisory job fired WITH override; non-advisory WITHOUT
    calls = {c.args[1]: c.kwargs.get("input_override") for c in scheduler.fire_job.await_args_list}
    assert calls["j1"] == {"message": "ENRICHED"}
    assert calls["j2"] is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_scheduler_tick.py -k enriches -v`
Expected: FAIL — `build_ambient_input` not imported in `tasks`; override not applied.

- [ ] **Step 3: Update the ticker**

At the top of `life_graph/workers/tasks.py` add imports:
```python
from life_graph.kernel.ambient import AMBIENT_ADVISORY
from life_graph.services.ambient_context import build_ambient_input
```
Change the loop body of `tick_scheduled_jobs`:
```python
        try:
            set_tenant_context(job["tenant_id"], "system")
            override = None
            if job["agent_name"] in AMBIENT_ADVISORY:
                override = await build_ambient_input(
                    job["agent_name"], job.get("input") or {}, job["tenant_id"]
                )
            await scheduler.fire_job(job["tenant_id"], job["id"], input_override=override)
            fired += 1
        except Exception:
            logger.exception("tick_scheduled_jobs: fire failed for job %s", job.get("id"))
            failed += 1
```

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_scheduler_tick.py -v`
Expected: PASS (all tick tests, including Task 3's).

- [ ] **Step 5: Commit**

```bash
git add life_graph/workers/tasks.py tests/unit/test_scheduler_tick.py
git commit -m "feat(ambient): ticker composes enriched prompt for advisory jobs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Persona findings-JSON contract

Ensure scout/admin/tutor end their runs with the findings JSON the bridge parses.

**Files:**
- Modify: `life_graph/kernel/personas.py` (append to scout/admin/tutor `system_prompt`, `:204-230`)
- Test: `tests/unit/test_ambient_personas.py`

**Interfaces:** none (data change).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_ambient_personas.py
from life_graph.kernel.personas import _BUILTIN_PERSONAS


def _p(name):
    return next(p for p in _BUILTIN_PERSONAS if p["name"] == name)


def test_advisory_personas_declare_findings_json_contract():
    for name in ("scout", "admin", "tutor"):
        sp = _p(name)["system_prompt"]
        assert "JSON array" in sp
        assert '"urgency"' in sp
        assert '"now"' in sp and '"brief"' in sp


def test_advisory_personas_stay_read_only():
    write_tools = {"terminal", "git", "delegate_to_persona", "browse_web_write"}
    for name in ("scout", "admin", "tutor"):
        assert not (set(_p(name)["allowed_tools"]) & write_tools)
```

- [ ] **Step 2: Run to verify it fails**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_ambient_personas.py -v`
Expected: FAIL on the contract assertion (prompts don't mention JSON yet). The read-only test should already PASS.

- [ ] **Step 3: Append the contract to each prompt**

For scout, admin, and tutor in `_BUILTIN_PERSONAS`, append this sentence to the existing `system_prompt` string (keep each persona's own wording; just add the trailing contract):

```
" End your reply with ONLY a JSON array of findings, each object "
"{\"title\": str, \"detail\": str, \"urgency\": \"now\"|\"brief\"}. Use \"now\" "
"only for genuinely time-sensitive items; use \"brief\" otherwise. If you have "
"nothing new to report, return []."
```

- [ ] **Step 4: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/unit/test_ambient_personas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit + note deploy re-sync**

```bash
git add life_graph/kernel/personas.py tests/unit/test_ambient_personas.py
git commit -m "feat(ambient): advisory personas emit findings JSON contract

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

> **Deploy note (out of band, like the jarvis prompt sync):** seeding skips existing personas, so the live DB rows for scout/admin/tutor keep their old prompts. At deploy, re-sync the three `system_prompt`s into `agent_personas` for tenants `personal` + `default` (same method used for the jarvis prompt). Record this in the deploy checklist.

---

### Task 9: Advisory-safety regression test

Pin the guarantee that a scheduled advisory run cannot call a write tool.

**Files:**
- Test: `tests/integration/test_ambient_advisory_safety.py`

- [ ] **Step 1: Write the test**

```python
# tests/integration/test_ambient_advisory_safety.py
"""A scheduled advisory persona must never receive a write tool."""
from life_graph.kernel.personas import _BUILTIN_PERSONAS
from life_graph.kernel.ambient import AMBIENT_ADVISORY


def test_advisory_allowed_tools_are_read_only():
    read_only = {"web_search", "browse_web", "memory_search", "get_current_datetime"}
    for name in AMBIENT_ADVISORY:
        persona = next(p for p in _BUILTIN_PERSONAS if p["name"] == name)
        assert set(persona["allowed_tools"]) <= read_only, (
            f"{name} has non-read-only tools: {persona['allowed_tools']}"
        )


def test_process_manager_filters_tools_by_allowed_set():
    """Guard: the headless path must filter tools by persona allowed_tools."""
    import inspect
    from life_graph.kernel import process_manager

    src = inspect.getsource(process_manager._run_agent)
    assert "allowed_tools" in src and "get_tools()" in src
    assert "tools=tools" in src  # tools are passed to orchestrator.run
```

- [ ] **Step 2: Run to verify it passes**

Run: `/c/Python314/python.exe -m pytest tests/integration/test_ambient_advisory_safety.py -v`
Expected: PASS (this is a guard test, green from the start; it fails only if someone later widens the tools or drops the filter).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_ambient_advisory_safety.py
git commit -m "test(ambient): pin advisory read-only tool guarantee

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: Dashboard schedules API client

Add a `kernel.schedules` group to the dashboard API client.

**Files:**
- Modify: `dashboard/lib/api.ts` (extend the `kernel` object, ~`:132-182`)

**Interfaces:**
- Produces: `kernel.schedules.list()`, `.create(body)`, `.update(id, body)`, `.remove(id)`. Note the list endpoint returns `data = {schedules, total}` (a dict), so read `.data.schedules`, not `listRequest`.

- [ ] **Step 1: Add the client group**

Inside the `kernel: { ... }` object in `dashboard/lib/api.ts`, add:

```typescript
    schedules: {
      list: () => GET<any>("/kernel/schedules"),               // read .data.schedules
      create: (body: {
        name: string; cron_expression: string; agent_name: string;
        description?: string; input?: Record<string, unknown>;
      }) => POST<any>("/kernel/schedules", body),
      update: (id: string, body: Record<string, unknown>) =>
        request<any>("PATCH", `/kernel/schedules/${id}`, body),
      remove: (id: string) => request<any>("DELETE", `/kernel/schedules/${id}`),
    },
```

- [ ] **Step 2: Type-check**

Run (in `dashboard/`): `npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/lib/api.ts
git commit -m "feat(ambient): dashboard kernel.schedules API client

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: Ambient roles dashboard UI + end-to-end integration

The mobile settings surface, plus an integration test proving the whole pipeline.

**Files:**
- Create: `dashboard/components/ambient-roles.tsx`
- Create: `dashboard/app/(mobile)/m/schedules/page.tsx`
- Test: `tests/integration/test_ambient_end_to_end.py`

**Interfaces:**
- Consumes: `kernel.schedules.*` (Task 10); notifications feed `kernel.notifications({limit})` filtered by `source_type ∈ {scout,admin,tutor}`.

- [ ] **Step 1: Write the end-to-end integration test (backend)**

```python
# tests/integration/test_ambient_end_to_end.py
"""Seed → ticker → advisory task completes → findings become notifications."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_findings_bridge_end_to_end_creates_and_pushes(monkeypatch):
    from life_graph.services.findings_bridge import FindingsBridge

    engine = AsyncMock(); engine.create = AsyncMock(return_value={"id": "n"})
    push = AsyncMock(); push.send_to_tenant = AsyncMock(return_value=1)
    bridge = FindingsBridge(notification_engine=engine, push_service=push)

    result_text = (
        "Scouted your topics.\n"
        '[{"title":"pgvector 0.9 HNSW","detail":"faster recall","urgency":"brief"},'
        '{"title":"Cert expires in 3 days","detail":"renew now","urgency":"now"}]'
    )
    created = await bridge.process_result("personal", "scout", "44444444-4444-4444-4444-444444444444", result_text)
    assert created == 2
    # urgent pushed, brief held
    assert push.send_to_tenant.await_count == 1
    briefs = [c for c in engine.create.await_args_list if c.kwargs["deliver_at_brief"]]
    assert len(briefs) == 1
```

- [ ] **Step 2: Run to verify pass**

Run: `/c/Python314/python.exe -m pytest tests/integration/test_ambient_end_to_end.py -v`
Expected: PASS.

- [ ] **Step 3: Build the UI component**

Create `dashboard/components/ambient-roles.tsx`: a client component that on mount calls `api.kernel.schedules.list()` and reads `res.data.schedules`, filters to the three ambient jobs by `agent_name ∈ {scout,admin,tutor}`, and renders per role:
- an enable/disable toggle → `api.kernel.schedules.update(id, { is_active })`;
- for `scout`, a topics editor (chips add/remove) → `api.kernel.schedules.update(id, { input: { topics } })`;
- a cadence label showing the cron + its local-time equivalent (schedules are UTC; convert `cron_expression` hour to the browser's local time for display only).
Below the roles, a "Recent findings" list from `api.kernel.notifications({ limit: "20" })` filtered to `source_type ∈ {scout,admin,tutor}`.
Follow the existing mobile component patterns in `dashboard/components/` (e.g. `persona-chat.tsx`, `mobile/parts.tsx`) for styling and the `api` import.

- [ ] **Step 4: Add the mobile route**

Create `dashboard/app/(mobile)/m/schedules/page.tsx` mounting `<AmbientRoles/>` inside the mobile layout, matching the structure of the sibling pages (`m/approvals/page.tsx`, `m/tasks/page.tsx`). Add a nav entry to it if the mobile shell (`m/layout.tsx`) has a nav.

- [ ] **Step 5: Type-check + build**

Run (in `dashboard/`): `npx tsc --noEmit && npm run build`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add dashboard/components/ambient-roles.tsx "dashboard/app/(mobile)/m/schedules/page.tsx" tests/integration/test_ambient_end_to_end.py
git commit -m "feat(ambient): mobile ambient-roles UI + end-to-end test

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (after all tasks)

- [ ] Backend unit + integration: `/c/Python314/python.exe -m pytest tests/unit/test_findings_bridge.py tests/unit/test_scheduler_tick.py tests/unit/test_ambient_seed.py tests/unit/test_ambient_context.py tests/unit/test_ambient_personas.py tests/integration/test_ambient_advisory_safety.py tests/integration/test_ambient_end_to_end.py -v`
- [ ] Full unit suite (regression): `/c/Python314/python.exe -m pytest tests/unit/ -q`
- [ ] Lint: `ruff check life_graph/ && ruff format --check life_graph/`
- [ ] Dashboard: `cd dashboard && npx tsc --noEmit && npm run build`
- [ ] Worker import sanity: `/c/Python314/python.exe -c "import life_graph.workers.settings"`

## Deploy checklist (out of band; batch-deploy mode — deploy only when told)

1. Rebuild `app` **and** `worker` images (the ticker + bridge live in the worker; the seeding + web-bridge live in the app). Reconnect `web` network on `app` after `--force-recreate`.
2. Re-sync scout/admin/tutor `system_prompt`s into `agent_personas` for tenants `personal` + `default` (seeding skips existing rows).
3. Seed the ambient jobs for tenant `personal` (startup seeds `default` only) — call `seed_ambient_jobs` for `personal`, or insert via the scheduler API.
4. Fill Scout's watch-list (`scout-daily.input.topics`) via the new UI or the scheduler API.
5. Verify one manual run: temporarily set an ambient job's cron to the next minute (or fire via the scheduler), confirm a `Notification` appears in the feed and an urgent one pushes.
6. Rebuild + swap the dashboard image (build-args as in the gcp-deployment notes) for the new `/m/schedules` page.
