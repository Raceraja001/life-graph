"""NotificationEngine.check_stale_critical against a real database.

The method referenced three columns that do not exist — ``WatchEvent
.acknowledged`` and ``WatchEvent.retry_count`` (twice). Acknowledgement is
``acknowledged_at``; the retry counter lives on WatcherNotification, which is
where deliveries are tracked. Nothing calls this method, so nothing raised.

These run against Postgres deliberately. The bug that survived the rewrite —
``WatchEvent.details`` is JSONB and may hold a dict, while the notification
body is a Text column — only appears at insert time, as an asyncpg DataError.
A mocked session would have passed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from life_graph.storage.database import async_session
from life_graph.watchers.models import WatcherNotification, WatcherRun, WatchEvent
from life_graph.watchers.notification_engine import NotificationEngine
from tests.integration.conftest import skip_on_db_error

MAX_RETRIES = 3


@pytest_asyncio.fixture
async def tenant():
    tid = f"stale-critical-{uuid.uuid4().hex[:8]}"
    yield tid
    async with async_session() as session:
        await session.execute(
            delete(WatcherNotification).where(WatcherNotification.tenant_id == tid)
        )
        await session.execute(delete(WatchEvent).where(WatchEvent.tenant_id == tid))
        await session.execute(delete(WatcherRun).where(WatcherRun.tenant_id == tid))
        await session.commit()


async def _seed_event(tid: str, *, age_hours: int, severity: str = "critical", details=None):
    run_id, evt_id = uuid.uuid4(), uuid.uuid4()
    created = datetime.now(UTC) - timedelta(hours=age_hours)
    async with async_session() as session:
        session.add(
            WatcherRun(
                id=run_id,
                tenant_id=tid,
                watcher_name="code_quality",
                status="success",
                started_at=created,
            )
        )
        await session.commit()
        session.add(
            WatchEvent(
                id=evt_id,
                tenant_id=tid,
                watcher_name="code_quality",
                run_id=run_id,
                severity=severity,
                title="disk full",
                details={"pct": 99} if details is None else details,
                created_at=created,
            )
        )
        await session.commit()
    return evt_id


async def _retry_counts(evt_id) -> list[int]:
    async with async_session() as session:
        result = await session.execute(
            select(WatcherNotification.retry_count).where(WatcherNotification.event_id == evt_id)
        )
        return list(result.scalars().all())


class TestStaleCriticalRetry:
    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_resends_and_increments_until_the_cap(self, tenant):
        evt_id = await _seed_event(tenant, age_hours=48)
        engine = NotificationEngine(async_session)

        for expected in range(1, MAX_RETRIES + 1):
            assert await engine.check_stale_critical(tenant) == 1
            assert await _retry_counts(evt_id) == [expected]

        # capped
        assert await engine.check_stale_critical(tenant) == 0
        assert await _retry_counts(evt_id) == [MAX_RETRIES]

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_jsonb_details_survive_the_text_body_column(self, tenant):
        """A dict in details must not raise asyncpg DataError on insert."""
        evt_id = await _seed_event(tenant, age_hours=48, details={"pct": 99, "disk": "/"})
        engine = NotificationEngine(async_session)

        assert await engine.check_stale_critical(tenant) == 1, (
            "the resend failed — a dict details value probably reached the Text body column"
        )

        async with async_session() as session:
            body = (
                await session.execute(
                    select(WatcherNotification.body).where(WatcherNotification.event_id == evt_id)
                )
            ).scalar_one()
        assert isinstance(body, str)
        assert "99" in body

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_string_details_pass_through_unchanged(self, tenant):
        evt_id = await _seed_event(tenant, age_hours=48, details="plain text detail")
        engine = NotificationEngine(async_session)
        await engine.check_stale_critical(tenant)

        async with async_session() as session:
            body = (
                await session.execute(
                    select(WatcherNotification.body).where(WatcherNotification.event_id == evt_id)
                )
            ).scalar_one()
        assert body == "plain text detail"

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_acknowledged_events_are_not_resent(self, tenant):
        evt_id = await _seed_event(tenant, age_hours=48)
        engine = NotificationEngine(async_session)

        async with async_session() as session:
            evt = await session.get(WatchEvent, evt_id)
            evt.acknowledged_at = datetime.now(UTC)
            await session.commit()

        assert await engine.check_stale_critical(tenant) == 0

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_recent_events_are_not_resent(self, tenant):
        await _seed_event(tenant, age_hours=1)
        assert await NotificationEngine(async_session).check_stale_critical(tenant) == 0

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_non_critical_events_are_ignored(self, tenant):
        await _seed_event(tenant, age_hours=48, severity="info")
        assert await NotificationEngine(async_session).check_stale_critical(tenant) == 0

    @pytest.mark.asyncio
    @skip_on_db_error
    async def test_other_tenants_events_are_not_touched(self, tenant):
        await _seed_event(tenant, age_hours=48)
        other = f"{tenant}-other"
        assert await NotificationEngine(async_session).check_stale_critical(other) == 0
