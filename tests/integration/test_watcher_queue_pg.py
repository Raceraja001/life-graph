"""Queued watcher notifications reach the daily brief, without a flood.

``NotificationEngine.route_event`` stores an important event from a
non-urgent watcher as ``watcher_notifications.status = 'queued'``, and nothing
ever delivered it. ``hold_queued_for_brief`` gathers the fresh rows into one
kernel notification held for the brief, expires old ones unsent, caps how
many it gathers, and folds a repeated title into one line.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"wq_{uuid.uuid4().hex[:8]}"


def _tenant() -> str:
    return f"{TENANT}_{uuid.uuid4().hex[:6]}"


async def _queue(tenant: str, subject: str, *, age_hours: float = 1, status: str = "queued"):
    from life_graph.storage.database import async_session
    from life_graph.watchers.models import WatcherNotification, WatchEvent

    created = datetime.now(UTC) - timedelta(hours=age_hours)
    async with async_session() as s:
        evt = WatchEvent(
            tenant_id=tenant,
            watcher_name="dependency",
            severity="important",
            title=subject,
            details={},
            created_at=created,
        )
        s.add(evt)
        await s.flush()
        row = WatcherNotification(
            tenant_id=tenant,
            event_id=evt.id,
            channel="terminal",
            severity="important",
            status=status,
            subject=subject,
            body=f"details of {subject}",
            created_at=created,
        )
        s.add(row)
        await s.commit()
        return row.id


async def _rows(tenant: str) -> list[tuple]:
    from life_graph.storage.database import async_session
    from life_graph.watchers.models import WatcherNotification

    async with async_session() as s:
        return list(
            (
                await s.execute(
                    select(
                        WatcherNotification.subject,
                        WatcherNotification.status,
                        WatcherNotification.digest_id,
                    )
                    .where(WatcherNotification.tenant_id == tenant)
                    .order_by(WatcherNotification.created_at)
                )
            ).all()
        )


async def _held(tenant: str) -> list:
    from life_graph.models.db import Notification
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return list(
            (await s.execute(select(Notification).where(Notification.tenant_id == tenant)))
            .scalars()
            .all()
        )


def _engines():
    from life_graph.kernel.notification_engine import NotificationEngine as Kernel
    from life_graph.storage.database import async_session
    from life_graph.watchers.notification_engine import NotificationEngine

    return NotificationEngine(async_session), Kernel(async_session)


@pytest.mark.asyncio
@skip_on_db_error
async def test_fresh_rows_become_one_brief_line_and_old_ones_expire():
    from life_graph.services.brief import BriefComposer
    from life_graph.storage.database import async_session

    tenant = _tenant()
    await _queue(tenant, "Outdated: ancient", age_hours=30)
    await _queue(tenant, "Outdated: httpx", age_hours=3)
    await _queue(tenant, "Outdated: fastapi", age_hours=2)
    await _queue(tenant, "Outdated: fastapi", age_hours=1)  # same finding again
    await _queue(tenant, "Already sent", status="sent")

    watchers, kernel = _engines()
    assert tenant in await watchers.queued_tenants()
    counts = await watchers.hold_queued_for_brief(tenant, kernel, max_age_hours=24, limit=10)

    assert counts == {"held": 3, "lines": 2, "expired": 1, "left": 0, "failed": 0}
    held = await _held(tenant)
    assert len(held) == 1  # one phone notification, however many were queued
    note = held[0]
    assert note.title == "3 watcher findings: Outdated: httpx and 1 more"
    assert note.body == "- Outdated: httpx\n- Outdated: fastapi (x2)"
    assert note.priority == "important"
    assert note.source_type == "watcher"
    assert note.extra_metadata["deliver_at_brief"] is True
    assert note.is_delivered is False
    assert await _rows(tenant) == [
        ("Outdated: ancient", "expired", None),
        ("Outdated: httpx", "held_for_brief", note.id),
        ("Outdated: fastapi", "held_for_brief", note.id),
        ("Outdated: fastapi", "held_for_brief", note.id),
        ("Already sent", "sent", None),
    ]
    assert tenant not in await watchers.queued_tenants()

    # The brief lists it under "Needs attention", once.
    since = datetime.now(UTC) - timedelta(hours=24)
    composer = BriefComposer(async_session)
    picked = await composer._collect_held_notifications(tenant, since)
    assert [h["title"] for h in picked] == [note.title]
    assert await composer._collect_held_notifications(tenant, since) == []

    # A second run has nothing left to do and writes nothing.
    again = await watchers.hold_queued_for_brief(tenant, kernel, max_age_hours=24, limit=10)
    assert again == {"held": 0, "lines": 0, "expired": 0, "left": 0, "failed": 0}
    assert len(await _held(tenant)) == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_cap_leaves_the_rest_queued_oldest_first():
    tenant = _tenant()
    await _queue(tenant, "first", age_hours=3)
    await _queue(tenant, "second", age_hours=2)
    await _queue(tenant, "third", age_hours=1)

    watchers, kernel = _engines()
    counts = await watchers.hold_queued_for_brief(tenant, kernel, max_age_hours=24, limit=2)

    assert counts == {"held": 2, "lines": 2, "expired": 0, "left": 1, "failed": 0}
    assert [(s, st) for s, st, _ in await _rows(tenant)] == [
        ("first", "held_for_brief"),
        ("second", "held_for_brief"),
        ("third", "queued"),
    ]
    (note,) = await _held(tenant)
    assert note.body == "- first\n- second\n1 more still queued."


@pytest.mark.asyncio
@skip_on_db_error
async def test_rows_stay_queued_when_the_summary_could_not_be_written():
    tenant = _tenant()
    await _queue(tenant, "will fail")

    class Broken:
        async def create(self, *a, **kw):
            raise RuntimeError("db hiccup")

    watchers, _ = _engines()
    counts = await watchers.hold_queued_for_brief(tenant, Broken(), max_age_hours=24, limit=10)

    assert counts == {"held": 0, "lines": 0, "expired": 0, "left": 0, "failed": 1}
    assert [(s, st) for s, st, _ in await _rows(tenant)] == [("will fail", "queued")]
    assert await _held(tenant) == []
