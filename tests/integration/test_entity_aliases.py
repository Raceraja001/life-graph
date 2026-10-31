"""One person, many names, against the database (services/entities.py, migration 056).

The extractor is a stand-in (no model call): here only the wiring is checked —
what the owner's words link, what they never link, and that every link can be
undone through the approvals queue.
"""

from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import skip_on_db_error


def _tenant() -> str:
    return f"alias_{uuid.uuid4().hex[:8]}"


def _fact(content, *, slot=None, subject="owner", entities=(), **kw):
    from life_graph.extraction.rules import ExtractedFact

    return ExtractedFact(
        content=content,
        fact_type="fact",
        confidence=0.95,
        source_text=content,
        slot=slot,
        subject=subject,
        entities=list(entities),
        **kw,
    )


async def _ingest(monkeypatch, tenant, facts, *, tier="self"):
    from life_graph.api.dependencies import get_memory_manager
    from life_graph.core.tenant import tenant_scope

    manager = get_memory_manager()

    class _Result:
        def __init__(self, f):
            self.facts = f

    async def fake_extract(text, capture=False):
        return _Result(list(facts))

    async def no_embedding(text):
        return None

    monkeypatch.setattr(manager._extractor, "extract", fake_extract)
    monkeypatch.setattr(manager, "_generate_embedding", no_embedding)
    with tenant_scope(tenant):
        return await manager.ingest("…", source="capture", trust_tier=tier, capture=True)


async def _entity(tenant, key):
    from sqlalchemy import select

    from life_graph.models.assistant import Entity
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (
            await s.execute(select(Entity).where(Entity.tenant_id == tenant, Entity.key == key))
        ).scalar_one_or_none()


async def _approvals(tenant):
    from sqlalchemy import select

    from life_graph.models.db import Approval
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return list(
            (
                await s.execute(
                    select(Approval).where(
                        Approval.tenant_id == tenant, Approval.kind == "entity_alias"
                    )
                )
            )
            .scalars()
            .all()
        )


async def _resolve(tenant, approval_id, decision):
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    async with async_session() as s:
        await ApprovalService(s).resolve(tenant, str(approval_id), decision)
        await s.commit()


async def _row(mid):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(str(mid)))


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_nickname_finds_what_was_said_with_the_full_name(monkeypatch):
    from life_graph.services import entities

    t = _tenant()
    await _ingest(
        monkeypatch,
        t,
        [
            _fact(
                "My wife Mahalakshmi — I call her Maha — works at a bank.", entities=["Mahalakshmi"]
            )
        ],
    )
    (bday,) = await _ingest(
        monkeypatch,
        t,
        [
            _fact(
                "Mahalakshmi's birthday is 4 March.",
                subject="Mahalakshmi",
                slot="family.mahalakshmi.birthday",
                entities=["Mahalakshmi"],
            )
        ],
    )
    maha, mahal = await _entity(t, "maha"), await _entity(t, "mahalakshmi")
    assert maha.canonical_id == mahal.id and maha.alias_via == "said"
    assert mahal.role == "spouse"

    for question in ("When is Maha's birthday?", "When is my wife's birthday?"):
        named = await entities.known_in_text(t, question)
        assert mahal.id in {eid for eid, _ in named}, question
        found = await entities.memories_for(t, [eid for eid, _ in named])
        assert bday.id in {m.id for m in found}, question
    hint = entities.alias_hint(t, await entities.known_in_text(t, "Maha?"))
    assert hint == "Names: Mahalakshmi = Maha (the owner's spouse)"
    about = await entities.about(t, "Maha")
    assert bday.id in {m.id for m in about["memories"]}

    # A new value said with the nickname replaces the one said with the full name.
    (new,) = await _ingest(
        monkeypatch,
        t,
        [
            _fact(
                "Maha's birthday is 5 March.",
                subject="Maha",
                slot="family.maha.birthday",
                correction=True,
            )
        ],
    )
    assert (await _row(new.id)).properties["slot"] == "family.mahalakshmi.birthday"
    assert (await _row(bday.id)).status == "superseded"


@pytest.mark.asyncio
@skip_on_db_error
async def test_two_people_who_share_a_first_name_are_not_merged(monkeypatch):
    t = _tenant()
    await _ingest(monkeypatch, t, [_fact("My wife Priyadharshini, called Priya, teaches maths.")])
    await _ingest(
        monkeypatch, t, [_fact("My colleague Priya Venkat, called Priya, joined Tessera.")]
    )
    priya, wife, colleague = (
        await _entity(t, "priya"),
        await _entity(t, "priyadharshini"),
        await _entity(t, "priya venkat"),
    )
    assert priya.canonical_id == wife.id  # unchanged by the second statement
    assert colleague.canonical_id is None and wife.canonical_id is None
    (ask,) = await _approvals(t)
    assert ask.status == "pending" and ask.payload["applied"] is False
    assert ask.payload["canonical_id"] == str(colleague.id)

    # The owner says yes: "Priya" now names the colleague. Nothing was deleted.
    await _resolve(t, ask.id, "approve")
    priya = await _entity(t, "priya")
    assert priya.canonical_id == colleague.id and priya.alias_via == "approved"
    assert await _entity(t, "priyadharshini") is not None


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_shared_role_links_fitting_names_undoably_and_asks_about_others(monkeypatch):
    t = _tenant()
    await _ingest(monkeypatch, t, [_fact("My wife Mahalakshmi works at a bank.")])
    await _ingest(monkeypatch, t, [_fact("My wife Ma loves filter coffee.")])
    ma, mahal = await _entity(t, "ma"), await _entity(t, "mahalakshmi")
    assert ma.canonical_id == mahal.id and ma.alias_via == "role"
    (applied,) = await _approvals(t)
    assert applied.payload["applied"] is True

    await _ingest(monkeypatch, t, [_fact("My wife Divya runs marathons.")])
    divya = await _entity(t, "divya")
    assert divya.canonical_id is None  # unrelated name: asked, not linked
    suggested = [a for a in await _approvals(t) if a.payload["applied"] is False]
    assert len(suggested) == 1

    # Rejecting the role link makes "Ma" her own entity again.
    await _resolve(t, applied.id, "reject")
    assert (await _entity(t, "ma")).canonical_id is None


@pytest.mark.asyncio
@skip_on_db_error
async def test_outside_or_negated_text_teaches_no_names(monkeypatch):
    t = _tenant()
    await _ingest(monkeypatch, t, [_fact("Anushka (Anu) is in class 2.")], tier="external")
    await _ingest(monkeypatch, t, [_fact("Vikram (Vicky) is not my son.", polarity="negate")])
    assert await _entity(t, "anu") is None
    assert await _entity(t, "vicky") is None
    assert await _approvals(t) == []
