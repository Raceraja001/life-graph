"""Rejecting a pending memory deletes its links (M8 ADR §5.3).

``ApprovalService.on_memory_rejected`` used to close only the contradiction
items, so a link to or from a rejected memory stayed in ``memory_links`` and
graph views, ``get_links`` and search expansion could still reach it. It now
deletes every link of that tenant where the memory is either end, and only
while the memory is that tenant's and rejected.
"""

from __future__ import annotations

import uuid

from life_graph.services.approvals import ApprovalService
from life_graph.services.memory import links
from tests.unit.fakes import FakeResult, FakeSession, sql


async def test_helper_deletes_both_ends_in_this_tenant_only():
    session = FakeSession(FakeResult(rowcount=3))
    memory_id = uuid.uuid4()

    assert await links.delete_links_of_rejected_memory(session, memory_id, "tenant-a") == 3

    (stmt,) = session.statements
    text = sql(stmt)
    assert text.startswith("DELETE FROM memory_links")
    assert "memory_links.tenant_id = 'tenant-a'" in text
    assert "memory_links.source_memory_id = " in text
    assert "memory_links.target_memory_id = " in text
    # The memory itself must be this tenant's and rejected.
    assert "memories.tenant_id = 'tenant-a'" in text
    assert "memories.status = 'rejected'" in text
    assert str(memory_id) in text
    assert session.commits == 0  # the reject path commits it


async def test_helper_reads_no_rowcount_as_zero():
    result = FakeResult()
    result.rowcount = None
    assert await links.delete_links_of_rejected_memory(FakeSession(result), uuid.uuid4(), "t") == 0


async def test_on_memory_rejected_deletes_the_links_of_that_memory():
    memory_id = uuid.uuid4()
    # 1st execute: the pending contradiction items (none); 2nd: the link delete.
    session = FakeSession(FakeResult([]), FakeResult(rowcount=2))

    closed = await ApprovalService(session).on_memory_rejected("tenant-r", str(memory_id))

    assert closed == 0
    assert len(session.statements) == 2
    text = sql(session.statements[1])
    assert text.startswith("DELETE FROM memory_links")
    assert "'tenant-r'" in text
    assert str(memory_id) in text


async def test_on_memory_approved_deletes_no_links():
    session = FakeSession(FakeResult([]))
    await ApprovalService(session).on_memory_approved("tenant-r", str(uuid.uuid4()))
    assert not any(sql(s).startswith("DELETE") for s in session.statements)
