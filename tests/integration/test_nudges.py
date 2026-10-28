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
        id=uuid.uuid4(),
        tenant_id=TENANT,
        surface=surface,
        trust_tier=tier,
        content=text,
        properties={"input": kind, "conversation_id": None},
    )


async def _nudge(what: str, *, starts: timedelta, due: timedelta, now: datetime, status="pending"):
    from life_graph.models.db import Intention
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = Intention(
            tenant_id=TENANT,
            content=what,
            trigger_type="nudge",
            status=status,
            trigger_time=now + starts,
            expires_at=now + due + timedelta(days=2),
            context_match={
                "due_by": (now + due).isoformat(),
                "when": "this week",
                "said_at": (now - timedelta(days=1)).isoformat(),
            },
        )
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
        assert (
            await proc._find_commitment(s, "I'll call the insurer this week", _capture("x"), TENANT)
            == 1
        )
        await s.commit()
        # The same promise again, shared text, mail, and no promise at all: nothing.
        assert (
            await proc._find_commitment(s, "I'll call the insurer this week", _capture("x"), TENANT)
            == 0
        )
        shared = _capture("x", tier="external", kind="shared")
        assert await proc._find_commitment(s, "I'll pay Acme 5000 by Friday", shared, TENANT) == 0
        mail = _capture("x", surface="email", tier="external")
        assert await proc._find_commitment(s, "I will wire the money tomorrow", mail, TENANT) == 0
        assert await proc._find_commitment(s, "what's the weather?", _capture("x"), TENANT) == 0
        await s.commit()
        rows = (
            (await s.execute(select(Intention).where(Intention.tenant_id == TENANT)))
            .scalars()
            .all()
        )
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
    ids = [
        await _nudge(
            f"I'll do thing {i} this week",
            starts=-timedelta(hours=1),
            due=timedelta(days=i + 1),
            now=now,
        )
        for i in range(4)
    ]
    later = await _nudge(
        "I'll do the later thing", starts=timedelta(hours=5), due=timedelta(days=2), now=now
    )
    old = await _nudge(
        "I'll do the old thing", starts=-timedelta(days=5), due=-timedelta(days=3), now=now
    )

    async with async_session() as s:
        assert await nudges.run_tenant(s, TENANT, now.replace(hour=23), UTCZ) == {
            "sent": 0,
            "lapsed": 1,
        }
    async with async_session() as s:
        assert await nudges.run_tenant(s, TENANT, now, UTCZ) == {"sent": 3, "lapsed": 0}
    async with async_session() as s:
        assert (await nudges.run_tenant(s, TENANT, now + timedelta(minutes=30), UTCZ))[
            "sent"
        ] == 0  # 3 a day
        rows = {
            r.id: r
            for r in (
                await s.execute(select(Intention).where(Intention.tenant_id == TENANT))
            ).scalars()
        }
        notes = (
            (await s.execute(select(Notification).where(Notification.tenant_id == TENANT)))
            .scalars()
            .all()
        )
    assert [rows[i].status for i in ids] == [
        "nudged",
        "nudged",
        "nudged",
        "pending",
    ]  # soonest deadlines first
    assert rows[later].status == "pending" and rows[old].status == "expired"
    assert {n.title for n in notes} == {nudges.TITLE}
    assert notes[0].body.startswith("“I'll do thing") and "you said so" in notes[0].body

    # From the phone's notification: Drop.
    first = next(n for n in notes if n.extra_metadata["item_id"] == str(ids[0]))
    listed = (await client.get("/api/v1/jarvis/notifications")).json()["data"]
    mine = next(
        n
        for n in (listed if isinstance(listed, list) else listed.get("items", []))
        if n["id"] == str(first.id)
    )
    assert [a["id"] for a in mine["actions"]] == ["done", "snooze_1d", "drop"]
    r = await client.post(
        f"/api/v1/jarvis/notifications/{first.id}/action", json={"action": "drop"}
    )
    assert r.status_code == 200 and "won't bring it up" in r.json()["data"]["result"]

    # From the web: Tomorrow, then Done; a settled one cannot be acted on again.
    r = await client.post(f"/api/v1/jarvis/nudges/{ids[1]}", json={"action": "snooze_1d"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "pending"
    assert datetime.fromisoformat(r.json()["data"]["next_nudge_at"]) > datetime.now(UTC)
    assert (
        await client.post(f"/api/v1/jarvis/nudges/{ids[2]}", json={"action": "done"})
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/jarvis/nudges/{ids[2]}", json={"action": "done"})
    ).status_code == 409
    assert (
        await client.post(f"/api/v1/jarvis/nudges/{ids[2]}", json={"action": "build"})
    ).status_code == 422
    other = await client.post(
        f"/api/v1/jarvis/nudges/{ids[3]}",
        json={"action": "done"},
        headers={"X-Tenant-ID": "someone_else"},
    )
    assert other.status_code == 404

    open_now = {n["id"] for n in (await client.get("/api/v1/jarvis/nudges")).json()["data"]}
    assert {str(ids[1]), str(ids[3]), str(later)} <= open_now
    assert not open_now & {str(ids[0]), str(ids[2]), str(old)}  # dropped, done, expired


async def _chat(tenant: str, context: dict | None = None):
    from life_graph.models.db import AgentSession, AgentTask
    from life_graph.storage.database import async_session

    async with async_session() as s:
        conv = AgentSession(
            tenant_id=tenant, user_message="insurer", routed_to="jarvis", context=context or {}
        )
        s.add(conv)
        await s.flush()
        s.add(
            AgentTask(
                tenant_id=tenant,
                agent_name="jarvis",
                task_name="chat:jarvis",
                session_id=conv.id,
                status="completed",
                input={"message": "I'll call the insurer this week"},
                result={"response": "Noted."},
                created_at=datetime(2026, 10, 27, 9, 0, tzinfo=UTC),
            )
        )
        await s.commit()
        return conv.id


async def _promise(tenant: str, what: str, conv_id, now: datetime):
    from life_graph.models.db import Intention
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = Intention(
            tenant_id=tenant,
            content=what,
            trigger_type="nudge",
            status="pending",
            trigger_time=now - timedelta(hours=1),
            expires_at=now + timedelta(days=4),
            context_match={
                "due_by": (now + timedelta(days=2)).isoformat(),
                "when": "this week",
                "said_at": (now - timedelta(days=1)).isoformat(),
                "conversation_id": str(conv_id) if conv_id else None,
            },
        )
        s.add(row)
        await s.commit()
        return row.id


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_nudge_is_said_in_the_chat_it_was_promised_in(client):
    from fastapi import HTTPException

    from life_graph.api.kernel import ChatStreamRequest, _load_chat_history, _regeneration
    from life_graph.models.db import Intention
    from life_graph.services import nudges
    from life_graph.storage.database import async_session

    # Its own tenant: the 3-a-day limit is per tenant, and the test above spends it.
    tenant = f"nudge_{uuid.uuid4().hex[:8]}"
    headers = {"X-Tenant-ID": tenant}
    api = "/api/v1/jarvis"
    now = datetime(2026, 10, 28, 11, 0, tzinfo=UTC)
    conv = await _chat(tenant)
    temp = await _chat(tenant, {"temporary": True})
    kept = await _promise(tenant, "I'll call the insurer this week", conv, now)
    hidden = await _promise(tenant, "I'll book the dentist this week", temp, now)
    loose = await _promise(tenant, "I'll renew the passport this week", uuid.uuid4(), now)

    async with async_session() as s:
        assert (await nudges.run_tenant(s, tenant, now, UTCZ))["sent"] == 3
        rows = {
            r.id: r.status
            for r in (
                await s.execute(select(Intention).where(Intention.tenant_id == tenant))
            ).scalars()
        }
    assert rows[kept] == rows[hidden] == rows[loose] == "nudged"

    r = await client.get(f"{api}/conversations/{conv}/messages", headers=headers)
    msgs = r.json()["data"]
    said = msgs[-1]
    assert said["role"] == "assistant" and said["persona"] == "jarvis"
    assert said["content"] == (
        "You said you would: “I'll call the insurer this week” — you said so yesterday."
    )
    assert said["nudge"] == {"id": str(kept), "status": "nudged"}
    assert [m["role"] for m in msgs] == ["user", "assistant", "assistant"]  # no question invented

    # Only in the chat it came from: a temporary chat gets the notification only.
    r = await client.get(f"{api}/conversations/{temp}/messages", headers=headers)
    assert all("nudge" not in m for m in (r.json().get("data") or []))

    # The next turn's history is the owner's own exchanges; it cannot be asked again.
    assert await _load_chat_history(tenant, conv) == [
        {"role": "user", "content": "I'll call the insurer this week"},
        {"role": "assistant", "content": "Noted."},
    ]
    with pytest.raises(HTTPException) as refused:
        await _regeneration(tenant, ChatStreamRequest(regenerates=uuid.UUID(said["task_id"])))
    assert refused.value.status_code == 409

    # Done from the chat's button; the message then shows it settled.
    r = await client.post(f"{api}/nudges/{kept}", json={"action": "done"}, headers=headers)
    assert r.status_code == 200
    r = await client.get(f"{api}/conversations/{conv}/messages", headers=headers)
    assert r.json()["data"][-1]["nudge"] == {"id": str(kept), "status": "completed"}


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_brief_counts_open_promises_without_their_words():
    from life_graph.services import nudges
    from life_graph.services.assistant_daily import brief_lines
    from life_graph.storage.database import async_session

    tenant = f"nudge_{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    assert not [
        ln for ln in await brief_lines(async_session, tenant) if ln.startswith(nudges.TITLE)
    ]
    await _promise(tenant, "I'll call the insurer about the claim this week", None, now)
    await _promise(tenant, "I'll book the dentist this week", None, now)
    lines = await brief_lines(async_session, tenant)
    line = next(ln for ln in lines if ln.startswith(nudges.TITLE))
    assert line == "You said you would: 2 things open — Done, Tomorrow or Drop in chat"
    assert "insurer" not in line and "dentist" not in line
    assert nudges.brief_line(1) == (
        "You said you would: 1 thing open — Done, Tomorrow or Drop in chat"
    )
