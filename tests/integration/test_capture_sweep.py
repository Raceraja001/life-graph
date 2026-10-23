"""Captures left "received" are retried by the sweep (workers/capture_sweep.py)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from tests.integration.conftest import skip_on_db_error

TENANT = f"sweep_{uuid.uuid4().hex[:8]}"


async def _capture(content: str, *, surface="cli", modality="text", age_min=30, props=None):
    from life_graph.models.db import CaptureEvent
    from life_graph.storage.database import async_session

    async with async_session() as s:
        c = CaptureEvent(
            tenant_id=TENANT,
            surface=surface,
            modality=modality,
            content=content,
            content_hash=hashlib.sha256(f"{TENANT}{content}".encode()).hexdigest(),
            status="received",
            properties=props or {},
            trust_tier="self",
        )
        c.created_at = c.occurred_at = datetime.now(UTC) - timedelta(minutes=age_min)
        s.add(c)
        await s.commit()
        return c.id


async def _row(cid):
    from life_graph.models.db import CaptureEvent
    from life_graph.storage.database import async_session

    async with async_session() as s:
        return (await s.execute(select(CaptureEvent).where(CaptureEvent.id == cid))).scalar_one()


@pytest.fixture
def processor(monkeypatch):
    """The real processor's contract, without an LLM: mark the capture processed."""
    from life_graph.services import capture_processors as cp

    seen = []

    async def fake(event):
        seen.append(event.payload)
        if "fail" in (await _row(uuid.UUID(event.payload["capture_event_id"]))).content:
            raise RuntimeError("extraction blew up")
        from sqlalchemy import update

        from life_graph.models.db import CaptureEvent
        from life_graph.storage.database import async_session

        async with async_session() as s:
            await s.execute(
                update(CaptureEvent)
                .where(CaptureEvent.id == uuid.UUID(event.payload["capture_event_id"]))
                .values(status="processed")
            )
            await s.commit()

    monkeypatch.setattr(cp.capture_processors, "_on_capture_received", fake)
    return seen


@pytest.mark.asyncio
@skip_on_db_error
async def test_stale_captures_are_processed_fresh_ones_left_alone(processor):
    from life_graph.workers.capture_sweep import sweep_stuck_captures

    stale = await _capture("I prefer morning meetings.")
    fresh = await _capture("Just arrived.", age_min=2)
    voice = await _capture("(audio)", modality="voice")

    await sweep_stuck_captures(tenant_id=TENANT)

    assert (await _row(stale)).status == "processed"
    assert (await _row(fresh)).status == "received"  # the API may still be on it
    assert (await _row(voice)).status == "processed"  # handled by the upload path
    assert [p["capture_event_id"] for p in processor if p["tenant_id"] == TENANT] == [str(stale)]


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_capture_that_keeps_failing_is_marked_failed_after_three_tries(processor):
    from life_graph.workers.capture_sweep import MAX_ATTEMPTS, sweep_stuck_captures

    bad = await _capture("this one will fail every time")
    for _ in range(MAX_ATTEMPTS - 1):
        await sweep_stuck_captures(tenant_id=TENANT)
        assert (await _row(bad)).status == "received"
    await sweep_stuck_captures(tenant_id=TENANT)
    row = await _row(bad)
    assert row.status == "failed" and row.properties["sweep_attempts"] == MAX_ATTEMPTS
