"""What a Jarvis run saved, read from the real database (services/saved_by_tool.py).

The unit tests cover the logic with fakes; this checks the JSONB task_id
lookup, tenant scoping, and that a save the owner undid still counts, so the
extractor's reworded copy of it is dropped (seen live 2026-10-25).
"""

from __future__ import annotations

import hashlib
import uuid

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"sbt_{uuid.uuid4().hex[:8]}"


async def _seed(content, *, status, props, tenant=TENANT):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=tenant,
            content_hash=hashlib.sha256(f"{tenant}{content}{uuid.uuid4()}".encode()).hexdigest(),
            status=status,
            trust_tier="self",
            source_type="explicit",
            properties=props,
        )
        s.add(m)
        await s.commit()
        return m.id


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_runs_saves_include_one_the_owner_undid_and_nothing_else():
    from life_graph.services.saved_by_tool import _saved_in

    run = uuid.uuid4()
    mine = {"saved_by": "jarvis", "task_id": str(run)}
    kept = await _seed("My locker is 55.", status="active", props=mine)
    undone = await _seed(
        "My bike is red.", status="archived", props={**mine, "undone": {"by": "owner"}}
    )
    await _seed("Forgotten later.", status="archived", props={**mine, "forgotten": {}})
    await _seed("Another run.", status="active", props={"task_id": str(uuid.uuid4())})
    await _seed("Their save.", status="active", props=mine, tenant="other_" + TENANT)

    saved = await _saved_in(run, TENANT)
    assert sorted(s.id for s in saved) == sorted([kept, undone])
