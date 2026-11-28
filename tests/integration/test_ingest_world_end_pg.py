"""World end on the save path, against the database (ADR m8-ingestion §5.1, ``ingest_world_end``).

MemoryManager.ingest with ``ingest_world_end`` on writes ``valid_until`` from a
fact's own words ("until 20 November 2026"), ``properties.world_time.end`` and
``valid_until_by = "rules"``; a model ``valid_until`` no rule backs is not
stored; a future end keeps the row current until then; the flag off stores the
extractor's ``valid_until`` as before. The extractor is a stand-in: only the
wiring is checked.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from life_graph.config import settings
from tests.integration.conftest import skip_on_db_error

TENANT = f"world_end_{uuid.uuid4().hex[:8]}"
IST = ZoneInfo("Asia/Kolkata")


def _fact(content, valid_until=None):
    from life_graph.extraction.rules import ExtractedFact

    return ExtractedFact(
        content=content, fact_type="fact", confidence=0.95, source_text="", valid_until=valid_until
    )


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
                "SELECT valid_until, properties->'world_time', properties->>'valid_until_by',"
                " tenant_id FROM memories WHERE id = :id"
            ),
            {"id": memory_id},
        )
        return row.one()


async def _valid_now(memory_id) -> bool:
    """The same valid-time filter the store's ``valid_at`` search uses (storage/postgres.py)."""
    from sqlalchemy import text

    from life_graph.storage.database import async_session

    async with async_session() as s:
        row = await s.execute(
            text(
                "SELECT count(*) FROM memories WHERE id = :id AND tenant_id = :t"
                " AND (valid_until IS NULL OR valid_until > :now)"
            ),
            {"id": memory_id, "t": TENANT, "now": datetime.now(UTC)},
        )
        return row.scalar_one() == 1


@pytest.mark.asyncio
@skip_on_db_error
async def test_rule_end_past_and_future_model_only_and_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(settings, "ingest_world_end", True)
    tag = uuid.uuid4().hex[:6]
    past, future, model_only = await _ingest(
        monkeypatch,
        [
            _fact(f"The owner {tag} was on leave until 20 November 2026."),
            _fact(f"The owner {tag} has the flat on lease until 2099."),
            _fact(f"The owner {tag} is on leave.", valid_until="2099-12-10"),
        ],
    )

    valid_until, wt, by, tenant = await _row(past.id)
    assert tenant == TENANT
    assert valid_until == datetime(2026, 11, 21, tzinfo=IST)
    assert wt == {
        "end": {
            "end": datetime(2026, 11, 21, tzinfo=IST).isoformat(),
            "precision": "day",
            "rule": "until.date",
            "source": "content",
        }
    }
    assert by == "rules"
    assert not await _valid_now(past.id)  # expired

    valid_until, wt, by, _ = await _row(future.id)
    assert valid_until == datetime(2100, 1, 1, tzinfo=IST)
    assert wt["end"]["precision"] == "year" and by == "rules"
    assert await _valid_now(future.id)  # current until then

    valid_until, wt, by, _ = await _row(model_only.id)
    assert valid_until is None and wt is None and by is None

    monkeypatch.setattr(settings, "ingest_world_end", False)
    (off,) = await _ingest(
        monkeypatch, [_fact(f"The owner {tag} is away on work.", valid_until="2099-12-10")]
    )
    valid_until, wt, by, _ = await _row(off.id)
    assert valid_until == datetime.combine(date(2099, 12, 10), time.max, tzinfo=IST)
    assert wt is None and by is None


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_late_capture_keeps_its_rule_end(monkeypatch):
    from life_graph.core.said_at import said_at

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(settings, "ingest_world_end", True)
    tag = uuid.uuid4().hex[:6]
    said = datetime.now(UTC) - timedelta(days=20)
    token = said_at.set(said)
    try:
        (late,) = await _ingest(
            monkeypatch, [_fact(f"The owner {tag} is on night shift till tomorrow.")]
        )
    finally:
        said_at.reset(token)

    valid_until, wt, by, _ = await _row(late.id)
    day_after = (said.astimezone(IST) + timedelta(days=2)).date()
    assert valid_until == datetime.combine(day_after, time(0, 0), tzinfo=IST)
    assert wt["end"]["rule"] == "until.tomorrow" and by == "rules"
