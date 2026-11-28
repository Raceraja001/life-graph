"""services/memory/supersession.py against Postgres: a supersede and its undo
land in one tenant-scoped transaction, and another tenant's row is never
written (ADR M8 §5.2, step 4)."""

from __future__ import annotations

import hashlib
import uuid

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"supx_{uuid.uuid4().hex[:8]}"
OTHER = f"supy_{uuid.uuid4().hex[:8]}"


async def _seed(tenant: str, content: str, **props) -> str:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
            importance=0.6,
            tags=["test"],
            status="active",
            trust_tier="self",
            source_type="test",
            properties=props,
        )
        s.add(m)
        await s.commit()
        return str(m.id)


async def _memory(mem_id: str):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, uuid.UUID(mem_id))


@skip_on_db_error
async def test_apply_then_undo_round_trip_in_the_database():
    from life_graph.services.memory import supersession
    from life_graph.storage.database import async_session

    old_id = await _seed(TENANT, "quillon lives in Chennai", slot="home.city")
    new_id = await _seed(TENANT, "quillon lives in Mumbai", slot="home.city")

    async with async_session() as s:
        old, new = await supersession.load(s, TENANT, old_id, new_id, lock=True)
        assert supersession.apply(TENANT, old, new, why="test")
        await s.commit()
    old, new = await _memory(old_id), await _memory(new_id)
    assert old.status == "superseded" and str(old.superseded_by) == new_id
    assert str(new.supersedes) == old_id
    assert old.properties["slot"] == "home.city" and old.properties["superseded_at"]
    assert old.valid_until is None

    async with async_session() as s:
        old, new = await supersession.load(s, TENANT, old_id, new_id)
        assert supersession.undo(TENANT, old, new)
        await s.commit()
    old, new = await _memory(old_id), await _memory(new_id)
    assert old.status == "active" and old.superseded_by is None
    assert new.supersedes is None
    assert old.properties == {"slot": "home.city"}


@skip_on_db_error
async def test_load_never_returns_another_tenants_row():
    from life_graph.services.memory import supersession
    from life_graph.storage.database import async_session

    mine = await _seed(TENANT, "quillon mine")
    theirs = await _seed(OTHER, "quillon theirs")
    async with async_session() as s:
        old, new = await supersession.load(s, TENANT, theirs, mine)
        assert old is None and str(new.id) == mine
        assert not supersession.apply(TENANT, old, new, why="test")
        old, new = await supersession.load(s, TENANT, "not-a-uuid", mine)
        assert old is None


@skip_on_db_error
async def test_a_correction_never_points_at_another_tenants_memory():
    from life_graph.tools.memory_search import _supersede

    mine = await _seed(TENANT, "quillon corrected from")
    theirs = await _seed(OTHER, "quillon other tenant")

    assert await _supersede(TENANT, uuid.UUID(theirs), uuid.UUID(mine)) is None
    assert await _supersede(TENANT, uuid.UUID(mine), uuid.UUID(theirs)) is None
    m, t = await _memory(mine), await _memory(theirs)
    assert m.status == "active" and m.superseded_by is None and m.supersedes is None
    assert t.status == "active" and t.superseded_by is None and t.supersedes is None


@skip_on_db_error
async def test_memory_manager_refuses_another_tenants_rows():
    from life_graph.core.memory_manager import MemoryManager
    from life_graph.core.tenant import tenant_scope
    from life_graph.storage.postgres import PostgresMemoryStore

    mine = await _seed(TENANT, "quillon manager mine")
    theirs = await _seed(OTHER, "quillon manager theirs")
    mgr = MemoryManager(
        store=PostgresMemoryStore(), extractor=None, tagger=None, contradiction_detector=None
    )
    with tenant_scope(TENANT):
        # The old memory not this tenant's: ValueError, as store.update raised.
        with pytest.raises(ValueError, match="not found"):
            await mgr.supersede(theirs, mine, "test")
        # The new one not this tenant's: nothing is written.
        await mgr.supersede(mine, theirs, "test")
    m, t = await _memory(mine), await _memory(theirs)
    assert m.status == "active" and m.superseded_by is None
    assert t.status == "active" and t.supersedes is None


@skip_on_db_error
async def test_restore_replaced_by_keeps_merged_duplicates_and_other_tenants():
    from sqlalchemy import update

    from life_graph.models.db import Memory
    from life_graph.services.memory import supersession
    from life_graph.storage.database import async_session

    new_id = await _seed(TENANT, "quillon the saved one")
    replaced = await _seed(TENANT, "quillon the replaced one")
    merged = await _seed(TENANT, "quillon the merged one", merged_into=new_id)
    async with async_session() as s:
        for mid in (replaced, merged):
            await s.execute(
                update(Memory)
                .where(Memory.id == uuid.UUID(mid))
                .values(status="superseded", superseded_by=uuid.UUID(new_id))
            )
        await s.commit()

    async with async_session() as s:
        await supersession.restore_replaced_by(s, OTHER, uuid.UUID(new_id))
        await s.commit()
    assert (await _memory(replaced)).status == "superseded"

    async with async_session() as s:
        await supersession.restore_replaced_by(s, TENANT, uuid.UUID(new_id))
        await s.commit()
    assert (await _memory(replaced)).status == "active"
    assert (await _memory(merged)).status == "superseded"
