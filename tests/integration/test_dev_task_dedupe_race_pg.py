"""Two identical dev-task requests at the same moment make one task (audit L12).

Both used to pass the "already queued?" check before either row existed, so
both inserted. create_dev_task now takes a transaction advisory lock on the
dedupe key first. Against the real database, concurrent identical requests
must yield one row and point the rest at it.

Left alone, each call finishes before the next one has even connected, so
the race never shows. Every session therefore waits after its duplicate
lookup until all of them have looked (or a short timeout passes). Without
the lock all of them see "none yet" and insert. With it, the later ones are
still blocked on the lock, so the first gives up waiting, commits, and the
rest then find its row.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select

from tests.integration.conftest import skip_on_db_error

TENANT = f"dev_race_{uuid.uuid4().hex[:8]}"
N = 6


class _PauseAfterLookup:
    """An AsyncSession proxy that waits at a barrier after the lookup."""

    def __init__(self, session, barrier):
        self._s, self._barrier = session, barrier

    def __getattr__(self, name):
        return getattr(self._s, name)

    async def __aenter__(self):
        await self._s.__aenter__()
        return self

    async def __aexit__(self, *exc):
        return await self._s.__aexit__(*exc)

    async def execute(self, stmt, *a, **k):
        result = await self._s.execute(stmt, *a, **k)
        if "agent_tasks" in str(stmt):  # the duplicate lookup, not the lock
            with contextlib.suppress(TimeoutError, asyncio.BrokenBarrierError):
                await asyncio.wait_for(self._barrier.wait(), 0.5)
        return result


@pytest.mark.asyncio
@skip_on_db_error
async def test_concurrent_identical_requests_make_one_task(monkeypatch):
    from life_graph.api.dependencies import get_project_registry
    from life_graph.config import settings
    from life_graph.models.db import AgentTask
    from life_graph.services.dev.tasks import create_dev_task
    from life_graph.storage.database import async_session

    monkeypatch.setattr(settings, "tool_fs_roots", str(Path.cwd()))
    project = await get_project_registry().register(
        TENANT, {"name": f"proj-{uuid.uuid4().hex[:6]}", "path": str(Path.cwd())}
    )
    instruction = f"Fix the flaky thing {uuid.uuid4().hex[:6]}"
    barrier = asyncio.Barrier(N)

    def factory():
        return _PauseAfterLookup(async_session(), barrier)

    results = await asyncio.gather(
        *[
            create_dev_task(
                factory,
                TENANT,
                instruction=instruction,
                project=project,
                persona_name=None,
                start=False,
            )
            for _ in range(N)
        ]
    )

    async with async_session() as s:
        rows = await s.scalar(
            select(func.count()).where(
                AgentTask.tenant_id == TENANT,
                AgentTask.project_id == uuid.UUID(project["id"]),
            )
        )
    assert rows == 1
    created = [r for r in results if "duplicate_of" not in r]
    assert len(created) == 1
    assert {r["id"] for r in results} == {created[0]["id"]}
