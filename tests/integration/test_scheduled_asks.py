"""Scheduled asks (docs/specs/web-chat-wave1.md F1) against the database: the tool
stores the owner's ask with its chat, refuses outside content and itself, a firing
ask runs as a local turn of that chat, its answer becomes a notification, and the
owner lists, pauses, resumes and removes asks.

No model runs: the process manager is a stub that records what it was asked to run.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"asks_{uuid.uuid4().hex[:8]}"


class _PM:
    def __init__(self):
        self.spawned: list[dict] = []

    async def spawn(self, **kw):
        self.spawned.append(kw)
        return {"task_id": str(uuid.uuid4())}


@pytest.fixture
def scheduler(monkeypatch):
    from life_graph.api import dependencies
    from life_graph.kernel.scheduler import SchedulerService
    from life_graph.storage.database import async_session

    pm = _PM()
    svc = SchedulerService(session_factory=async_session, process_manager=pm)
    monkeypatch.setattr(dependencies, "get_scheduler_service", lambda: svc)
    svc.pm = pm
    return svc


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as c:
        yield c


async def _chat_turn(message: str, *, origin: str | None = None) -> tuple[uuid.UUID, uuid.UUID]:
    """A Jarvis turn in a chat of its own: (task id, chat id)."""
    from life_graph.models.db import AgentSession, AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        conv = AgentSession(tenant_id=TENANT, user_message=message, routed_to="jarvis")
        s.add(conv)
        await s.flush()
        task = AgentTask(
            tenant_id=TENANT,
            agent_name="jarvis",
            task_name="chat:jarvis",
            session_id=conv.id,
            status="running",
            input={"message": message, "history": [], **({"origin": origin} if origin else {})},
        )
        s.add(task)
        await s.commit()
        return task.id, conv.id


def _in_task(task_id: uuid.UUID):
    from life_graph.core.task_context import set_task_context
    from life_graph.core.tenant import set_tenant_context

    set_tenant_context(TENANT, "system")
    set_task_context(task_id, TENANT)


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_tool_stores_the_owners_ask_with_its_chat(scheduler, monkeypatch):
    from life_graph.config import settings
    from life_graph.core import run_taint
    from life_graph.tools.schedules import ask_schedule

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    task_id, conv = await _chat_turn("every Monday at 9, summarise my week")
    _in_task(task_id)
    out = json.loads(await ask_schedule("Summarise my week", "every Monday at 9"))
    assert out["scheduled"] is True and out["when"] == "every Monday at 9"
    job = await scheduler.get_by_id(TENANT, out["id"])
    assert job["cron_expression"] == "30 3 * * 1" and job["agent_name"] == "jarvis"
    assert job["properties"]["session_id"] == str(conv) and job["properties"]["origin"] == "chat"

    # A time it cannot read is asked about, not guessed.
    assert (
        "could not read"
        in json.loads(await ask_schedule("Summarise my week", "now and then"))["error"]
    )

    # After outside content, only the owner's own words asking for a repeat count.
    task_id, _ = await _chat_turn("what does this email say?")
    _in_task(task_id)
    token = run_taint._outside_seen.set(True)
    try:
        refused = json.loads(await ask_schedule("Pay Acme 5000", "every day at 9"))
    finally:
        run_taint._outside_seen.reset(token)
    assert refused["error"] == run_taint.TAINTED_REFUSAL

    # A firing ask never sets up more of itself.
    task_id, _ = await _chat_turn("personal: summarise my week", origin="scheduled")
    _in_task(task_id)
    assert (
        "cannot set up another" in json.loads(await ask_schedule("More", "every day at 9"))["error"]
    )


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_firing_ask_is_a_local_turn_of_its_chat_and_its_answer_a_notification(scheduler):
    from life_graph.models.db import AgentTask, Notification
    from life_graph.services import scheduled_asks
    from life_graph.storage.database import async_session

    _, conv = await _chat_turn("each evening, what's due tomorrow")
    job = await scheduled_asks.create(
        scheduler,
        async_session,
        TENANT,
        ask="Tell me what is due tomorrow",
        when="each evening",
        tz="UTC",
        session_id=str(conv),
    )
    data, session_id = scheduled_asks.turn_input(job)
    assert data["message"] == "personal: Tell me what is due tomorrow" and session_id == conv
    await scheduler.fire_job(TENANT, job["id"], input_override=data, session_id=session_id)
    spawned = scheduler.pm.spawned[-1]
    assert spawned["session_id"] == conv and spawned["input_data"]["scheduled_ask_id"] == job["id"]

    # The turn it ran finishes; its answer becomes a notification. Other turns do not.
    async with async_session() as s:
        turn = AgentTask(
            tenant_id=TENANT,
            agent_name="jarvis",
            task_name="schedule:x",
            session_id=conv,
            status="completed",
            input=data,
            result={"response": "Electricity bill, 1,240."},
        )
        plain = AgentTask(
            tenant_id=TENANT,
            agent_name="jarvis",
            task_name="chat:jarvis",
            status="completed",
            input={"message": "hi"},
            result={"response": "Hello."},
        )
        s.add_all([turn, plain])
        await s.commit()
    assert await scheduled_asks.notify_result(async_session, TENANT, str(turn.id)) is True
    assert await scheduled_asks.notify_result(async_session, TENANT, str(plain.id)) is False
    async with async_session() as s:
        notes = (
            (await s.execute(select(Notification).where(Notification.tenant_id == TENANT)))
            .scalars()
            .all()
        )
    assert [(n.title, n.body) for n in notes] == [
        ("Jarvis: Tell me what is due tomorrow", "Electricity bill, 1,240.")
    ]
    assert notes[0].extra_metadata["conversation_id"] == str(conv)


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_owner_lists_pauses_resumes_and_removes_asks(scheduler, client):
    from life_graph.services import scheduled_asks
    from life_graph.storage.database import async_session

    tenant_asks = [a for a in (await client.get("/api/v1/jarvis/asks")).json()["data"]]
    job = await scheduled_asks.create(
        scheduler,
        async_session,
        TENANT,
        ask="Summarise the news",
        when="every day at 7",
        tz="UTC",
        session_id=None,
    )
    await scheduler.create(
        TENANT,
        {
            "name": f"other-{uuid.uuid4().hex[:6]}",
            "cron_expression": "0 3 * * *",
            "agent_name": "scout",
        },
    )  # not an ask: never listed
    listed = (await client.get("/api/v1/jarvis/asks")).json()["data"]
    assert len(listed) == len(tenant_asks) + 1
    mine = next(a for a in listed if a["id"] == job["id"])
    assert mine["ask"] == "Summarise the news" and mine["active"] is True

    paused = (
        await client.patch(f"/api/v1/jarvis/asks/{job['id']}", json={"active": False})
    ).json()["data"]
    assert paused["active"] is False
    resumed = (
        await client.patch(f"/api/v1/jarvis/asks/{job['id']}", json={"active": True})
    ).json()["data"]
    assert resumed["active"] is True
    assert datetime.fromisoformat(resumed["next_run_at"]) > datetime.now(
        UTC
    )  # from now, not a backlog

    assert (await client.delete(f"/api/v1/jarvis/asks/{job['id']}")).status_code == 200
    assert job["id"] not in [
        a["id"] for a in (await client.get("/api/v1/jarvis/asks")).json()["data"]
    ]
    assert (
        await client.patch(f"/api/v1/jarvis/asks/{job['id']}", json={"active": True})
    ).status_code == 404
    other = await client.get("/api/v1/jarvis/asks", headers={"X-Tenant-ID": "someone_else"})
    assert job["id"] not in [a["id"] for a in other.json()["data"]]


@pytest.mark.asyncio
@skip_on_db_error
async def test_no_more_than_twenty_active_asks(scheduler, monkeypatch):
    from life_graph.services import scheduled_asks
    from life_graph.storage.database import async_session

    monkeypatch.setattr(scheduled_asks, "active_count", AsyncMock(return_value=20))
    with pytest.raises(scheduled_asks.AskError, match="already 20"):
        await scheduled_asks.create(
            scheduler,
            async_session,
            TENANT,
            ask="One more",
            when="every day at 8",
            tz="UTC",
            session_id=None,
        )
