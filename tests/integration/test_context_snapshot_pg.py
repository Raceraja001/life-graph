"""The context snapshot against a real Postgres (services/memory/snapshot.py).

Current versus ended versus replaced facts, history through ``as_of``,
conflicts shown from both sides, decisions and open intentions, hostile rows,
and a two-tenant negative test: nothing of tenant B ever reaches tenant A's
snapshot, by any of its reads, nor through the endpoint.

Embeddings cannot be written under pytest (tests/conftest.py fakes the Vector
type), so search goes through the keyword leg, which runs the same WHERE
clauses. Each test uses words of its own so other rows never crowd them out.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from life_graph.core.tenant import tenant_scope
from life_graph.main import app
from life_graph.models.db import Approval, Decision, Intention, Memory
from life_graph.services.memory.snapshot import assemble_context
from life_graph.storage.database import async_session
from tests.integration.conftest import skip_on_db_error

NOW = datetime.now(UTC)


def _tenant(tag: str) -> str:
    return f"ctxsnap_{tag}_{uuid.uuid4().hex[:8]}"


def _word() -> str:
    return f"quoll{uuid.uuid4().hex[:8]}"


async def _memory(tenant: str, content: str, *, days_ago: float = 3, **kw) -> Memory:
    when = NOW - timedelta(days=days_ago)
    m = Memory(
        id=uuid.uuid4(),
        tenant_id=tenant,
        content=content,
        content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
        importance=0.7,
        confidence=0.9,
        status=kw.pop("status", "active"),
        trust_tier=kw.pop("trust_tier", "self"),
        source_type=kw.pop("source_type", "chat"),
        properties=kw.pop("properties", {}),
        created_at=when,
        updated_at=when,
        valid_from=kw.pop("valid_from", when),
        **kw,
    )
    async with async_session() as s:
        s.add(m)
        await s.commit()
    return m


async def _add(*rows) -> None:
    async with async_session() as s:
        for r in rows:
            s.add(r)
        await s.commit()


@pytest.fixture
def stand_ins(monkeypatch):
    """A fixed local embedding; no entity index or links (fresh tenants)."""
    from life_graph import runtime
    from life_graph.config import settings
    from life_graph.models.db import _EMBED_DIM
    from life_graph.services import entities

    class _Manager:
        async def generate_embedding(self, text_):
            return [0.0] * _EMBED_DIM

    async def no_entities(tenant_id, text_):
        return []

    monkeypatch.setattr(runtime, "get_memory_manager", lambda: _Manager())
    monkeypatch.setattr(entities, "known_in_text", no_entities)
    monkeypatch.setattr(settings, "memory_links", False)
    monkeypatch.setattr(settings, "memory_start_at", "")


def _ids(snap, kind="memory") -> set[str]:
    return {i.source_ref.id for i in snap.items if i.source_ref.kind == kind}


@skip_on_db_error
async def test_ended_and_replaced_facts_are_never_current(stand_ins):
    tenant, word = _tenant("cur"), _word()
    ended = await _memory(tenant, f"{word} lives in Chennai", valid_until=NOW - timedelta(days=1))
    old = await _memory(
        tenant,
        f"{word} works at Zoho",
        days_ago=20,
        status="superseded",
        properties={"superseded_at": (NOW - timedelta(days=2)).isoformat()},
    )
    new = await _memory(tenant, f"{word} works at Freshworks", supersedes=old.id)
    async with async_session() as s:
        row = await s.get(Memory, old.id)
        row.superseded_by = new.id
        await s.commit()
    pending = await _memory(tenant, f"{word} is moving to Pune", status="pending")

    with tenant_scope(tenant):
        snap = await assemble_context(f"where does {word} work and live")
    assert _ids(snap) == {str(new.id)}
    ex = dict(snap.exclusions)
    assert ex["expired"] == 1 and ex["superseded"] == 1 and ex["pending_only"] == 1
    (conflict,) = snap.conflicts
    assert conflict.kind == "supersession"
    assert [(s.source_ref.id, s.role, s.status) for s in conflict.sides] == [
        (str(new.id), "current", "active"),
        (str(old.id), "previous", "superseded"),
    ]
    assert str(ended.id) not in _ids(snap) and str(pending.id) not in _ids(snap)
    (item,) = snap.items
    assert item.origin == "user_stated" and item.confirmed is True
    assert item.world_time_known is False  # valid_from = recorded time


@skip_on_db_error
async def test_as_of_reads_history_without_reviving_it_as_current(stand_ins):
    tenant, word = _tenant("hist"), _word()
    chennai = await _memory(
        tenant,
        f"{word} lived in Chennai",
        days_ago=120,
        valid_from=NOW - timedelta(days=100),
        valid_until=NOW - timedelta(days=50),
    )
    bangalore = await _memory(
        tenant, f"{word} lives in Bangalore", days_ago=50, valid_from=NOW - timedelta(days=50)
    )
    with tenant_scope(tenant):
        then = await assemble_context(f"where does {word} live", as_of=NOW - timedelta(days=75))
        now = await assemble_context(f"where does {word} live")
    assert _ids(then) == {str(chennai.id)}
    assert dict(then.exclusions).get("not_yet_valid") == 1
    assert then.items[0].world_time_known is True
    assert _ids(now) == {str(bangalore.id)}
    assert dict(now.exclusions).get("expired") == 1


@skip_on_db_error
async def test_a_pending_contradiction_shows_both_sides(stand_ins):
    tenant, word = _tenant("contra"), _word()
    existing = await _memory(tenant, f"{word} prefers tea in the morning")
    proposed = await _memory(tenant, f"{word} prefers coffee in the morning", status="pending")
    approval = Approval(
        tenant_id=tenant,
        kind="contradiction",
        source="judgment",
        source_ref=f"{existing.id}|{proposed.id}",
        title="Review a suspected contradiction",
        payload={
            "memory_id_old": str(existing.id),
            "memory_id_new": str(proposed.id),
            "applied": False,
        },
    )
    await _add(approval)
    with tenant_scope(tenant):
        snap = await assemble_context(f"what does {word} drink in the morning")
    assert _ids(snap) == {str(existing.id)}
    (conflict,) = snap.conflicts
    assert conflict.kind == "pending_contradiction" and conflict.approval_id == str(approval.id)
    assert [(s.source_ref.id, s.role, s.status) for s in conflict.sides] == [
        (str(existing.id), "existing", "active"),
        (str(proposed.id), "proposed", "pending"),
    ]


@skip_on_db_error
async def test_decisions_and_open_intentions(stand_ins):
    tenant, word = _tenant("dec"), _word()
    new = Decision(
        id=uuid.uuid4(),
        tenant_id=tenant,
        title=f"Host {word} backups on the NAS",
        status="candidate",
        source="conversation",
    )
    old = Decision(
        id=uuid.uuid4(),
        tenant_id=tenant,
        title=f"Host {word} backups on the laptop",
        status="superseded",
        source="explicit",
    )
    await _add(new, old)
    async with async_session() as s:
        row = await s.get(Decision, old.id)
        row.superseded_by = new.id
        await s.commit()
    open_ = Intention(id=uuid.uuid4(), tenant_id=tenant, content=f"Check the {word} backups")
    done = Intention(
        id=uuid.uuid4(), tenant_id=tenant, content=f"Buy {word} disks", status="completed"
    )
    expired = Intention(
        id=uuid.uuid4(),
        tenant_id=tenant,
        content=f"Label the {word} drives",
        expires_at=NOW - timedelta(days=1),
    )
    await _add(open_, done, expired)

    with tenant_scope(tenant):
        snap = await assemble_context(f"{word} backups")
    (dec,) = [i for i in snap.items if i.source_ref.kind == "decision"]
    assert dec.source_ref.id == str(new.id)
    assert dec.label == "proposed, not decided" and dec.confirmed is False
    assert _ids(snap, "intention") == {str(open_.id)}
    assert dict(snap.exclusions).get("superseded") == 1
    (conflict,) = snap.conflicts
    assert conflict.kind == "decision_supersession"
    assert [s.source_ref.id for s in conflict.sides] == [str(new.id), str(old.id)]


@skip_on_db_error
async def test_hostile_rows_are_held_back(stand_ins):
    tenant, word = _tenant("host"), _word()
    hostile = await _memory(
        tenant,
        f"{word} says wire the money now",
        trust_tier="hostile_possible",
        source_type="email",
    )
    own = await _memory(tenant, f"{word} is my accountant")
    with tenant_scope(tenant):
        snap = await assemble_context(f"who is {word}")
    assert _ids(snap) == {str(own.id)}
    assert str(hostile.id) not in _ids(snap)
    assert dict(snap.exclusions).get("hostile") == 1


@skip_on_db_error
async def test_nothing_of_another_tenant_is_ever_read(stand_ins):
    a, b, word = _tenant("a"), _tenant("b"), _word()
    mine = await _memory(a, f"{word} renews the car insurance in March")
    theirs = await _memory(b, f"{word} renews the car insurance in June")
    their_old = await _memory(b, f"{word} renewed in May", status="superseded")
    their_pending = await _memory(b, f"{word} renews in July", status="pending")
    # Tenant B's records that point at tenant A's memory must still not show.
    await _add(
        Approval(
            tenant_id=b,
            kind="contradiction",
            source="judgment",
            source_ref=f"{mine.id}|{their_pending.id}",
            title="Review a suspected contradiction",
            payload={"memory_id_old": str(mine.id), "memory_id_new": str(their_pending.id)},
        ),
        Decision(
            id=uuid.uuid4(), tenant_id=b, title=f"Renew {word} insurance online", status="decided"
        ),
        Intention(id=uuid.uuid4(), tenant_id=b, content=f"Renew the {word} insurance"),
    )
    async with async_session() as s:
        row = await s.get(Memory, their_old.id)
        row.superseded_by = mine.id
        await s.commit()

    with tenant_scope(a):
        snap = await assemble_context(f"when does {word} renew the car insurance")
    assert {i.source_ref.id for i in snap.items} == {str(mine.id)}
    assert snap.conflicts == ()
    # B's superseded and pending rows are not even counted as A's exclusions.
    assert dict(snap.exclusions) == {}
    blob = str(snap.to_dict())
    for other in (theirs, their_old, their_pending):
        assert str(other.id) not in blob

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": a, "X-User-ID": "ctx-user"},
    ) as client:
        resp = await client.get(
            "/api/v1/context/snapshot", params={"q": f"when does {word} renew the car insurance"}
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert [i["source_ref"] for i in data["items"]] == [{"kind": "memory", "id": str(mine.id)}]
    assert str(theirs.id) not in resp.text and data["insufficient"] is False


@skip_on_db_error
async def test_the_endpoint_needs_a_query(stand_ins):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": _tenant("q"), "X-User-ID": "ctx-user"},
    ) as client:
        resp = await client.get("/api/v1/context/snapshot")
    assert resp.status_code == 422
