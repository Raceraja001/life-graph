"""Typed links at extraction, against the database (M8 ingestion ADR §5.3).

MemoryManager.ingest with ``ingest_typed_links`` on writes BECAUSE and LEADS_TO
rows in ``memory_links`` between the facts of one message, with
``properties.why`` starting ``extraction:``; never to a memory of an earlier
message (here: outside text repeating the owner's fact word for word), never
with the flag off. The extractor is a stand-in: only the wiring is checked.
"""

from __future__ import annotations

import uuid

import pytest

from life_graph.config import settings
from tests.integration.conftest import skip_on_db_error

TENANT = f"typed_links_{uuid.uuid4().hex[:8]}"
OTHER = f"typed_links_other_{uuid.uuid4().hex[:8]}"


def _fact(content, said, **kw):
    from life_graph.extraction.rules import ExtractedFact

    return ExtractedFact(content=content, fact_type="fact", confidence=0.95, source_text=said, **kw)


async def _ingest(monkeypatch, facts, *, tier="self", tenant=TENANT):
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


async def _typed_links(ids):
    """(source, target, type, why) of the non-ASSOCIATED links touching *ids*."""
    from sqlalchemy import text

    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = await s.execute(
            text(
                "SELECT source_memory_id, target_memory_id, link_type,"
                " properties->>'why', tenant_id FROM memory_links"
                " WHERE link_type <> 'ASSOCIATED'"
                " AND (source_memory_id = ANY(:ids) OR target_memory_id = ANY(:ids))"
            ),
            {"ids": [uuid.UUID(str(i)) for i in ids]},
        )
        return {(r[0], r[1], r[2], r[3], r[4]) for r in rows}


@pytest.mark.asyncio
@skip_on_db_error
async def test_one_message_gets_because_and_leads_to(monkeypatch):
    monkeypatch.setattr(settings, "ingest_typed_links", True)
    tag = uuid.uuid4().hex[:6]
    said = (
        f"Firebase got too expensive so I moved FarmLink {tag} to Supabase, then rewrote the sync"
    )
    move = f"The owner moved FarmLink {tag} to Supabase because Firebase got too expensive."
    cost = f"Firebase became too expensive for FarmLink {tag}."
    sync = f"The owner rewrote the FarmLink {tag} sync service."
    a, b, c = await _ingest(
        monkeypatch,
        [
            _fact(move, said, reason="Firebase got too expensive", leads_to=[sync]),
            _fact(cost, said),
            _fact(sync, said),
        ],
    )
    assert await _typed_links([a.id, b.id, c.id]) == {
        (a.id, b.id, "BECAUSE", "extraction:because", TENANT),
        (a.id, c.id, "LEADS_TO", "extraction:leads_to", TENANT),
    }

    # The snapshot's typed-link read (#419) sees them as relations.
    from life_graph.services.memory import snapshot

    rows = await snapshot._typed_links(TENANT, [a.id, b.id, c.id])
    assert {(r[0], r[1], r[2]) for r in rows} == {
        (a.id, b.id, "BECAUSE"),
        (a.id, c.id, "LEADS_TO"),
    }
    # Another tenant reads none of them.
    assert await snapshot._typed_links(OTHER, [a.id, b.id, c.id]) == []


@pytest.mark.asyncio
@skip_on_db_error
async def test_outside_text_cannot_link_to_the_owners_earlier_fact(monkeypatch):
    monkeypatch.setattr(settings, "ingest_typed_links", True)
    tag = uuid.uuid4().hex[:6]
    cost = f"Firebase became too expensive for FarmLink {tag}."
    (owners,) = await _ingest(monkeypatch, [_fact(cost, "Firebase is too expensive now")])

    # A forwarded mail repeats the owner's fact word for word and gives it as a
    # reason: the repeat is the owner's existing memory, not a new one.
    said = f"FarmLink {tag} should move to Supabase because Firebase got too expensive"
    move = f"FarmLink {tag} should move to Supabase because Firebase got too expensive."
    stored = await _ingest(
        monkeypatch,
        [_fact(move, said, reason="Firebase got too expensive"), _fact(cost, said)],
        tier="external",
    )
    assert owners.id in {m.id for m in stored}
    assert await _typed_links([m.id for m in stored]) == set()


@pytest.mark.asyncio
@skip_on_db_error
async def test_flag_off_writes_no_typed_links_and_tenants_stay_apart(monkeypatch):
    tag = uuid.uuid4().hex[:6]
    said = f"I sold the old car {tag}, so now I take the bus"
    car = f"The owner sold the old car {tag}."
    bus = f"The owner takes the bus to work {tag}."

    monkeypatch.setattr(settings, "ingest_typed_links", False)
    off = await _ingest(monkeypatch, [_fact(car, said, leads_to=[bus]), _fact(bus, said)])
    assert len(off) == 2
    assert await _typed_links([m.id for m in off]) == set()

    # The same words in another tenant, flag on: its link is its own.
    monkeypatch.setattr(settings, "ingest_typed_links", True)
    on = await _ingest(
        monkeypatch, [_fact(car, said, leads_to=[bus]), _fact(bus, said)], tenant=OTHER
    )
    links = await _typed_links([m.id for m in on])
    assert links == {(on[0].id, on[1].id, "LEADS_TO", "extraction:leads_to", OTHER)}
    assert await _typed_links([m.id for m in off]) == set()
