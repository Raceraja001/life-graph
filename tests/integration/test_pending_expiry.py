"""The nightly decay job rejects memories left unreviewed too long — reversibly.

On 2026-10-22 the review queue held 3,668 memories, none approved for nine
days, so nothing reached recall. Unreviewed memories now expire after
``pending_memory_expiry_days``: rejected (approve brings one back), never
deleted, with the reason stamped on the memory. The days count from when the
Memory check asked the owner (``review_offered_at``, 2026-10-28): one never
shown waits however old it is.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"exp_{uuid.uuid4().hex[:8]}"


async def _seed(content, *, status, age_days, asked_days_ago=None):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    props = {}
    if asked_days_ago is not None:
        asked = datetime.now(UTC) - timedelta(days=asked_days_ago)
        props["review_offered_at"] = asked.isoformat()
    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=TENANT,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            status=status,
            trust_tier="verified",
            source_type="test",
            properties=props,
        )
        m.created_at = datetime.now(UTC) - timedelta(days=age_days)
        s.add(m)
        await s.commit()
        return m.id


async def _row(mid):
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return await s.get(Memory, mid)


@pytest.mark.asyncio
@skip_on_db_error
async def test_old_pending_memories_are_rejected_not_deleted(monkeypatch):
    from life_graph.config import settings
    from life_graph.workers.decay import run_decay_sweep

    monkeypatch.setattr(settings, "pending_memory_expiry_days", 14)
    old = await _seed("old unreviewed", status="pending", age_days=20, asked_days_ago=15)
    fresh = await _seed("asked recently", status="pending", age_days=20, asked_days_ago=3)
    never_asked = await _seed("old, never shown", status="pending", age_days=40)
    active = await _seed("old but approved", status="active", age_days=40)

    result = await run_decay_sweep({}, TENANT)

    assert result["expired_pending_count"] == 1
    row = await _row(old)
    assert row is not None and row.status == "rejected"
    assert row.properties["expired_pending"]["after_days"] == 14
    assert row.properties["review_offered_at"]  # what it had is kept
    assert (await _row(fresh)).status == "pending"
    assert (await _row(never_asked)).status == "pending"
    assert (await _row(active)).status == "active"


@pytest.mark.asyncio
@skip_on_db_error
async def test_zero_days_keeps_them_waiting(monkeypatch):
    from life_graph.config import settings
    from life_graph.workers.decay import run_decay_sweep

    monkeypatch.setattr(settings, "pending_memory_expiry_days", 0)
    old = await _seed("waits forever", status="pending", age_days=400, asked_days_ago=300)
    result = await run_decay_sweep({}, TENANT)
    assert result["expired_pending_count"] == 0
    assert (await _row(old)).status == "pending"
