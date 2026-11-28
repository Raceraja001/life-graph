"""World time on the save path, against the database (ADR m8-ingestion §5.1, step 3).

MemoryManager.ingest with ``ingest_world_time`` on writes ``valid_from`` from a
fact's own words and ``properties.world_time``; unknown keeps ``valid_from`` at
the recorded time; a late capture keeps its earlier rule start after
``_as_said``; the flag off writes rows as before. The extractor is a stand-in:
only the wiring is checked.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from life_graph.config import settings
from tests.integration.conftest import skip_on_db_error

TENANT = f"world_time_{uuid.uuid4().hex[:8]}"
IST = ZoneInfo("Asia/Kolkata")


def _fact(content, said=""):
    from life_graph.extraction.rules import ExtractedFact

    return ExtractedFact(content=content, fact_type="fact", confidence=0.95, source_text=said)


async def _ingest(monkeypatch, facts):
    from life_graph.api.dependencies import get_memory_manager
    from life_graph.core.tenant import tenant_scope

    manager = get_memory_manager()

    class _Result:
        def __init__(self, f):
            self.facts = f

    async def fake_extract(text, capture=False):
        return _Result(list(facts))

    async def no_embedding(text):
        return None

    monkeypatch.setattr(manager._extractor, "extract", fake_extract)
    monkeypatch.setattr(manager, "_generate_embedding", no_embedding)
    with tenant_scope(TENANT):
        return await manager.ingest("…", source="capture", trust_tier="self", capture=True)


async def _row(memory_id):
    from sqlalchemy import text

    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = await s.execute(
            text(
                "SELECT valid_from, created_at, properties->'world_time', tenant_id"
                " FROM memories WHERE id = :id"
            ),
            {"id": memory_id},
        )
        return row.one()


@pytest.mark.asyncio
@skip_on_db_error
async def test_rule_start_unknown_and_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(settings, "ingest_world_time", True)
    tag = uuid.uuid4().hex[:6]
    since, unknown = await _ingest(
        monkeypatch,
        [
            _fact(f"The owner has used Postgres {tag} since 2019."),
            _fact(f"The owner currently lives in Chennai {tag}."),
        ],
    )

    valid_from, _created, wt, tenant = await _row(since.id)
    assert tenant == TENANT
    assert valid_from == datetime(2019, 1, 1, tzinfo=IST)
    assert wt == {
        "start": datetime(2019, 1, 1, tzinfo=IST).isoformat(),
        "precision": "year",
        "rule": "year",
        "source": "content",
    }

    valid_from, created, wt, _ = await _row(unknown.id)
    assert wt is None
    assert abs(valid_from - created) < timedelta(seconds=1)  # today's "no world time"

    monkeypatch.setattr(settings, "ingest_world_time", False)
    (off,) = await _ingest(monkeypatch, [_fact(f"The owner has used Redis {tag} since 2020.")])
    valid_from, created, wt, _ = await _row(off.id)
    assert wt is None
    assert abs(valid_from - created) < timedelta(seconds=1)


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_late_capture_keeps_its_rule_start(monkeypatch):
    from life_graph.core.said_at import said_at

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(settings, "ingest_world_time", True)
    tag = uuid.uuid4().hex[:6]
    said = datetime.now(UTC) - timedelta(days=20)
    token = said_at.set(said)
    try:
        (late,) = await _ingest(
            monkeypatch, [_fact(f"The owner joined Zoho {tag}.", f"nethu Zoho {tag} la join aanen")]
        )
    finally:
        said_at.reset(token)

    valid_from, created, wt, _ = await _row(late.id)
    start = datetime.combine(
        (said.astimezone(IST) - timedelta(days=1)).date(), datetime.min.time(), tzinfo=IST
    )
    assert created == said
    assert valid_from == start  # the day before it was said, kept by _as_said
    assert wt["source"] == "source_text" and wt["rule"] == "ta.yesterday"
