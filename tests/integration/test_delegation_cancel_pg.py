"""DelegationEngine against the real database: defaults and the cancel cascade.

* create_task defaulted priority to "medium", outside low|normal|high|critical
  (AgentTaskPriority, #307), and wrote a first history entry of "pending"
  while the row itself started "queued".
* cancel_task cascaded only to direct children in pending|running. Rows start
  "queued", so a child not yet picked up -- the usual case -- survived its
  parent's cancel, and so did every grandchild.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import assert_ok, skip_on_db_error

TENANT = f"deleg_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": TENANT, "X-User-ID": "tester"},
    ) as c:
        yield c


def _engine():
    from life_graph.services.delegation import DelegationEngine
    from life_graph.storage.database import async_session

    return DelegationEngine(async_session)


async def _task(task_id):
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(AgentTask, task_id)


@pytest.mark.asyncio
@skip_on_db_error
async def test_create_task_defaults_are_real_values():
    task = await _engine().create_task(TENANT, {"agent_name": "worker", "task_name": "t"})

    assert task.priority == "normal"
    assert task.status == "queued"
    assert task.status_history[0]["status"] == task.status


@pytest.mark.asyncio
@skip_on_db_error
async def test_cancel_reaches_queued_children_and_grandchildren(client):
    engine = _engine()
    parent = await engine.create_task(TENANT, {"agent_name": "lead", "task_name": "parent"})
    queued_child = await engine.create_child_task(
        TENANT, parent.id, {"agent_name": "w", "task_name": "queued child"}
    )
    done_child = await engine.create_child_task(
        TENANT, parent.id, {"agent_name": "w", "task_name": "done child"}
    )
    await engine.update_task(TENANT, done_child.id, {"status": "completed"})
    grandchild = await engine.create_child_task(
        TENANT, done_child.id, {"agent_name": "w", "task_name": "grandchild"}
    )
    running_grandchild = await engine.create_child_task(
        TENANT, queued_child.id, {"agent_name": "w", "task_name": "running grandchild"}
    )
    await engine.update_task(TENANT, running_grandchild.id, {"status": "running"})

    r = await client.post(f"/api/v1/agent-tasks/{parent.id}/cancel")
    assert assert_ok(r, 200)["data"]["status"] == "cancelled"

    for open_id in (queued_child.id, grandchild.id, running_grandchild.id):
        t = await _task(open_id)
        assert t.status == "cancelled", (t.task_name, t.status)
        assert t.cancel_reason == f"Parent {parent.id} cancelled"
        assert t.status_history[-1]["status"] == "cancelled"
    # A finished task keeps its outcome.
    assert (await _task(done_child.id)).status == "completed"


@pytest.mark.asyncio
@skip_on_db_error
async def test_cancel_leaves_other_tenants_children_alone():
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    engine = _engine()
    parent = await engine.create_task(TENANT, {"agent_name": "lead", "task_name": "p"})
    async with async_session() as s:
        foreign = AgentTask(
            tenant_id="someone-else",
            agent_name="w",
            task_name="foreign child",
            parent_task_id=parent.id,
            status="queued",
        )
        s.add(foreign)
        await s.commit()

    await engine.cancel_task(parent.id, TENANT)

    assert (await _task(foreign.id)).status == "queued"


# ── live capabilities (autonomy/kill_switch.revoke_live_capabilities, #306) ──


def _issue(store, task_id) -> str:
    return store.issue(
        tenant_id=TENANT,
        action_types=["transfer_money"],
        target_origins=["owner"],
        task_id=str(task_id),
    ).capability_id


@pytest.mark.asyncio
@skip_on_db_error
async def test_cancel_revokes_the_live_capabilities_of_every_task_it_stopped(client, monkeypatch):
    from life_graph.autonomy.approvals.capability import CapabilityStore

    store = CapabilityStore()
    monkeypatch.setattr("life_graph.autonomy.approvals.capability.capability_store", store)
    engine = _engine()
    parent = await engine.create_task(TENANT, {"agent_name": "lead", "task_name": "p"})
    child = await engine.create_child_task(TENANT, parent.id, {"agent_name": "w", "task_name": "c"})
    done = await engine.create_child_task(TENANT, parent.id, {"agent_name": "w", "task_name": "d"})
    await engine.update_task(TENANT, done.id, {"status": "completed"})
    on_parent, on_child, on_done = (
        _issue(store, parent.id),
        _issue(store, child.id),
        _issue(store, done.id),
    )
    unrelated = _issue(store, uuid.uuid4())

    r = await client.post(f"/api/v1/agent-tasks/{parent.id}/cancel")
    assert_ok(r, 200)

    assert store.get(on_parent).revoked is True
    assert store.get(on_child).revoked is True
    # Not stopped by this cancel (it had already finished), not someone else's.
    assert store.get(on_done).revoked is False
    assert store.get(unrelated).revoked is False


@pytest.mark.asyncio
@skip_on_db_error
async def test_cancel_with_the_store_down_stands_and_answers_503(client, monkeypatch):
    from life_graph.autonomy.approvals.durable_store import StoreUnavailableError

    class _Down:
        def revoke_all(self, **_kw):
            raise StoreUnavailableError("the authorization store is unavailable")

    monkeypatch.setattr("life_graph.autonomy.approvals.capability.capability_store", _Down())
    engine = _engine()
    parent = await engine.create_task(TENANT, {"agent_name": "lead", "task_name": "p"})
    child = await engine.create_child_task(TENANT, parent.id, {"agent_name": "w", "task_name": "c"})

    r = await client.post(f"/api/v1/agent-tasks/{parent.id}/cancel")

    assert r.status_code == 503, r.text
    detail = r.json().get("detail") or r.text
    assert "cancelled" in str(detail) and "could not be revoked" in str(detail)
    # The stop was committed before the revocation was attempted.
    assert (await _task(parent.id)).status == "cancelled"
    assert (await _task(child.id)).status == "cancelled"
