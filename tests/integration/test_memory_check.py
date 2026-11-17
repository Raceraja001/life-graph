"""The Memory check: Jarvis asks the owner to keep or drop what it noted (2026-10-28).

Five days after the 2026-10-23 fresh start only day summaries were active and
25 facts about the owner waited in a review queue nobody opened, set to expire
unseen. Now a few a day are asked about in the owner's Memory check chat, each
with Keep / Drop, and expiry counts from when it was asked.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"memchk_{uuid.uuid4().hex[:8]}"
API = "/api/v1"


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as c:
        yield c


async def _memory(content: str, *, status="pending", age_hours: float, props=None):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=TENANT,
            content_hash=hashlib.sha256(f"{TENANT}{content}".encode()).hexdigest(),
            status=status,
            trust_tier="self",
            source_type="capture",
            properties=props or {},
        )
        m.created_at = datetime.now(UTC) - timedelta(hours=age_hours)
        s.add(m)
        await s.commit()
        return str(m.id)


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_few_a_day_are_asked_about_in_one_chat_and_keep_drop_work(client, monkeypatch):
    from life_graph.services import memory_check
    from life_graph.storage.database import async_session

    monkeypatch.setattr(memory_check, "PER_DAY", 2)
    now = datetime(2026, 10, 28, 3, 50, tzinfo=UTC)
    oldest = await _memory("The owner uses a Realme X2 Pro phone.", age_hours=90)
    second = await _memory("The owner wants to build mockups.", age_hours=60)
    newest = await _memory("The owner is exploring OpenHands.", age_hours=2)
    await _memory("The owner prefers local HTML files.", status="active", age_hours=80)

    async with async_session() as s:
        assert await memory_check.run_tenant(s, TENANT, now) == 2
    # The next day: the one not asked yet, in the same chat; nothing is asked twice.
    async with async_session() as s:
        assert await memory_check.run_tenant(s, TENANT, now + timedelta(days=1)) == 1
    async with async_session() as s:
        assert await memory_check.run_tenant(s, TENANT, now + timedelta(days=2)) == 0
        assert await memory_check.waiting(s, TENANT) == 3

    r = await client.get(f"{API}/jarvis/conversations")
    chats = [c for c in r.json()["data"] if c["title"] == memory_check.TITLE]
    assert len(chats) == 1
    r = await client.get(f"{API}/jarvis/conversations/{chats[0]['id']}/messages")
    msgs = r.json()["data"]
    assert [m["role"] for m in msgs] == ["assistant", "assistant"]  # no question invented
    first = msgs[0]
    assert first["content"].startswith("I noted 2 things about you")
    assert first["memory_check"] == [
        {
            "id": oldest,
            "content": "The owner uses a Realme X2 Pro phone.",
            "status": "pending",
            "evidence": "said",
        },
        {
            "id": second,
            "content": "The owner wants to build mockups.",
            "status": "pending",
            "evidence": "said",
        },
    ]
    assert [m["id"] for m in msgs[1]["memory_check"]] == [newest]

    # Keep and Drop are the existing approve / reject; the message shows the result.
    assert (await client.post(f"{API}/memories/{oldest}/approve")).status_code == 200
    assert (await client.post(f"{API}/memories/{second}/reject")).status_code == 200
    r = await client.get(f"{API}/jarvis/conversations/{chats[0]['id']}/messages")
    statuses = {m["id"]: m["status"] for m in r.json()["data"][0]["memory_check"]}
    assert statuses == {oldest: "active", second: "rejected"}
    async with async_session() as s:
        assert await memory_check.waiting(s, TENANT) == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_nothing_pending_means_no_message_and_no_chat(client):
    from life_graph.services import memory_check
    from life_graph.storage.database import async_session

    tenant = f"memchk_{uuid.uuid4().hex[:8]}"
    async with async_session() as s:
        assert await memory_check.run_tenant(s, tenant, datetime.now(UTC)) == 0
    r = await client.get(f"{API}/jarvis/conversations", headers={"X-Tenant-ID": tenant})
    assert all(c["title"] != memory_check.TITLE for c in r.json()["data"])
