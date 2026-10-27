"""Nudges (docs/specs/web-chat-wave1.md F2) against the database: a promise in the
owner's own words is kept once, shared text never makes one, the job sends a few
a day outside quiet hours, and Done / Tomorrow / Drop work from the notification
and from the web."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"nudge_{uuid.uuid4().hex[:8]}"
UTCZ = ZoneInfo("UTC")


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as c:
        yield c


def _capture(text: str, *, surface="jarvis_app", tier="self", kind="text"):
    return SimpleNamespace(
        id=uuid.uuid4(), tenant_id=TENANT, surface=surface, trust_tier=tier, content=text,
        properties={"input": kind, "conversation_id": None},
    )


async def _nudge(what: str, *, starts: timedelta, due: timedelta, now: datetime, status="pending"):
    from life_graph.models.db import Intention
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = Intention(tenant_id=TENANT, content=what, trigger_type="nudge", status=status,
                        trigger_time=now + starts, expires_at=now + due + timedelta(days=2),
                        context_match={"due_by": (now + due).isoformat(), "when": "this week",
                                       "said_at": (now - timedelta(days=1)).isoformat()})
        s.add(row)
        await s.commit()
        return row.id


@pytest.mark.asyncio
@skip_on_db_error
async def test_only_the_owners_own_words_make_a_promise_once():
    from life_graph.models.db import Intention
    from life_graph.services.capture_processors import CaptureProcessors
    from life_graph.storage.database import async_session

    proc = CaptureProcessors()
    async with async_session() as s:
        assert await proc._find_commitment(s, "I'll call the insurer this week", _capture("x"), TENANT) == 1
        await s.commit()
        # The same promise again, shared text, mail, and no promise at all: nothing.
        assert await proc._find_commitment(s, "I'll call the insurer this week", _capture("x"), TENANT) == 0
        shared = _capture("x", tier="external", kind="shared")
        assert await proc._find_commitment(s, "I'll pay Acme 5000 by Friday", shared, TENANT) == 0
        mail = _capture("x", surface="email", tier="external")
        assert await proc._find_commitment(s, "I will wire the money tomorrow", mail, TENANT) == 0
        assert await proc._find_commitment(s, "what's the weather?", _capture("x"), TENANT) == 0
        await s.commit()
        rows = (await s.execute(select(Intention).where(Intention.tenant_id == TENANT))).scalars().all()
    assert [(r.content, r.trigger_type, r.status) for r in rows] == [
        ("I'll call the insurer this week", "nudge", "pending")
    ]


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_job_sends_a_few_a_day_and_the_buttons_work(client):
    from life_graph.models.db import Intention, Notification
    from life_graph.services import nudges
    from life_graph.storage.database import async_session

    now = datetime.now(UTC).replace(hour=11, minute=0, second=0, microsecond=0)
    ids = [await _nudge(f"I'll do thing {i} this week", starts=-timedelta(hours=1), due=timedelta(days=i + 1), now=now)
           for i in range(4)]
    later = await _nudge("I'll do the later thing", starts=timedelta(hours=5), due=timedelta(days=2), now=now)
    old = await _nudge("I'll do the old thing", starts=-timedelta(days=5), due=-timedelta(days=3), now=now)

    async with async_session() as s:
        assert await nudges.run_tenant(s, TENANT, now.replace(hour=23), UTCZ) == {"sent": 0, "lapsed": 1}
    async with async_session() as s:
        assert await nudges.run_tenant(s, TENANT, now, UTCZ) == {"sent": 3, "lapsed": 0}
    async with async_session() as s:
        assert (await nudges.run_tenant(s, TENANT, now + timedelta(minutes=30), UTCZ))["sent"] == 0  # 3 a day
        rows = {r.id: r for r in (await s.execute(select(Intention).where(Intention.tenant_id == TENANT))).scalars()}
        notes = (await s.execute(select(Notification).where(Notification.tenant_id == TENANT))).scalars().all()
    assert [rows[i].status for i in ids] == ["nudged", "nudged", "nudged", "pending"]  # soonest deadlines first
    assert rows[later].status == "pending" and rows[old].status == "expired"
    assert {n.title for n in notes} == {nudges.TITLE}
    assert notes[0].body.startswith("“I'll do thing") and "you said so" in notes[0].body

    # From the phone's notification: Drop.
    first = next(n for n in notes if n.extra_metadata["item_id"] == str(ids[0]))
    listed = (await client.get("/api/v1/jarvis/notifications")).json()["data"]
    mine = next(n for n in (listed if isinstance(listed, list) else listed.get("items", [])) if n["id"] == str(first.id))
    assert [a["id"] for a in mine["actions"]] == ["done", "snooze_1d", "drop"]
    r = await client.post(f"/api/v1/jarvis/notifications/{first.id}/action", json={"action": "drop"})
    assert r.status_code == 200 and "won't bring it up" in r.json()["data"]["result"]

    # From the web: Tomorrow, then Done; a settled one cannot be acted on again.
    r = await client.post(f"/api/v1/jarvis/nudges/{ids[1]}", json={"action": "snooze_1d"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "pending"
    assert datetime.fromisoformat(r.json()["data"]["next_nudge_at"]) > datetime.now(UTC)
    assert (await client.post(f"/api/v1/jarvis/nudges/{ids[2]}", json={"action": "done"})).status_code == 200
    assert (await client.post(f"/api/v1/jarvis/nudges/{ids[2]}", json={"action": "done"})).status_code == 409
    assert (await client.post(f"/api/v1/jarvis/nudges/{ids[2]}", json={"action": "build"})).status_code == 422
    other = await client.post(f"/api/v1/jarvis/nudges/{ids[3]}", json={"action": "done"},
                              headers={"X-Tenant-ID": "someone_else"})
    assert other.status_code == 404

    open_now = {n["id"] for n in (await client.get("/api/v1/jarvis/nudges")).json()["data"]}
    assert {str(ids[1]), str(ids[3]), str(later)} <= open_now
    assert not open_now & {str(ids[0]), str(ids[2]), str(old)}  # dropped, done, expired
