"""The live session log of a dev task (work order Stage 4), against Postgres.

- events are stored in order with a per-task seq, redacted and capped;
- "everything after N" is exact, so a reconnecting viewer has no gaps/repeats;
- the long-poll returns as soon as something new is written, at once when the
  task is over, and never shows another tenant's task;
- the API (long-poll and SSE) and a real runner pass produce the stream.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error

TENANT = f"dev_events_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": "events-test"}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as c:
        yield c


@pytest_asyncio.fixture
async def project(monkeypatch):
    from life_graph.api.dependencies import get_persona_service, get_project_registry
    from life_graph.config import settings

    monkeypatch.setattr(settings, "tool_fs_roots", str(Path.cwd()))
    await get_persona_service().seed_builtins(TENANT)
    return await get_project_registry().register(
        TENANT, {"name": f"proj-{uuid.uuid4().hex[:6]}", "path": str(Path.cwd())}
    )


@pytest.fixture(autouse=True)
def no_local_runner():
    from life_graph.services.dev import runner as runner_mod

    previous = runner_mod.local_runner()
    runner_mod.set_local_runner(None)
    yield
    runner_mod.set_local_runner(previous)


async def _task(project, **kw):
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    return await dev_tasks.create_dev_task(
        async_session, TENANT, instruction=f"Fix {uuid.uuid4().hex}", project=project,
        persona_name="code-fixer-local", start=False, **kw,
    )  # fmt: skip


async def _set_status(task_id, status):
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = await s.get(AgentTask, uuid.UUID(task_id))
        row.status = status
        await s.commit()


async def _events(task_id, after=0, tenant=TENANT):
    from life_graph.services.dev import task_events
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await task_events.read_events(s, tenant, task_id, after=after)


@pytest.mark.asyncio
@skip_on_db_error
async def test_events_are_ordered_redacted_and_resumable(project):
    from life_graph.services.dev import task_events

    t = await _task(project)
    for i in range(5):
        task_events.emit(TENANT, t["id"], "tool_result", f"line {i}", source="agent")
    task_events.emit(
        TENANT, t["id"], "tool_result", "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456"
    )
    await task_events.flush()

    events = await _events(t["id"])
    assert [e["seq"] for e in events] == [1, 2, 3, 4, 5, 6]
    assert [e["content"] for e in events[:5]] == [f"line {i}" for i in range(5)]
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in events[5]["content"]
    assert "REDACTED" in events[5]["content"]
    # A viewer that saw up to 3 gets exactly 4.. on reconnect.
    assert [e["seq"] for e in await _events(t["id"], after=3)] == [4, 5, 6]


@pytest.mark.asyncio
@skip_on_db_error
async def test_long_content_is_capped_with_its_real_length(project):
    from life_graph.services.dev import task_events

    t = await _task(project)
    task_events.emit(TENANT, t["id"], "tool_result", "x" * 50_000)
    await task_events.flush()
    (ev,) = await _events(t["id"])
    assert len(ev["content"]) == task_events.MAX_CONTENT_CHARS
    assert ev["data"]["original_chars"] == 50_000


@pytest.mark.asyncio
@skip_on_db_error
async def test_long_poll_returns_as_soon_as_an_event_arrives(project):
    from life_graph.services.dev import task_events
    from life_graph.storage.database import async_session

    t = await _task(project)

    async def later():
        await asyncio.sleep(0.6)
        task_events.emit(TENANT, t["id"], "status", "running")

    asyncio.get_running_loop().create_task(later())
    t0 = time.monotonic()
    events, status = await task_events.wait_for_events(
        async_session, TENANT, t["id"], after=0, wait=10, poll=0.1
    )
    assert [e["content"] for e in events] == ["running"]
    assert time.monotonic() - t0 < 5
    assert status == "queued"


@pytest.mark.asyncio
@skip_on_db_error
async def test_long_poll_does_not_wait_on_a_finished_task(project):
    from life_graph.services.dev import task_events
    from life_graph.storage.database import async_session

    t = await _task(project)
    await _set_status(t["id"], "completed")
    t0 = time.monotonic()
    events, status = await task_events.wait_for_events(
        async_session, TENANT, t["id"], after=0, wait=10
    )
    assert events == [] and status == "completed"
    assert time.monotonic() - t0 < 2


@pytest.mark.asyncio
@skip_on_db_error
async def test_another_tenant_sees_nothing(project, client):
    from life_graph.services.dev import task_events
    from life_graph.storage.database import async_session

    t = await _task(project)
    task_events.emit(TENANT, t["id"], "status", "running")
    await task_events.flush()
    assert await _events(t["id"], tenant="someone-else") == []
    events, status = await task_events.wait_for_events(
        async_session, "someone-else", t["id"], after=0, wait=0
    )
    assert events == [] and status is None
    other = {"X-Tenant-ID": "someone-else", "X-User-ID": "x"}
    resp = await client.get(f"/api/v1/kernel/drivers/tasks/{t['id']}/events", headers=other)
    assert resp.status_code == 404


@pytest.mark.asyncio
@skip_on_db_error
async def test_events_for_a_task_with_no_row_are_dropped_quietly():
    from life_graph.services.dev import task_events

    task_events.emit(TENANT, str(uuid.uuid4()), "status", "nobody home")
    await task_events.flush()  # no exception, nothing stored


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_api_long_poll_and_cursor(project, client):
    from life_graph.services.dev import task_events

    t = await _task(project)
    task_events.emit(TENANT, t["id"], "stage", "prepared", source="dispatcher")
    task_events.emit(TENANT, t["id"], "tool_call", '{"command": "pytest"}', data={"tool": "Bash"})
    await task_events.flush()

    resp = await client.get(f"/api/v1/kernel/drivers/tasks/{t['id']}/events?after=0")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert [e["kind"] for e in body["events"]] == ["stage", "tool_call"]
    assert body["events"][1]["data"]["tool"] == "Bash"
    assert body["next_after"] == 2 and body["live"] is True

    await _set_status(t["id"], "completed")
    again = (
        await client.get(f"/api/v1/kernel/drivers/tasks/{t['id']}/events?after=2&wait=5")
    ).json()["data"]
    assert again["events"] == [] and again["live"] is False


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_sse_stream_resumes_from_last_event_id_and_ends(project, client):
    from life_graph.services.dev import task_events

    t = await _task(project)
    for kind in ("stage", "tool_call", "verify"):
        task_events.emit(TENANT, t["id"], kind, kind)
    await task_events.flush()
    await _set_status(t["id"], "completed")

    resp = await client.get(
        f"/api/v1/kernel/drivers/tasks/{t['id']}/events/stream",
        headers={"Last-Event-ID": "1"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    text = resp.text
    assert "id: 1\n" not in text  # already seen
    assert "id: 2\nevent: tool_call" in text and "id: 3\nevent: verify" in text
    assert text.rstrip().splitlines()[-2] == "event: end"


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_real_runner_pass_records_the_lifecycle(project, monkeypatch):
    from life_graph.drivers.base import DriverResult
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.services.dev import task_events
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.services.dev.runner import DevTaskRunner
    from life_graph.storage.database import async_session

    seen = {}

    async def fake_dispatch(self, **kw):
        # Keyed by task: the runner also runs whatever else is queued in the DB.
        seen[kw["task_id"]] = kw.get("timeout_seconds")
        task_events.emit(kw["tenant_id"], kw["task_id"], "tool_call", "ls", source="agent")
        return DriverResult(success=True, output="done")

    monkeypatch.setattr(TaskDispatcher, "dispatch_task", fake_dispatch)
    t = await dev_tasks.create_dev_task(
        async_session, TENANT, instruction=f"Run {uuid.uuid4().hex}", project=project,
        persona_name="code-fixer", timeout_seconds=600,
    )  # fmt: skip
    await DevTaskRunner(async_session, listen=False).run_until_idle()
    await task_events.flush()

    kinds = [(e["kind"], e["content"]) for e in await _events(t["id"])]
    assert ("status", "running") in kinds
    assert ("tool_call", "ls") in kinds
    assert kinds[-1] == ("status", "completed")
    assert seen[t["id"]] == 600


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_nul_byte_or_a_bad_event_never_drops_the_batch(project, monkeypatch):
    """Review 2026-11-18: Postgres rejects NUL; one rejected insert used to
    roll back every event in the batch."""
    from life_graph.services.dev import task_events

    t = await _task(project)
    task_events.emit(TENANT, t["id"], "tool_result", "binary\x00file", data={"x": "a\x00b"})
    task_events.emit(TENANT, t["id"], "text", "after the NUL")
    await task_events.flush()
    contents = [e["content"] for e in await _events(t["id"])]
    assert contents == ["binaryfile", "after the NUL"]
