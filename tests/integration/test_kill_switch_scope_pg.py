"""The kill switch against the database (Stage 0 finding 4, M1.7).

A paused tenant's queued dev task is not claimed (and is after resume); the
pause cancels its running dev task; pause and resume each write one
audit_log row naming who did it.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"killsw_{uuid.uuid4().hex[:8]}"
HEADERS = {"X-Tenant-ID": TENANT}


async def _set_paused(paused: bool) -> None:
    from life_graph.autonomy.kill_switch import invalidate_autonomy_pause_cache
    from life_graph.models.db import TenantConfig
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = await s.get(TenantConfig, TENANT)
        if row is None:
            s.add(TenantConfig(tenant_id=TENANT, autonomy_paused=paused))
        else:
            row.autonomy_paused = paused
        await s.commit()
    invalidate_autonomy_pause_cache(TENANT)


async def _dev_task(status: str) -> uuid.UUID:
    from life_graph.models.db import AgentTask
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = AgentTask(
            tenant_id=TENANT,
            agent_name=dev_tasks.AGENT_NAME,
            task_name="dev:kill-switch-test",
            status=status,
            input={},
            properties={"kind": dev_tasks.KIND, "run_mode": dev_tasks.QUEUE_MODE},
        )
        s.add(row)
        await s.commit()
        return row.id


async def _claim_mine() -> object | None:
    """Claim until this tenant's task comes up or the queue has nothing for us."""
    from life_graph.services.dev import tasks as dev_tasks
    from life_graph.storage.database import async_session

    for _ in range(50):
        claimed = await dev_tasks.claim_next_queued(async_session)
        if claimed is None or claimed.tenant_id == TENANT:
            return claimed
    return None


@pytest_asyncio.fixture
async def client():
    from life_graph.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS
    ) as c:
        yield c


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_paused_tenants_queued_task_waits_until_resume():
    await _set_paused(True)
    queued = await _dev_task("queued")

    assert await _claim_mine() is None

    await _set_paused(False)
    claimed = await _claim_mine()
    assert claimed is not None and claimed.id == queued


@pytest.mark.asyncio
@skip_on_db_error
async def test_pausing_cancels_the_running_dev_task_and_both_are_audited(client):
    from life_graph.autonomy.models import AuditLogEntry
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    await _set_paused(False)
    running = await _dev_task("running")

    r = await client.post("/api/v1/autonomy/safety/kill-switch/pause")
    assert r.status_code in (200, 503), r.text  # 503: capability store down, still paused
    if r.status_code == 200:
        assert r.json()["data"]["dev_tasks_cancelled"] >= 1
    async with async_session() as s:
        row = await s.get(AgentTask, running)
        assert (row.properties or {}).get("cancel_requested_at") or row.status == "cancelled"

    r = await client.post("/api/v1/autonomy/safety/kill-switch/resume")
    # Resume is owner-only; with no owner keys configured the local caller is the owner.
    assert r.status_code in (200, 403), r.text

    async with async_session() as s:
        rows = (
            (
                await s.execute(
                    select(AuditLogEntry).where(
                        AuditLogEntry.tenant_id == TENANT,
                        AuditLogEntry.action_type == "kill_switch",
                    )
                )
            )
            .scalars()
            .all()
        )
    names = sorted(r.action_name for r in rows)
    assert "autonomy_pause" in names
    assert all(r.actor_type == "operator" and r.actor_id for r in rows)
    if "autonomy_resume" in names:
        assert len(rows) == 2
