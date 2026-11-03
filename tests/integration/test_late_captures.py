"""A capture delivered late is stored as said then, not now (core/said_at.py, 2026-11-03).

The Claude Code hook's queue delivered 2,844 captures at once on 2026-11-02, the
oldest from 13 Oct. Dated on arrival, an old "I live in Madurai" would have
replaced a newer "I live in Coimbatore". The extractor is a stand-in here, as in
test_memory_slots.py; only the storage rules are checked.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"late_{uuid.uuid4().hex[:8]}"


def _fact(content, slot):
    from life_graph.extraction.rules import ExtractedFact

    return ExtractedFact(content=content, fact_type="fact", confidence=0.95, slot=slot)


async def _ingest(monkeypatch, fact, *, said=None):
    from life_graph.api.dependencies import get_memory_manager
    from life_graph.core.said_at import said_at
    from life_graph.core.tenant import tenant_scope

    manager = get_memory_manager()

    class _Result:
        facts = [fact]

    async def fake_extract(text, capture=False):
        return _Result()

    async def no_embedding(text):
        return None

    monkeypatch.setattr(manager._extractor, "extract", fake_extract)
    monkeypatch.setattr(manager, "_generate_embedding", no_embedding)
    token = said_at.set(said)
    try:
        with tenant_scope(TENANT):
            (stored,) = await manager.ingest("…", source="capture", trust_tier="self", capture=True)
    finally:
        said_at.reset(token)
    return stored


async def _row(mid):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(str(mid)))


async def _backdate(mid, at):
    from sqlalchemy import update

    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        await s.execute(update(Memory).where(Memory.id == mid).values(created_at=at, updated_at=at))
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_late_old_value_is_history_of_the_newer_one(monkeypatch):
    tag = uuid.uuid4().hex[:6]
    now_value = await _ingest(
        monkeypatch, _fact(f"The owner lives in Coimbatore ({tag}).", "home.city")
    )
    said = datetime.now(UTC) - timedelta(days=10)
    old_value = await _ingest(
        monkeypatch, _fact(f"The owner lives in Madurai ({tag}).", "home.city"), said=said
    )

    current, late = await _row(now_value.id), await _row(old_value.id)
    assert current.status == "active" and current.superseded_by is None
    assert late.status == "superseded" and str(late.superseded_by) == str(now_value.id)
    assert abs((late.created_at - said).total_seconds()) < 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_late_value_still_replaces_an_older_one(monkeypatch):
    tag = uuid.uuid4().hex[:6]
    oldest = await _ingest(
        monkeypatch, _fact(f"The owner works at Nimbus Soft ({tag}).", "work.employer")
    )
    await _backdate(oldest.id, datetime.now(UTC) - timedelta(days=30))
    said = datetime.now(UTC) - timedelta(days=10)
    newer = await _ingest(
        monkeypatch, _fact(f"The owner works at Tessera Labs ({tag}).", "work.employer"), said=said
    )

    was, now_ = await _row(oldest.id), await _row(newer.id)
    assert was.status == "superseded" and str(was.superseded_by) == str(newer.id)
    assert now_.status == "active"
    assert abs((now_.created_at - said).total_seconds()) < 1
