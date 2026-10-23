"""The daily brief says how many new memories wait for review — counts only."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.conftest import skip_on_db_error

TENANT = f"brief_mr_{uuid.uuid4().hex[:8]}"


async def _seed(content: str, *, status: str, age_hours: float) -> None:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        m = Memory(
            content=content,
            tenant_id=TENANT,
            content_hash=hashlib.sha256(f"{TENANT}{content}".encode()).hexdigest(),
            status=status,
            trust_tier="self",
            source_type="test",
        )
        m.created_at = datetime.now(UTC) - timedelta(hours=age_hours)
        s.add(m)
        await s.commit()


def _composer():
    from life_graph.core.events import event_bus
    from life_graph.services.brief import BriefComposer
    from life_graph.storage.database import async_session

    return BriefComposer(async_session, event_bus)


@pytest.mark.asyncio
@skip_on_db_error
async def test_the_line_counts_new_and_waiting_memories_without_their_content(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "pending_memory_expiry_days", 14)
    since = datetime.now(UTC) - timedelta(days=1)
    await _seed("My passport expires in May 2029.", status="pending", age_hours=2)
    await _seed("My dentist is Dr. Rao.", status="pending", age_hours=3)
    await _seed("An older unreviewed note.", status="pending", age_hours=72)
    await _seed("Approved already.", status="active", age_hours=1)

    line = await _composer()._memory_review_line(TENANT, since)

    assert (
        line
        == "2 new memories to review (3 waiting in all). Unreviewed ones are dropped after 14 days."
    )
    assert "passport" not in line and "dentist" not in line


@pytest.mark.asyncio
@skip_on_db_error
async def test_no_new_memories_means_no_line():
    since = datetime.now(UTC) - timedelta(days=1)
    other = f"{TENANT}_empty"
    assert await _composer()._memory_review_line(other, since) is None
