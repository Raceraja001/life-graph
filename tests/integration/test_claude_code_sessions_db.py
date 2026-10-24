"""Claude Code memory sessions against the real database.

The unit half (tests/unit/test_claude_code_sessions.py) inspects compiled
statements; this half runs them: the upsert makes one tenant-scoped row per
Claude Code session, a memory carrying its id is linked, a SessionEnd request
plus the closer ends and summarises it, and a session that carries on after
that continues in part 2.

Every call that sweeps is scoped to this file's own tenant
(``close_due(tenant_id=...)``): the database is shared, and an unscoped sweep
with a future ``now`` would close everyone's open sessions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.core.tenant import tenant_scope
from tests.integration.conftest import skip_on_db_error

TENANT = f"ccs_{uuid.uuid4().hex[:8]}"
OTHER = f"ccs_other_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """No model and no background consolidation: both are exercised elsewhere."""
    from life_graph.api import sessions as sessions_api

    lm = SimpleNamespace(
        chat=AsyncMock(side_effect=AssertionError("cloud-capable chat must not be used")),
        chat_local_only=AsyncMock(return_value="Worked on the memory layer."),
    )
    monkeypatch.setattr("life_graph.api.dependencies.get_lm_client", lambda: lm)
    monkeypatch.setattr(sessions_api, "_run_micro_consolidation", AsyncMock())
    return lm


async def _row(session_id: uuid.UUID):
    from life_graph.models.db import Session
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Session, session_id)


async def _links(session_id: uuid.UUID) -> dict[uuid.UUID, str]:
    from sqlalchemy import select

    from life_graph.models.db import MemorySession
    from life_graph.storage.database import async_session

    async with async_session() as s:
        rows = await s.execute(
            select(MemorySession.memory_id, MemorySession.role).where(
                MemorySession.session_id == session_id
            )
        )
        return dict(rows.all())


@pytest.mark.asyncio
@skip_on_db_error
async def test_one_row_per_session_scoped_to_the_tenant():
    from life_graph.services import claude_code_sessions as ccs

    cc = f"cc-{uuid.uuid4().hex[:8]}"
    first = await ccs.ensure_session(TENANT, cc, project="life-graph", cwd="/w/life-graph")
    again = await ccs.ensure_session(TENANT, cc, project="life-graph")
    theirs = await ccs.ensure_session(OTHER, cc)

    assert first == again == ccs.memory_session_id(TENANT, cc)
    assert theirs != first
    row = await _row(first)
    assert row.tenant_id == TENANT
    assert row.ended_at is None
    assert row.context["source"] == "claude_code"
    assert row.context["claude_code_session_id"] == cc
    assert row.context["project"] == "life-graph"
    assert row.context["part"] == 1
    assert row.context["last_seen_at"]
    assert (await _row(theirs)).tenant_id == OTHER


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_memory_with_its_id_is_linked_as_created():
    from life_graph.models.schemas import MemoryCreate
    from life_graph.services import claude_code_sessions as ccs
    from life_graph.storage.postgres import PostgresMemoryStore

    cc = f"cc-{uuid.uuid4().hex[:8]}"
    sid = await ccs.ensure_session(TENANT, cc)
    with tenant_scope(TENANT):
        row = await PostgresMemoryStore().store(
            MemoryCreate(
                content=f"Uses pgvector {uuid.uuid4().hex[:6]}",
                properties={"session_id": str(sid), "claude_code_session_id": cc},
            ),
            status="active",
        )
    assert await _links(sid) == {row.id: "created"}
    assert (await _row(sid)).memories_created == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_end_request_then_close_then_part_two(_offline):
    from life_graph.models.schemas import MemoryCreate
    from life_graph.services import claude_code_sessions as ccs
    from life_graph.storage.postgres import PostgresMemoryStore

    cc = f"cc-{uuid.uuid4().hex[:8]}"
    sid = await ccs.ensure_session(TENANT, cc, project="life-graph")
    with tenant_scope(TENANT):
        await PostgresMemoryStore().store(
            MemoryCreate(
                content=f"Chose uuid5 {uuid.uuid4().hex[:6]}", properties={"session_id": str(sid)}
            ),
            status="active",
        )

    # Not due yet: the end was asked for just now.
    assert await ccs.request_end(TENANT, cc, "clear") is True
    assert await ccs.close_due(tenant_id=TENANT) == []

    later = datetime.now(UTC) + timedelta(minutes=30)
    assert await ccs.close_due(later, tenant_id=TENANT) == [sid]
    row = await _row(sid)
    assert row.ended_at is not None
    assert row.summary == "Worked on the memory layer."
    assert row.memories_created == 1
    _offline.chat_local_only.assert_awaited()
    _offline.chat.assert_not_awaited()

    # The session goes on (resumed): a new memory session, not a lost link.
    part_two = await ccs.ensure_session(TENANT, cc)
    assert part_two == ccs.memory_session_id(TENANT, cc, 2)
    assert (await _row(part_two)).context["part"] == 2


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_idle_session_is_closed_without_an_end_request():
    from life_graph.services import claude_code_sessions as ccs

    cc = f"cc-{uuid.uuid4().hex[:8]}"
    sid = await ccs.ensure_session(TENANT, cc)

    assert sid not in await ccs.close_due(tenant_id=TENANT)
    far = datetime.now(UTC) + timedelta(days=2)
    assert sid in await ccs.close_due(far, tenant_id=TENANT)
    assert (await _row(sid)).ended_at is not None


@pytest.mark.asyncio
@skip_on_db_error
async def test_an_end_request_never_reaches_another_tenant():
    from life_graph.services import claude_code_sessions as ccs

    cc = f"cc-{uuid.uuid4().hex[:8]}"
    theirs = await ccs.ensure_session(OTHER, cc)

    assert await ccs.request_end(TENANT, cc, "clear") is False
    assert "end_requested_at" not in (await _row(theirs)).context
