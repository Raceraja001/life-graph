"""The owner's form against the database (core/slots.py, core/memory_manager.py, 2026-10-31).

A new firm value for a slot replaces the old one at once, undoably, and the old
one becomes history; anything not firm or not the owner's own waits for review.
The extractor is replaced by a stand-in: the model is measured by the bake-off
and eval_extraction_meaning.py, here only the wiring is checked.
"""

from __future__ import annotations

import uuid

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"slots_{uuid.uuid4().hex[:8]}"


def _fact(content, slot, **kw):
    from life_graph.extraction.rules import ExtractedFact

    return ExtractedFact(content=content, fact_type="fact", confidence=0.95, slot=slot, **kw)


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


async def _row(mid):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(str(mid)))


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_new_firm_value_replaces_the_old_one_and_can_be_undone(monkeypatch):
    from sqlalchemy import select

    from life_graph.models.db import Approval
    from life_graph.services import profile_card
    from life_graph.services.approvals import ApprovalService
    from life_graph.storage.database import async_session

    tag = uuid.uuid4().hex[:6]
    (old,) = await _ingest(
        monkeypatch, [_fact(f"The owner works at Nimbus Soft ({tag}).", "work.employer")]
    )
    assert (await _row(old.id)).status == "active"
    (new,) = await _ingest(
        monkeypatch, [_fact(f"The owner works at Tessera Labs ({tag}).", "work.employer")]
    )
    assert (await _row(new.id)).status == "active"
    was = await _row(old.id)
    assert was.status == "superseded" and str(was.superseded_by) == str(new.id)

    # The form shows the new value; the history the old one.
    profile_card.clear_cache()
    card = await profile_card.card_items(TENANT)
    assert [c["content"] for c in card if c.get("slot") == "work.employer"] == [new.content]
    assert [h["content"] for h in await profile_card.history(TENANT)][:1] == [old.content]

    # Undo: rejecting the approval brings the old value back.
    async with async_session() as s:
        appr = (
            await s.execute(select(Approval).where(Approval.source_ref == f"{old.id}|{new.id}"))
        ).scalar_one()
        assert appr.payload["applied"] is True
        await ApprovalService(s).resolve(TENANT, str(appr.id), "reject")
        await s.commit()
    assert (await _row(old.id)).status == "active"


@pytest.mark.asyncio
@skip_on_db_error
async def test_outside_text_never_replaces_a_form_value(monkeypatch):
    tag = uuid.uuid4().hex[:6]
    (mine,) = await _ingest(
        monkeypatch, [_fact(f"The owner's phone is a Pixel 9 ({tag}).", "devices.phone")]
    )
    (theirs,) = await _ingest(
        monkeypatch,
        [_fact(f"The owner's phone is an iPhone 16 ({tag}).", "devices.phone")],
        tier="external",
    )
    # Over MCP/API: waits for review, replaces nothing until the owner keeps it.
    assert (await _row(theirs.id)).status == "pending"
    assert (await _row(mine.id)).status == "active"


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_changed_hobby_day_replaces_an_older_spelling(monkeypatch):
    # 2026-10-31: hobbies.cricket_day then hobbies.cricket.day both stayed current.
    from life_graph.services import profile_card

    tag = uuid.uuid4().hex[:6]
    (old,) = await _ingest(
        monkeypatch,
        [_fact(f"The owner plays cricket every Sunday ({tag}).", "hobbies.cricket_day")],
    )
    (new,) = await _ingest(
        monkeypatch,
        [_fact(f"The owner plays cricket on Saturdays now ({tag}).", "hobbies.cricket.day")],
    )
    was = await _row(old.id)
    assert was.status == "superseded" and str(was.superseded_by) == str(new.id)
    profile_card.clear_cache()
    card = [c["content"] for c in await profile_card.card_items(TENANT) if tag in c["content"]]
    assert card == [new.content]
