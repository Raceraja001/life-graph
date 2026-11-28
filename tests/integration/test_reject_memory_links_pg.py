"""Rejecting a memory deletes its links, against the database (M8 ADR §5.3).

The reject path (services/memory/transitions.py -> ApprovalService.on_memory_rejected)
deletes every link of the tenant where the rejected memory is either end, of
any type. Another tenant's link rows are untouched, a link between two other
memories stays, and a denied memory (``/deny``: true once, now superseded)
keeps its links.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from sqlalchemy import or_, select

from tests.integration.conftest import skip_on_db_error

pytestmark = pytest.mark.asyncio


async def _seed(tenant: str, content: str, status: str = "active") -> uuid.UUID:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{content}{uuid.uuid4()}".encode()).hexdigest(),
            importance=0.5,
            tags=["test"],
            status=status,
            trust_tier="verified",
            source_type="test",
        )
        s.add(m)
        await s.commit()
        return m.id


async def _raw_link(tenant: str, source: uuid.UUID, target: uuid.UUID, kind: str) -> None:
    """A link row written straight to the table (no tenant check), like an old row."""
    from life_graph.models.db import MemoryLink
    from life_graph.storage.database import async_session

    async with async_session() as s:
        s.add(
            MemoryLink(
                source_memory_id=source,
                target_memory_id=target,
                link_type=kind,
                strength=0.5,
                properties={},
                tenant_id=tenant,
            )
        )
        await s.commit()


async def _links(memory_id: uuid.UUID) -> set[tuple]:
    from life_graph.models.db import MemoryLink
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = await s.execute(
            select(
                MemoryLink.source_memory_id,
                MemoryLink.target_memory_id,
                MemoryLink.link_type,
                MemoryLink.tenant_id,
            ).where(
                or_(
                    MemoryLink.source_memory_id == memory_id,
                    MemoryLink.target_memory_id == memory_id,
                )
            )
        )
        return {tuple(r) for r in rows}


@skip_on_db_error
async def test_reject_deletes_links_other_tenant_and_deny_keep_theirs():
    from life_graph.core.tenant import tenant_scope
    from life_graph.services.memory import links
    from life_graph.services.memory.transitions import transition
    from life_graph.storage.postgres import PostgresMemoryStore

    run = uuid.uuid4().hex[:8]
    a, b = f"rejlinks_a_{run}", f"rejlinks_b_{run}"
    pending = await _seed(a, f"A pending fact {run}", status="pending")
    a1 = await _seed(a, f"A first fact {run}")
    a2 = await _seed(a, f"A second fact {run}")
    denied = await _seed(a, f"A fact that stops being true {run}")
    b1 = await _seed(b, f"B fact {run}")
    b2 = await _seed(b, f"B other fact {run}")

    # Links of the pending memory, both directions, two kinds.
    await links.create_link(
        pending, a1, "BECAUSE", properties={"why": "extraction:because"}, tenant_id=a
    )
    await links.create_link(a2, pending, "RELATED_TO", tenant_id=a)
    # A link between two other memories of A, and one of B.
    await links.create_link(a1, a2, "LEADS_TO", tenant_id=a)
    await links.create_link(b1, b2, "RELATED_TO", tenant_id=b)
    # A row of tenant B that touches A's memory (as old rows could): B's, so it stays.
    await _raw_link(b, b1, pending, "RELATED_TO")
    # The denied memory's link.
    await links.create_link(denied, a1, "BECAUSE", tenant_id=a)

    store = PostgresMemoryStore()
    with tenant_scope(a):
        row = await transition(pending, "reject", store)
        assert row.status == "rejected"
        old, _new = await store.deny(denied)
        assert old.status == "superseded"

    # Every A link of the rejected memory is gone; B's row touching it stays.
    assert await _links(pending) == {(b1, pending, "RELATED_TO", b)}
    # The link between A's other two memories stays.
    assert (a1, a2, "LEADS_TO", a) in await _links(a1)
    # B's own link is untouched.
    assert await _links(b2) == {(b1, b2, "RELATED_TO", b)}
    # A deny keeps its links: the fact was true once.
    assert await _links(denied) == {(denied, a1, "BECAUSE", a)}


@skip_on_db_error
async def test_helper_never_touches_a_memory_of_another_tenant_or_not_rejected():
    from life_graph.services.memory import links
    from life_graph.storage.database import async_session

    run = uuid.uuid4().hex[:8]
    a, b = f"rejlinks2_a_{run}", f"rejlinks2_b_{run}"
    b_rejected = await _seed(b, f"B rejected fact {run}", status="rejected")
    b_other = await _seed(b, f"B fact {run}")
    a_active = await _seed(a, f"A active fact {run}")
    a_other = await _seed(a, f"A other fact {run}")
    await links.create_link(b_rejected, b_other, "RELATED_TO", tenant_id=b)
    await links.create_link(a_active, a_other, "RELATED_TO", tenant_id=a)

    async with async_session() as s:
        # Named with the wrong tenant: B's memory loses nothing.
        assert await links.delete_links_of_rejected_memory(s, b_rejected, a) == 0
        # A memory that is not rejected loses nothing.
        assert await links.delete_links_of_rejected_memory(s, a_active, a) == 0
        await s.commit()

    assert await _links(b_rejected) == {(b_rejected, b_other, "RELATED_TO", b)}
    assert await _links(a_active) == {(a_active, a_other, "RELATED_TO", a)}
