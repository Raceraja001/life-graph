"""Cold memory, learned links and the nightly form fill against the database (2026-10-31).

- services/memory_tiers.py: archived and replaced memories are searched when
  nothing active answers, labelled; what the owner took back or a bulk clean-up
  moved out never is; one that answers goes back to active.
- services/associations.py: facts said together are linked, links strengthen
  with use, and a found memory brings its linked ones along.
- services/form_fill.py: unchecked memories get a slot; a same-slot clash is
  offered, not applied.

The models are stand-ins (judge, slot question, no embeddings): the models are
measured by the bake-off; here only the wiring is checked.
"""

from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"tiers_{uuid.uuid4().hex[:8]}"


def _fact(content, **kw):
    from life_graph.extraction.rules import ExtractedFact

    return ExtractedFact(content=content, fact_type="fact", confidence=0.95, **kw)


async def _ingest(monkeypatch, facts, *, tier="self"):
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
    with tenant_scope(TENANT):
        return await manager.ingest("…", source="capture", trust_tier=tier, capture=True)


async def _put(content, status, **props):
    """A memory stored directly in *status*, with *props*."""
    from life_graph.api.dependencies import get_store
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.schemas import MemoryCreate

    with tenant_scope(TENANT):
        return await get_store().store(
            MemoryCreate(content=content, properties=props, source_type="capture"),
            trust_tier="self",
            status=status,
        )


async def _row(mid):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(str(mid)))


async def _strength(a, b) -> float:
    from sqlalchemy import text

    from life_graph.storage.database import async_session

    lo, hi = sorted([str(a), str(b)])
    async with async_session() as s:
        return float(
            (
                await s.execute(
                    text(
                        "SELECT strength FROM memory_links WHERE source_memory_id = :a"
                        " AND target_memory_id = :b AND link_type = 'ASSOCIATED'"
                    ),
                    {"a": lo, "b": hi},
                )
            ).scalar_one()
        )


@pytest.mark.asyncio
@skip_on_db_error
async def test_facts_said_together_are_linked_and_strengthen_with_use(monkeypatch):
    from life_graph.services import associations

    tag = uuid.uuid4().hex[:6]
    a, b, c = await _ingest(
        monkeypatch,
        [
            _fact(f"The owner's wife Priya teaches at DAV school ({tag})."),
            _fact(f"Priya takes the 8:10 bus every morning ({tag})."),
            _fact(f"Priya's school closes at 3 pm on Fridays ({tag})."),
        ],
    )
    first = await _strength(a.id, b.id)
    assert first == pytest.approx(associations.SAID_TOGETHER)

    near = await associations.neighbours(TENANT, [a.id])
    assert {m.id for m in near} == {b.id, c.id}

    await associations.used_together(TENANT, [a.id, b.id])
    assert await _strength(a.id, b.id) > first
    # Used together again: stronger still, never above 1.
    for _ in range(10):
        await associations.used_together(TENANT, [a.id, b.id])
    assert first < await _strength(a.id, b.id) <= 1.0


@pytest.mark.asyncio
@skip_on_db_error
async def test_cold_search_reads_archived_and_replaced_but_not_what_was_taken_back():
    from life_graph.core.tenant import tenant_scope
    from life_graph.services import memory_tiers
    from life_graph.storage.database import async_session

    tag = uuid.uuid4().hex[:6]
    word = f"zephyrine{tag}"
    old = await _put(f"The owner's {word} bicycle is red.", "archived")
    gone = await _put(f"The owner's {word} bicycle is blue.", "archived", forgotten={"at": "x"})
    bulk = await _put(
        f"The owner's {word} bicycle is green.", "archived", archived_by="fresh_start_2026-10-23"
    )
    wrong = await _put(f"The owner's {word} scooter is grey.", "active")
    fixed = await _put(f"The owner's {word} scooter is black.", "active", correction=True)
    from sqlalchemy import text

    async with async_session() as s:
        await s.execute(
            text("UPDATE memories SET status = 'superseded', superseded_by = :n WHERE id = :o"),
            {"n": fixed.id, "o": wrong.id},
        )
        await s.commit()

    with tenant_scope(TENANT):
        found = await memory_tiers.search([0.01] * 1024, f"{word} bicycle scooter")
    ids = {m.id for m in found}
    assert old.id in ids and wrong.id in ids
    assert gone.id not in ids and bulk.id not in ids
    assert fixed.id not in ids  # active: warm, not cold
    replaced = next(m for m in found if m.id == wrong.id)
    assert memory_tiers.label(replaced).startswith("later corrected on ")
    assert memory_tiers.label(next(m for m in found if m.id == old.id)) == "older note"

    # Used to answer: the archived one is active again; the replaced one stays history.
    with tenant_scope(TENANT):
        assert await memory_tiers.reawaken(found) == 1
    back = await _row(old.id)
    assert back.status == "active"
    assert back.properties["reawakened"]["previous_status"] == "archived"
    assert (await _row(wrong.id)).status == "superseded"


@pytest.mark.asyncio
@skip_on_db_error
async def test_retrieve_falls_back_to_cold_and_follows_links(monkeypatch):
    from life_graph.api.dependencies import get_memory_manager
    from life_graph.core.tenant import tenant_scope
    from life_graph.services import associations, memory_retrieval

    tag = uuid.uuid4().hex[:6]
    word = f"quillback{tag}"
    cold = await _put(f"The owner's {word} locker code is 4471.", "archived")

    async def vector(text):
        return [0.01] * 1024

    monkeypatch.setattr(get_memory_manager(), "generate_embedding", vector)

    # Nothing active answers: the cold tier is read, and the archived note found.
    async def judge(question, contents):
        return [i for i, c in enumerate(contents) if "locker" in c]

    monkeypatch.setattr(memory_retrieval, "judge", judge)
    with tenant_scope(TENANT):
        got = await memory_retrieval.retrieve(f"What is my {word} locker code?")
    assert [m.id for m in got] == [cold.id]

    # A linked memory joins the candidates though search would not find it.
    hit = await _put(f"The owner's {word} gym is on 4th street.", "active")
    linked = await _put("Open from six in the morning.", "active")
    await associations.said_together(TENANT, [hit.id, linked.id])
    seen = []

    async def record(question, contents):
        seen.extend(contents)
        return list(range(len(contents)))

    monkeypatch.setattr(memory_retrieval, "judge", record)
    with tenant_scope(TENANT):
        got = await memory_retrieval.retrieve(f"Where is my {word} gym?")
    assert linked.content in seen
    assert linked.id in {m.id for m in got}


@pytest.mark.asyncio
@skip_on_db_error
async def test_form_fill_sets_slots_and_offers_same_slot_replacement(monkeypatch):
    from sqlalchemy import select

    from life_graph.models.db import Approval
    from life_graph.services import form_fill
    from life_graph.storage.database import async_session

    tenant = f"form_{uuid.uuid4().hex[:8]}"
    global TENANT
    saved, TENANT = TENANT, tenant
    try:
        older = await _put("The owner works at Nimbus Soft.", "active")
        newer = await _put("The owner works at Tessera Labs.", "active")
        pref = await _put("The owner prefers tea over coffee.", "active")
    finally:
        TENANT = saved

    async def slot_of(content):
        return "work.employer" if "works at" in content else None

    monkeypatch.setattr(form_fill, "ask_slot", slot_of)
    report = await form_fill.fill(tenant)
    assert report == {"checked": 3, "slotted": 2, "replacements_offered": 1}
    assert (await _row(older.id)).properties["slot"] == "work.employer"
    assert (await _row(newer.id)).properties["slot"] == "work.employer"
    assert (await _row(pref.id)).properties["slot_checked"] is True
    # Offered, not applied: both stay active until the owner keeps it.
    assert (await _row(older.id)).status == "active"
    async with async_session() as s:
        appr = (
            await s.execute(select(Approval).where(Approval.source_ref == f"{older.id}|{newer.id}"))
        ).scalar_one()
    assert appr.payload["applied"] is False

    # Nothing left to ask about the next night.
    assert await form_fill.fill(tenant) == {
        "checked": 0,
        "slotted": 0,
        "replacements_offered": 0,
    }
