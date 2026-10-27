"""What shaped a reply (docs/specs/web-chat-wave1.md F3) against the database: the
trace endpoint, "that's wrong" on a memory the reply used, and temporary chat
being the lead's only."""

from __future__ import annotations

import hashlib
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"trace_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as c:
        yield c


async def _memory(content: str, status: str = "active") -> uuid.UUID:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(content=content, tenant_id=TENANT, status=status, trust_tier="self", source_type="test",
                   content_hash=hashlib.sha256(f"{TENANT}{content}".encode()).hexdigest())
        s.add(m)
        await s.commit()
        return m.id


async def _turn(trace: dict | None) -> uuid.UUID:
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        t = AgentTask(tenant_id=TENANT, agent_name="jarvis", task_name="chat:jarvis", status="completed",
                      input={"message": "what bills?"},
                      result={"response": "Two.", **({"trace": trace} if trace else {})})
        s.add(t)
        await s.commit()
        return t.id


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_trace_and_a_wrong_memory(client):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    used = await _memory("Electricity bill is due on the 5th.")
    other = await _memory("The car is blue.")
    trace = {
        "route": {"kind": "personal", "model": "m", "reason": "mentions 'bills'"},
        "local": True,
        "models": ["m"],
        "memories": [{"id": str(used), "snippet": "Electricity bill is due on the 5th."}],
        "tools": [{"name": "bills_due", "ok": True, "ms": 80}],
    }
    turn = await _turn(trace)

    data = (await client.get(f"/api/v1/jarvis/turns/{turn}/trace")).json()["data"]
    assert data["trace"]["local"] is True and data["summary"] == "Local · 1 memory · 1 tool"
    old = await _turn(None)  # from before traces were kept
    assert (await client.get(f"/api/v1/jarvis/turns/{old}/trace")).json()["data"]["trace"] is None
    other_tenant = await client.get(f"/api/v1/jarvis/turns/{turn}/trace", headers={"X-Tenant-ID": "someone_else"})
    assert other_tenant.status_code == 404

    # Only a memory the reply used can be called wrong from it.
    r = await client.post(f"/api/v1/jarvis/turns/{turn}/memories/{other}/wrong", json={})
    assert r.status_code == 404
    r = await client.post(f"/api/v1/jarvis/turns/{turn}/memories/{used}/wrong", json={"note": "It moved to the 8th"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "pending"
    async with async_session() as s:
        row = await s.get(Memory, used)
        untouched = await s.get(Memory, other)
    assert row.status == "pending" and row.properties["disputed"]["note"] == "It moved to the 8th"
    assert untouched.status == "active"
    # Already back in review: a second time is a conflict, not a change.
    again = await client.post(f"/api/v1/jarvis/turns/{turn}/memories/{used}/wrong", json={})
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_a_temporary_chat_is_with_jarvis_only():
    from life_graph.api.dependencies import get_persona_service
    from life_graph.main import app

    class _Personas:
        async def get_by_name(self, tenant_id, name):
            return {"name": name, "is_active": True}

    app.dependency_overrides[get_persona_service] = lambda: _Personas()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                               headers={"X-Tenant-ID": TENANT}) as c:
            r = await c.post("/api/v1/kernel/chat/stream",
                             json={"target_agent": "scout", "message": "hi", "temporary": True})
    finally:
        app.dependency_overrides.pop(get_persona_service, None)
    assert r.status_code == 400 and "Jarvis only" in r.text
