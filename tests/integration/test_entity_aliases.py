"""One person, many names, against the database (services/entities.py, migration 057).

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

    async def no_embedding(self, text):
        return None

    monkeypatch.setattr(manager._extractor, "extract", fake_extract)
    # On the class: undoing an instance patch leaves a bound method on the shared
    # manager, which hides later class-level patches (test_judged_search).
    monkeypatch.setattr(type(manager), "_generate_embedding", no_embedding)
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


# ── Review of PR #205 (2026-10-31) ─────────────────────────────────────────


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_mother_in_law_is_never_merged_with_the_mother(monkeypatch):
    t = _tenant()
    await _ingest(monkeypatch, t, [_fact("My mother Meena lives in Madurai.")])
    await _ingest(monkeypatch, t, [_fact("Meenakshi is my mother-in-law.")])
    await _ingest(monkeypatch, t, [_fact("Kamala, my mother in law, visited.")])
    meena, meenakshi = await _entity(t, "meena"), await _entity(t, "meenakshi")
    assert meena.canonical_id is None and meena.role == "mother"
    assert meenakshi.canonical_id is None and meenakshi.role == "mother_in_law"
    kamala = await _entity(t, "kamala")
    assert kamala.role == "mother_in_law" and kamala.canonical_id is None
    # Two mothers-in-law with unfitting names are asked about; the mother never is.
    for ask in await _approvals(t):
        assert str(meena.id) not in (ask.payload["alias_id"], ask.payload["canonical_id"])
        assert ask.payload["applied"] is False


@pytest.mark.asyncio
@skip_on_db_error
async def test_only_the_facts_own_firm_words_teach_names(monkeypatch):
    t = _tenant()
    message = "I think Ravi is short for Ravindran, not sure. My wife Priya teaches at DAV."
    from life_graph.extraction.rules import ExtractedFact

    (priya,) = await _ingest(
        monkeypatch,
        t,
        [
            ExtractedFact(
                content="My wife Priya teaches at DAV.",
                fact_type="fact",
                confidence=0.95,
                source_text=message,  # the LLM extractor passes the whole message
            )
        ],
    )
    assert (await _row(priya.id)).status == "active"
    assert (await _entity(t, "priya")).role == "spouse"
    assert await _entity(t, "ravi") is None and await _entity(t, "ravindran") is None


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_memory_waiting_for_review_teaches_no_names(monkeypatch):
    t = _tenant()
    fact = _fact("Anushka (Anu) is in class 2.")
    fact.confidence = 0.5  # below the auto-keep bar: waits for the owner's review
    (held,) = await _ingest(monkeypatch, t, [fact])
    assert (await _row(held.id)).status == "pending"
    assert await _entity(t, "anu") is None
    assert await _approvals(t) == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_sentence_words_and_denials_link_nobody(monkeypatch):
    t = _tenant()
    await _ingest(monkeypatch, t, [_fact("My mother Lakshmi has diabetes.")])
    await _ingest(monkeypatch, t, [_fact("Nobody calls her Lakshmi.")])
    await _ingest(monkeypatch, t, [_fact("Remember I call her Ammu.")])
    lakshmi = await _entity(t, "lakshmi")
    assert lakshmi.canonical_id is None
    assert await _entity(t, "nobody") is None and await _entity(t, "remember") is None
    ammu = await _entity(t, "ammu")
    assert ammu is None or ammu.canonical_id is None


@pytest.mark.asyncio
@skip_on_db_error
async def test_rejecting_a_role_link_takes_back_all_of_it(monkeypatch):
    from life_graph.services import entities

    t = _tenant()
    await _ingest(monkeypatch, t, [_fact("My wife Mahalakshmi works at a bank.")])
    await _ingest(monkeypatch, t, [_fact("Maha (Ma) loves filter coffee.")])
    ma, maha = await _entity(t, "ma"), await _entity(t, "maha")
    assert ma.canonical_id == maha.id and ma.alias_via == "said"

    # The role links Maha to Mahalakshmi; Ma comes along through Maha.
    await _ingest(monkeypatch, t, [_fact("My wife Maha sings Carnatic music.")])
    mahal = await _entity(t, "mahalakshmi")
    assert (await _entity(t, "maha")).canonical_id == mahal.id
    named = await entities.known_in_text(t, "Is Ma at home?")
    assert mahal.id in {eid for eid, _ in named}
    (applied,) = [a for a in await _approvals(t) if a.payload["applied"]]

    # The owner says no: Maha and her nickname Ma leave Mahalakshmi together.
    await _resolve(t, applied.id, "reject")
    maha, ma = await _entity(t, "maha"), await _entity(t, "ma")
    assert maha.canonical_id is None
    assert ma.canonical_id == maha.id
    named = await entities.known_in_text(t, "Is Ma at home?")
    assert mahal.id not in {eid for eid, _ in named}
    assert (await _entity(t, "mahalakshmi")).role == "spouse"  # her own, never copied


# -- Bake-off leftovers (2026-10-31) ------------------------------------------


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_name_in_brackets_links_and_the_card_shows_one_person(monkeypatch):
    from life_graph.services import profile_card

    t = _tenant()
    await _ingest(
        monkeypatch,
        t,
        [_fact("Priya's birthday is on 14 February.", slot="family.priya.birthday")],
    )
    content = "Priyadharshini (the owner's wife, called Priya) teaches maths at Sunrise School."
    await _ingest(monkeypatch, t, [_fact(content, slot="family.priyadharshini.occupation")])
    pd, priya = await _entity(t, "priyadharshini"), await _entity(t, "priya")
    assert priya.canonical_id == pd.id and pd.role == "spouse"
    profile_card.clear_cache()
    slots = {c["slot"] for c in await profile_card.card_items(t)}
    assert {"family.priyadharshini.birthday", "family.priyadharshini.occupation"} <= slots
    assert "family.priya.birthday" not in slots


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_tamil_case_form_is_not_learned_as_a_nickname(monkeypatch):
    t = _tenant()
    await _ingest(monkeypatch, t, [_fact("Priya (Priyavukku) always loves jasmine flowers.")])
    form = await _entity(t, "priyavukku")
    assert form is None or form.canonical_id is None
    assert not await _approvals(t)
