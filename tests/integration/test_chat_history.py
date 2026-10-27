"""A chat history that remembers (docs/specs/web-chat-wave1.md F6) against the
database: search, pin and rename, and regenerating the latest reply.

Conversations and turns are written straight to the database. No model runs:
the process manager is a stub that records what it was asked to run and ends
the stream, as in test_temporary_chat.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import skip_on_db_error

TENANT = f"hist_{uuid.uuid4().hex[:8]}"
OTHER = f"hist_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT}
API = "/api/v1/jarvis"


class _Persona:
    async def get_by_name(self, tenant_id, name):
        if name == "nobody":
            return None
        return {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "name": name, "is_active": True}


class _PM:
    """Records each spawn and ends its stream at once."""

    def __init__(self):
        self.spawns: list[dict] = []

    @property
    def inputs(self) -> list[dict]:
        return [s["input_data"] for s in self.spawns]

    async def spawn(self, **kw):
        from life_graph.services.chat_stream import get_chat_stream_bus

        self.spawns.append(kw)
        task_id = str(uuid.uuid4())
        bus = get_chat_stream_bus()

        async def publish():
            await asyncio.sleep(0)
            bus.publish(
                task_id,
                {"task_id": task_id, "agent_name": "jarvis", "depth": 0, "event": {"type": "done"}},
            )

        asyncio.create_task(publish())
        return {"task_id": task_id}


@pytest.fixture
def pm(monkeypatch):
    from life_graph.api import dependencies, jarvis

    stub = _PM()
    captured: list[str] = []

    async def capture(tenant_id, text, *a, **k):
        captured.append(text)

    monkeypatch.setattr(dependencies, "get_process_manager", lambda: stub)
    monkeypatch.setattr(dependencies, "get_persona_service", lambda: _Persona())
    monkeypatch.setattr(jarvis, "_capture", capture)
    stub.captured = captured
    return stub


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as c:
        yield c


_CLOCK = datetime.now(UTC) - timedelta(hours=2)


def _tick() -> datetime:
    """Strictly increasing creation times, so 'newest' never ties."""
    global _CLOCK
    _CLOCK += timedelta(seconds=5)
    return _CLOCK


async def _conversation(
    tenant: str,
    turns: list[tuple[str, str | None]],
    *,
    context: dict | None = None,
    routed_to: str = "jarvis",
    status: str = "completed",
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """A conversation with these (asked, answered) turns, oldest first; the
    last turn gets ``status``."""
    from life_graph.models.db import AgentSession
    from life_graph.storage.database import async_session

    async with async_session() as s:
        conv = AgentSession(
            tenant_id=tenant,
            user_message=turns[0][0],
            routed_to=routed_to,
            context=context or {},
        )
        conv.created_at = _tick()
        s.add(conv)
        await s.flush()
        ids = []
        for i, (asked, answered) in enumerate(turns):
            ids.append(
                await _add_turn(
                    s,
                    tenant,
                    conv.id,
                    asked,
                    answered,
                    status=(status if i == len(turns) - 1 else "completed"),
                )
            )
        await s.commit()
        return conv.id, ids


async def _add_turn(s, tenant, conv_id, asked, answered, *, status="completed", **extra):
    from life_graph.models.db import AgentTask

    turn = AgentTask(
        tenant_id=tenant,
        agent_name="jarvis",
        task_name="chat:jarvis",
        session_id=conv_id,
        status=status,
        input={"message": asked, "history": [], **extra},
        result={"response": answered} if answered else {},
    )
    turn.created_at = _tick()
    s.add(turn)
    await s.flush()
    return turn.id


async def _listed(client, **params) -> list[dict]:
    r = await client.get(f"{API}/conversations", params=params)
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ── AC-W6.1 search ─────────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_search_finds_words_in_messages_and_replies_and_nothing_else(client):
    dentist, _ = await _conversation(
        TENANT, [("hello", "hi"), ("Book the dentist for Friday, please", "Booked for 10am.")]
    )
    weather, _ = await _conversation(TENANT, [("what is it like out", "Chennai is hot today")])
    long_reply = "word " * 50 + "the zebra crossing is closed " + "more " * 50
    zebra, _ = await _conversation(TENANT, [("any news", long_reply)])
    temp, _ = await _conversation(
        TENANT, [("my dentist secret", "ok")], context={"temporary": True}
    )
    scribe, _ = await _conversation(TENANT, [("dentist notes", "ok")], routed_to="scribe")
    theirs, _ = await _conversation(OTHER, [("dentist on friday", "ok")])

    found = await _listed(client, q="dentist")
    assert [c["id"] for c in found] == [str(dentist)]
    assert found[0]["match"] == "Book the dentist for Friday, please"

    # All the words, in any order, whole words only, newest first.
    assert [c["id"] for c in await _listed(client, q="friday DENTIST")] == [str(dentist)]
    assert await _listed(client, q="dent") == []
    assert await _listed(client, q="dentist tuesday") == []

    # A reply matches too, and a long one is cut around the words.
    hit = await _listed(client, q="chennai")
    assert [c["id"] for c in hit] == [str(weather)] and hit[0]["match"] == "Chennai is hot today"
    hit = await _listed(client, q="zebra")
    assert [c["id"] for c in hit] == [str(zebra)]
    assert "zebra" in hit[0]["match"] and len(hit[0]["match"]) <= 120

    # Nothing found; a temporary, another persona's or another tenant's chat never shows.
    assert await _listed(client, q="xylophone") == []
    assert await _listed(client, q="secret") == []
    assert await _listed(client, q="notes") == []
    every = {c["id"] for c in await _listed(client, limit=200)}
    assert str(temp) not in every and str(scribe) not in every and str(theirs) not in every
    r = await client.get(
        f"{API}/conversations", params={"q": "dentist"}, headers={"X-Tenant-ID": OTHER}
    )
    assert [c["id"] for c in r.json()["data"]] == [str(theirs)]

    # Without q (or with only spaces) it is the plain list, without match.
    plain = await _listed(client, q="  ")
    assert str(dentist) in {c["id"] for c in plain} and "match" not in plain[0]


# ── AC-W6.2 pin and rename ─────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_pinned_first_renamed_and_context_merged(client):
    tenant = f"hist_{uuid.uuid4().hex[:8]}"
    h = {"X-Tenant-ID": tenant}
    older, _ = await _conversation(tenant, [("the older chat", "ok")], context={"keep": 1})
    newer, _ = await _conversation(tenant, [("the newer chat", "ok")])

    async def listed():
        r = await client.get(f"{API}/conversations", headers=h)
        return r.json()["data"]

    assert [c["id"] for c in await listed()] == [str(newer), str(older)]
    assert all(c["pinned"] is False for c in await listed())

    r = await client.patch(f"{API}/conversations/{older}", json={"pinned": True}, headers=h)
    assert r.status_code == 200 and r.json()["data"]["pinned"] is True
    first = (await listed())[0]
    assert first["id"] == str(older) and first["pinned"] is True
    assert first["title"] == "the older chat"

    r = await client.patch(
        f"{API}/conversations/{older}", json={"title": "  Trip   plans "}, headers=h
    )
    assert r.status_code == 200
    first = (await listed())[0]
    assert first["title"] == "Trip plans" and first["pinned"] is True  # rename kept the pin

    # It is found by its words still, and keeps its new title there.
    r = await client.get(f"{API}/conversations", params={"q": "older"}, headers=h)
    assert r.json()["data"][0]["title"] == "Trip plans"

    r = await client.patch(f"{API}/conversations/{older}", json={"pinned": False}, headers=h)
    assert [c["id"] for c in await listed()] == [str(newer), str(older)]

    from life_graph.models.db import AgentSession
    from life_graph.storage.database import async_session

    async with async_session() as s:
        ctx = (await s.get(AgentSession, older)).context
    assert ctx == {"keep": 1, "title": "Trip plans", "pinned": False}

    for bad in ({}, {"title": ""}, {"title": "   "}, {"title": "x" * 81}):
        r = await client.patch(f"{API}/conversations/{older}", json=bad, headers=h)
        assert r.status_code == 422, bad


@pytest.mark.asyncio
@skip_on_db_error
async def test_pin_refuses_other_tenants_other_personas_and_temporary_chats(client):
    from life_graph.models.db import AgentSession
    from life_graph.storage.database import async_session

    theirs, _ = await _conversation(OTHER, [("theirs", "ok")])
    scribe, _ = await _conversation(TENANT, [("a scribe chat", "ok")], routed_to="scribe")
    for conv in (theirs, scribe, uuid.uuid4()):
        r = await client.patch(f"{API}/conversations/{conv}", json={"pinned": True})
        assert r.status_code == 404

    temp, _ = await _conversation(TENANT, [("temp", "ok")], context={"temporary": True})
    r = await client.patch(f"{API}/conversations/{temp}", json={"pinned": True})
    assert r.status_code == 409
    # Renaming it is harmless, and it stays temporary.
    r = await client.patch(f"{API}/conversations/{temp}", json={"title": "scratch"})
    assert r.status_code == 200
    async with async_session() as s:
        ctx = (await s.get(AgentSession, temp)).context
    assert ctx == {"temporary": True, "title": "scratch"}


# ── AC-W6.3 regenerate ─────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_regenerate_asks_the_latest_message_again_and_keeps_both(pm, client):
    from life_graph.api.kernel import _load_chat_history
    from life_graph.storage.database import async_session

    conv, (t1, t2) = await _conversation(
        TENANT, [("hello", "hi there"), ("pick a film for tonight", "Jailer")]
    )

    r = await client.post(f"{API}/turns/{t2}/regenerate", json={"persona": "scribe"})
    assert r.status_code == 200, r.text
    assert '"type": "done"' in r.text or '"type":"done"' in r.text
    sent = pm.spawns[-1]
    assert sent["agent_name"] == "scribe" and sent["session_id"] == conv
    assert sent["input_data"]["message"] == "pick a film for tonight"
    assert sent["input_data"]["regenerates"] == str(t2)
    assert sent["input_data"]["history"] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    assert "temporary" not in sent["input_data"]
    assert pm.captured == []  # the words were captured the first time

    # With no body it is Jarvis again.
    r = await client.post(f"{API}/turns/{t2}/regenerate")
    assert r.status_code == 200 and pm.spawns[-1]["agent_name"] == "jarvis"

    # Only the latest turn; not another tenant's, not a missing one.
    assert (await client.post(f"{API}/turns/{t1}/regenerate")).status_code == 409
    assert (await client.post(f"{API}/turns/{uuid.uuid4()}/regenerate")).status_code == 404
    _, (theirs,) = await _conversation(OTHER, [("theirs", "ok")])
    assert (await client.post(f"{API}/turns/{theirs}/regenerate")).status_code == 404
    assert (
        await client.post(f"{API}/turns/{t2}/regenerate", json={"persona": "nobody"})
    ).status_code == 404

    # The new version, as the spawned run would store it.
    async with async_session() as s:
        t3 = await _add_turn(
            s, TENANT, conv, "pick a film for tonight", "Vikram", regenerates=str(t2)
        )
        await s.commit()

    # The next turn sees only the chosen version.
    assert await _load_chat_history(TENANT, conv) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "pick a film for tonight"},
        {"role": "assistant", "content": "Vikram"},
    ]

    # Both stay in the messages; the old reply is marked, the question not repeated.
    r = await client.get(f"{API}/conversations/{conv}/messages")
    msgs = r.json()["data"]
    assert [(m["role"], m["content"]) for m in msgs] == [
        ("user", "hello"),
        ("assistant", "hi there"),
        ("user", "pick a film for tonight"),
        ("assistant", "Jailer"),
        ("assistant", "Vikram"),
    ]
    assert msgs[3]["superseded_by"] == str(t3) and msgs[3]["task_id"] == str(t2)
    assert msgs[4]["regenerates"] == str(t2) and "superseded_by" not in msgs[4]
    assert "superseded_by" not in msgs[1]

    # The old version is no longer the latest; the new one can be regenerated,
    # and its history leaves out both versions.
    assert (await client.post(f"{API}/turns/{t2}/regenerate")).status_code == 409
    r = await client.post(f"{API}/turns/{t3}/regenerate")
    assert r.status_code == 200
    again = pm.inputs[-1]
    assert again["regenerates"] == str(t3) and again["message"] == "pick a film for tonight"
    assert [m["content"] for m in again["history"]] == ["hello", "hi there"]
    assert pm.captured == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_regenerate_resends_shared_text_and_refuses_a_running_turn(pm, client):
    from life_graph.storage.database import async_session

    conv, (t1,) = await _conversation(TENANT, [("hello", "hi")])
    async with async_session() as s:
        shared = await _add_turn(
            s,
            TENANT,
            conv,
            "<fenced> what does this say",
            "It is a bill.",
            owner_message="what does this say",
            shared="Electricity bill: Rs 1,200",
        )
        await s.commit()

    r = await client.post(f"{API}/turns/{shared}/regenerate")
    assert r.status_code == 200
    sent = pm.inputs[-1]
    assert sent["owner_message"] == "what does this say"
    assert sent["shared"] == "Electricity bill: Rs 1,200"
    assert "client_id" not in sent and pm.captured == []

    running, (busy,) = await _conversation(TENANT, [("slow one", None)], status="running")
    assert (await client.post(f"{API}/turns/{busy}/regenerate")).status_code == 409


@pytest.mark.asyncio
@skip_on_db_error
async def test_regenerating_a_temporary_chat_keeps_it_temporary(pm, client):
    conv, (t1,) = await _conversation(
        TENANT, [("what is my locker code", "I can't know that")], context={"temporary": True}
    )

    r = await client.post(f"{API}/turns/{t1}/regenerate")
    assert r.status_code == 200
    sent = pm.inputs[-1]
    assert sent["temporary"] is True and sent["regenerates"] == str(t1)
    assert pm.captured == []

    # Only Jarvis's model can be held local.
    before = len(pm.spawns)
    r = await client.post(f"{API}/turns/{t1}/regenerate", json={"persona": "scribe"})
    assert r.status_code == 400 and len(pm.spawns) == before

    # Still never listed.
    assert str(conv) not in {c["id"] for c in await _listed(client, limit=200)}


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_kernel_stream_regenerates_too(pm, client):
    """The web chat's own stream takes ``regenerates`` (api/kernel.py)."""
    # The originals kernel.py depends on (the pm fixture replaced the module names).
    from life_graph.api import kernel
    from life_graph.main import app

    app.dependency_overrides[kernel.get_process_manager] = lambda: pm
    app.dependency_overrides[kernel.get_persona_service] = lambda: _Persona()
    try:
        conv, (t1, t2) = await _conversation(TENANT, [("one", "1"), ("two", "2")])
        r = await client.post(
            "/api/v1/kernel/chat/stream", json={"regenerates": str(t2), "message": "ignored"}
        )
        assert r.status_code == 200
        sent = pm.inputs[-1]
        assert sent["message"] == "two" and sent["regenerates"] == str(t2)
        assert [m["content"] for m in sent["history"]] == ["one", "1"]

        other, _ = await _conversation(TENANT, [("elsewhere", "ok")])
        r = await client.post(
            "/api/v1/kernel/chat/stream",
            json={"regenerates": str(t2), "session_id": str(other)},
        )
        assert r.status_code == 409

        # Without regenerates a message is still required.
        r = await client.post("/api/v1/kernel/chat/stream", json={"message": ""})
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(kernel.get_process_manager, None)
        app.dependency_overrides.pop(kernel.get_persona_service, None)
