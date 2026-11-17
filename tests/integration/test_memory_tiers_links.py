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
        got = await memory_retrieval.retrieve(f"What is my {word} locker code?", cold=True)
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
        got = await memory_retrieval.retrieve(f"Where is my {word} gym?", cold=True)
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

    async def slot_of(content, subject=None):
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


@pytest.mark.asyncio
@skip_on_db_error
async def test_review_fixes_for_the_cold_tier(monkeypatch):
    """Review 2026-10-31: /ask gets no unlabelled cold memories; a merged duplicate
    is not "later replaced"; what the owner archived does not wake up by itself."""
    from sqlalchemy import text

    from life_graph.api.dependencies import get_memory_manager
    from life_graph.core.tenant import tenant_scope
    from life_graph.services import memory_retrieval, memory_tiers
    from life_graph.storage.database import async_session

    tag = uuid.uuid4().hex[:6]
    word = f"marlinspike{tag}"
    cold = await _put(f"The owner's {word} tent is orange.", "archived")
    winner = await _put(f"The owner's {word} kayak is yellow.", "active")
    dup = await _put(
        f"The owner's {word} kayak is yellow!", "superseded", merged_into=str(winner.id)
    )
    mine = await _put(f"The owner's {word} sail is white.", "archived", archived_by="owner")
    async with async_session() as s:
        await s.execute(
            text("UPDATE memories SET superseded_by = :w WHERE id = :d"),
            {"w": winner.id, "d": dup.id},
        )
        await s.commit()

    async def vector(text_):
        return [0.01] * 1024

    async def keep_cold(question, contents):
        return [i for i, c in enumerate(contents) if "tent" in c]

    monkeypatch.setattr(get_memory_manager(), "generate_embedding", vector)
    monkeypatch.setattr(memory_retrieval, "judge", keep_cold)
    with tenant_scope(TENANT):
        # /ask and the dashboard chat: no cold tier.
        assert await memory_retrieval.retrieve(f"What colour is my {word} tent?") == []
        # The Jarvis block (labelled): the cold tier.
        got = await memory_retrieval.retrieve(f"What colour is my {word} tent?", cold=True)
        assert [m.id for m in got] == [cold.id]
        found = await memory_tiers.search([0.01] * 1024, f"{word} kayak tent sail")
    ids = {m.id for m in found}
    assert dup.id not in ids  # a duplicate, not an earlier value
    assert {cold.id, mine.id} <= ids
    with tenant_scope(TENANT):
        assert await memory_tiers.reawaken(found) == 1  # the decay-archived one only
    assert (await _row(cold.id)).status == "active"
    assert (await _row(mine.id)).status == "archived"


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_unjudged_answer_never_includes_cold_memories(monkeypatch):
    from life_graph.api.dependencies import get_memory_manager
    from life_graph.core.tenant import tenant_scope
    from life_graph.services import memory_retrieval

    word = f"gunwale{uuid.uuid4().hex[:6]}"
    warm = await _put(f"The owner's {word} job started in March.", "active")
    old = await _put(f"The owner's {word} job before was at a bank.", "archived")

    async def vector(text_):
        return [0.01] * 1024

    async def outage(question, contents):
        return None

    monkeypatch.setattr(get_memory_manager(), "generate_embedding", vector)
    monkeypatch.setattr(memory_retrieval, "judge", outage)
    with tenant_scope(TENANT):
        got = await memory_retrieval.retrieve(f"Where did I {word} work before?", cold=True)
    ids = [m.id for m in got]
    assert warm.id in ids and old.id not in ids


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_card_shows_the_newest_value_of_a_shared_slot():
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from life_graph.services import profile_card
    from life_graph.storage.database import async_session

    tenant = f"card_{uuid.uuid4().hex[:8]}"
    global TENANT
    saved, TENANT = TENANT, tenant
    try:
        old = await _put("The owner works at Infosys.", "active", slot="work.employer")
        new = await _put("The owner works at Zoho.", "active", slot="work.employer")
    finally:
        TENANT = saved
    async with async_session() as s:
        # The old one is more used and more important: it still must not win.
        await s.execute(
            text(
                "UPDATE memories SET created_at = :c, importance = 0.95, access_count = 40"
                " WHERE id = :id"
            ),
            {"c": datetime.now(UTC) - timedelta(days=400), "id": old.id},
        )
        await s.commit()
    profile_card.clear_cache()
    card = await profile_card.card_items(tenant)
    assert [c["content"] for c in card if c.get("slot") == "work.employer"] == [new.content]


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_old_decay_proposal_never_archives_a_form_fact():
    from life_graph.models.db import Approval
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    m = await _put("The owner lives in Coimbatore.", "active", slot="home.city")
    async with async_session() as s:
        appr = Approval(
            tenant_id=TENANT,
            kind="archive",
            title="Archive a decayed memory",
            payload={"memory_id": str(m.id)},
            source="decay",
            source_ref=f"decay:{m.id}",
        )
        s.add(appr)
        await s.commit()
        await ApprovalService(s)._apply_archive(TENANT, appr, True)
        await s.commit()
    assert (await _row(m.id)).status == "active"
