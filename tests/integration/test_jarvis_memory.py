"""Jarvis learns from the owner's phone messages and can forget on request.

- What the owner types or says in the phone app goes to the capture spine as
  the ``jarvis_app`` surface, trusted as the owner's own words.
- ``memory_forget`` archives (never deletes) one active memory of the
  current tenant, and nothing else.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager

import pytest

from life_graph.core.tenant import tenant_scope
from tests.integration.conftest import skip_on_db_error

TENANT = f"jm_{uuid.uuid4().hex[:8]}"


async def _seed(content, *, tenant=TENANT, status="active"):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{tenant}{content}".encode()).hexdigest(),
            status=status,
            trust_tier="self",
            source_type="test",
        )
        s.add(m)
        await s.commit()
        return m.id


async def _status(mid):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = await s.get(Memory, mid)
        return row.status, row.properties


@pytest.mark.asyncio
@skip_on_db_error
async def test_memory_forget_archives_one_active_memory_of_this_tenant():
    from life_graph.tools.memory_search import memory_forget

    mine = await _seed("My dentist is Dr. Rao.")
    pending = await _seed("Unreviewed thing.", status="pending")
    theirs = await _seed("Someone else's fact.", tenant="other_" + TENANT)

    with tenant_scope(TENANT), _in_run(await _run("That's wrong, forget my dentist")):
        out = json.loads(await memory_forget(str(mine), "user said it is wrong"))
        assert out == {"forgotten": True, "id": str(mine), "content": "My dentist is Dr. Rao."}
        status, props = await _status(mine)
        assert status == "archived" and props["forgotten"]["reason"] == "user said it is wrong"

        assert "error" in json.loads(await memory_forget(str(mine)))  # already forgotten
        assert "error" in json.loads(await memory_forget(str(pending)))  # not active
        assert "error" in json.loads(await memory_forget(str(theirs)))  # another tenant
        assert "error" in json.loads(await memory_forget("not-an-id"))
    assert (await _status(pending))[0] == "pending"
    assert (await _status(theirs))[0] == "active"


@pytest.mark.asyncio
@skip_on_db_error
async def test_memory_forget_needs_the_owner_to_ask():
    """Review 2026-10-24 (H3): a forget the owner's own message did not ask for
    is refused, and the memory stays."""
    from life_graph.tools.memory_search import memory_forget

    mine = await _seed(f"My locker is 82 ({uuid.uuid4().hex[:6]}).")
    with tenant_scope(TENANT), _in_run(await _run("what's my locker code?")):
        out = json.loads(await memory_forget(str(mine), "user said it is wrong"))
    assert "did not ask to forget" in out["error"]
    assert (await _status(mine))[0] == "active"
    with tenant_scope(TENANT):  # no run at all: no owner message, no forget
        assert "error" in json.loads(await memory_forget(str(mine)))
    assert (await _status(mine))[0] == "active"


async def _run(message: str) -> uuid.UUID:
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        task = AgentTask(
            tenant_id=TENANT, agent_name="jarvis", input={"message": message}, status="running"
        )
        s.add(task)
        await s.commit()
        return task.id


@contextmanager
def _in_run(task_id: uuid.UUID):
    from life_graph.core.task_context import TaskContext, _task_context_var

    token = _task_context_var.set(TaskContext(task_id=task_id, tenant_id=TENANT))
    try:
        yield
    finally:
        _task_context_var.reset(token)


@pytest.mark.asyncio
@skip_on_db_error
async def test_phone_messages_are_captured_as_the_owners_words(monkeypatch):
    from sqlalchemy import select

    from life_graph.api import jarvis
    from life_graph.core import events
    from life_graph.models.db import CaptureEvent
    from life_graph.storage.database import async_session

    emitted = []

    async def no_processing(event_type, payload, **kw):
        emitted.append(event_type)

    monkeypatch.setattr(events.event_bus, "emit", no_processing)
    conv = uuid.uuid4()
    text = f"Remember that my passport expires in May 2029 {uuid.uuid4().hex[:6]}"
    await jarvis._capture(TENANT, text, "voice", conv)

    async with async_session() as s:
        row = (
            (
                await s.execute(
                    select(CaptureEvent).where(
                        CaptureEvent.tenant_id == TENANT, CaptureEvent.surface == "jarvis_app"
                    )
                )
            )
            .scalars()
            .one()
        )
    assert row.content == text and row.trust_tier == "self"
    assert row.properties["input"] == "voice" and row.properties["conversation_id"] == str(conv)
    assert emitted  # handed on for extraction


@pytest.mark.asyncio
async def test_a_failed_capture_never_fails_the_conversation(monkeypatch):
    from life_graph.api import jarvis

    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("db down")

    monkeypatch.setattr("life_graph.services.capture.CaptureService", _Boom)
    await jarvis._capture(TENANT, "hello", "text", None)  # no exception
