"""Jarvis saves what the owner asks it to remember (tools/memory_search.py memory_save).

- Active at once only when the owner's own message for the run asks to
  remember something; a save prompted by anything else (an email, a web page)
  waits for review.
- The same fact twice is not stored twice.
- A correction replaces the old memory (superseded, never deleted), and only
  one of this tenant's.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"ms_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def no_embeddings(monkeypatch):
    """No embedding service in tests: the exact-match path is what is checked."""
    from life_graph.api import dependencies

    class _Manager:
        async def generate_embedding(self, text):
            return None

    monkeypatch.setattr(dependencies, "get_memory_manager", lambda: _Manager())


async def _run(message: str, tenant: str = TENANT) -> uuid.UUID:
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        task = AgentTask(
            tenant_id=tenant, agent_name="jarvis", input={"message": message}, status="running"
        )
        s.add(task)
        await s.commit()
        return task.id


@contextmanager
def _in_run(task_id: uuid.UUID, tenant: str = TENANT):
    from life_graph.core.task_context import TaskContext, _task_context_var

    token = _task_context_var.set(TaskContext(task_id=task_id, tenant_id=tenant))
    try:
        yield
    finally:
        _task_context_var.reset(token)


async def _row(mid):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(str(mid)))


async def _seed(content, *, tenant=TENANT, status="active"):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(content.strip().lower().encode()).hexdigest(),
            status=status,
            trust_tier="self",
            source_type="test",
        )
        s.add(m)
        await s.commit()
        return m.id


@pytest.mark.asyncio
@skip_on_db_error
async def test_what_the_owner_asks_to_remember_is_saved_once_and_active():
    from life_graph.tools.memory_search import memory_save

    fact = f"My car insurance renews on 5 March 2027 ({uuid.uuid4().hex[:6]})."
    with _in_run(await _run("Remember that my car insurance renews on 5 March")):
        out = json.loads(await memory_save(fact))
        again = json.loads(await memory_save(fact))
    assert out["saved"] is True and "status" not in out
    row = await _row(out["id"])
    assert (row.status, row.trust_tier, row.content) == ("active", "self", fact)
    assert "explicit_save" in row.tags
    assert again == {"saved": False, "already_remembered": fact}


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_save_the_owner_did_not_ask_for_waits_for_review():
    from life_graph.tools.memory_search import memory_save

    with _in_run(await _run("Summarise my latest email from the bank")):
        out = json.loads(
            await memory_save(f"The owner owes the bank 5000 ({uuid.uuid4().hex[:6]}).")
        )
    assert out["saved"] is True and out["status"] == "waiting for the user's review"
    assert (await _row(out["id"])).status == "pending"


@pytest.mark.asyncio
@skip_on_db_error
async def test_asking_settles_the_same_fact_already_waiting_for_review():
    from life_graph.tools.memory_search import memory_save

    fact = f"I am allergic to peanuts ({uuid.uuid4().hex[:6]})."
    waiting = await _seed(fact, status="pending")
    run = await _run("please save this: I'm allergic to peanuts")
    with _in_run(run):
        out = json.loads(await memory_save(fact))
    row = await _row(waiting)
    assert out["id"] == str(waiting) and row.status == "active"
    # Marked as Jarvis's save, so Undo and the voice reply find it (review H3).
    assert row.properties["saved_by"] == "jarvis" and row.properties["task_id"] == str(run)


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_question_about_memory_does_not_activate_a_save():
    from life_graph.tools.memory_search import memory_save

    with _in_run(await _run("do you remember my locker code?")):
        out = json.loads(await memory_save(f"My locker code is 82 ({uuid.uuid4().hex[:6]})."))
    assert out["status"] == "waiting for the user's review"
    assert (await _row(out["id"])).status == "pending"


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_correction_replaces_only_this_tenants_memory():
    from life_graph.tools.memory_search import memory_save

    tag = uuid.uuid4().hex[:6]
    old = await _seed(f"My dentist is Dr. Rao ({tag}).")
    theirs = await _seed(f"Their dentist is Dr. Rao ({tag}).", tenant="other_" + TENANT)
    with _in_run(await _run("No, remember my dentist is Dr. Mehta now")):
        out = json.loads(
            await memory_save(f"My dentist is Dr. Mehta ({tag}).", replaces_id=str(old))
        )
        other = json.loads(await memory_save(f"Dentist: Mehta ({tag}).", replaces_id=str(theirs)))
    assert out["replaced"] == f"My dentist is Dr. Rao ({tag})."
    was = await _row(old)
    assert was.status == "superseded" and str(was.superseded_by) == out["id"]
    assert str((await _row(out["id"])).supersedes) == str(old)
    assert "replaced" not in other and (await _row(theirs)).status == "active"


@pytest.mark.asyncio
@skip_on_db_error
async def test_bad_input_is_refused_without_saving():
    from life_graph.tools.memory_search import memory_save

    assert "error" in json.loads(await memory_save("hi"))  # no tenant context
    with _in_run(await _run("remember this")):
        assert "error" in json.loads(await memory_save("  "))
        assert "error" in json.loads(await memory_save("x" * 1001))
        assert "error" in json.loads(await memory_save("A fact.", replaces_id="not-an-id"))


async def _approval(old, new):
    from sqlalchemy import select

    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (
            await s.execute(select(Approval).where(Approval.source_ref == f"{old}|{new}"))
        ).scalar_one_or_none()


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_plain_correction_replaces_at_once_and_can_be_undone():
    """ "No, it's X now" with the fact named: before 2026-10-30 only "remember …"
    replaced anything, so the old fact stayed active beside the new one."""
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    tag = uuid.uuid4().hex[:6]
    old = await _seed(f"My phone is a Realme X2 Pro ({tag}).")
    with _in_run(await _run("No, it's a Pixel 8 now")):
        out = json.loads(
            await memory_save_(f"My phone is a Pixel 8 ({tag}).", replaces_id=str(old))
        )
    assert out["replaced"] == f"My phone is a Realme X2 Pro ({tag})."
    assert (await _row(out["id"])).status == "active"
    assert (await _row(old)).status == "superseded"
    appr = await _approval(old, out["id"])
    assert appr.kind == "contradiction" and appr.payload["applied"] is True
    assert appr.detail == f"Replaces: My phone is a Realme X2 Pro ({tag})."

    # Rejecting the review item brings the old fact back.
    async with async_session() as s:
        await ApprovalService(s).resolve(TENANT, str(appr.id), "reject")
        await s.commit()
    assert (await _row(old)).status == "active"


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_unclear_correction_waits_and_keep_replaces():
    from httpx import ASGITransport, AsyncClient

    from life_graph.main import app
    from life_graph.services import memory_check
    from life_graph.storage.database import async_session

    tag = uuid.uuid4().hex[:6]
    old = await _seed(f"My car is a Honda City ({tag}).")
    with _in_run(await _run("I got a Kia Seltos")):
        out = json.loads(
            await memory_save_(f"My car is a Kia Seltos ({tag}).", replaces_id=str(old))
        )
    assert out["status"] == "waiting for the user's review"
    assert out["will_replace"] == f"My car is a Honda City ({tag})."
    assert (await _row(old)).status == "active"  # not yet
    assert (await _approval(old, out["id"])).payload["applied"] is False

    async with async_session() as s:
        item = (await memory_check.states(s, TENANT, [out["id"]]))[out["id"]]
    assert item["replaces"] == f"My car is a Honda City ({tag})."

    # Keep (the Memory check's approve) applies the replacement.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as c:
        assert (await c.post(f"/api/v1/memories/{out['id']}/approve")).status_code == 200
    assert (await _row(out["id"])).status == "active"
    was = await _row(old)
    assert was.status == "superseded" and str(was.superseded_by) == out["id"]


async def memory_save_(content, **kw):
    from life_graph.tools.memory_search import memory_save

    return await memory_save(content, **kw)
