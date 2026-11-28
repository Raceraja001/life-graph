"""A late capture's ``valid_from`` follows its recorded time (ADR m8-ingestion §5.1, §10.1).

``_as_said`` backdates ``created_at`` to when a late capture was said. It used to
leave ``valid_from`` at the arrival time, later than the recorded time, so the
snapshot reported ``world_time_known: true`` with a world time that was only the
delivery time.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from life_graph.core.memory_manager import MemoryManager
from life_graph.services.memory.snapshot import Budget, memory_item

ARRIVED = datetime(2026, 11, 2, 9, 0, 0, tzinfo=UTC)
SAID = ARRIVED - timedelta(days=20)


class _Session:
    def __init__(self, sink: list) -> None:
        self._sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, stmt):
        self._sink.append(stmt)

    async def commit(self):
        return None


@pytest.fixture
def written(monkeypatch):
    sink: list = []
    monkeypatch.setattr(
        "life_graph.storage.database.async_session", lambda: _Session(sink), raising=True
    )
    monkeypatch.setattr(
        "life_graph.core.memory_manager.get_current_tenant_id", lambda: "t_late", raising=True
    )
    return sink


def _stored(valid_from: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        content="The owner lives in Madurai.",
        created_at=ARRIVED,
        updated_at=ARRIVED,
        last_accessed=ARRIVED,
        valid_from=valid_from,
        valid_until=None,
        properties={},
        status="active",
        source_type="capture",
        trust_tier="self",
        extraction_tier="llm",
        fact_type="fact",
        tags=[],
        last_reinforced=None,
    )


def _manager() -> MemoryManager:
    return MemoryManager(store=None, extractor=None, tagger=None, contradiction_detector=None)


def _set_values(stmt) -> dict:
    return {col.key: bind.value for col, bind in stmt._values.items()}


async def test_a_late_memory_gets_valid_from_as_said(written):
    stored = _stored(valid_from=ARRIVED)
    await _manager()._as_said(stored, SAID, history_of=None)

    assert stored.valid_from == SAID == stored.created_at
    (stmt,) = written
    assert _set_values(stmt)["valid_from"] == SAID


async def test_a_late_memory_has_no_world_time_in_the_snapshot(written):
    stored = _stored(valid_from=ARRIVED)
    await _manager()._as_said(stored, SAID, history_of=None)

    item = memory_item(stored, ARRIVED, Budget())
    assert item.world_time_known is False
    assert item.valid_from == item.recorded_at == SAID.isoformat()


async def test_an_arrival_a_moment_after_the_insert_still_moves(written):
    # The column defaults are separate "now" calls; a valid_from a little after
    # created_at is still the arrival time, not a world time.
    stored = _stored(valid_from=ARRIVED + timedelta(seconds=1))
    await _manager()._as_said(stored, SAID, history_of=None)

    assert stored.valid_from == SAID
    assert memory_item(stored, ARRIVED, Budget()).world_time_known is False


async def test_an_earlier_world_time_of_its_own_is_kept(written):
    # A start before it was said ("since 2019") is a real world time: not moved.
    since = datetime(2019, 1, 1, tzinfo=UTC)
    stored = _stored(valid_from=since)
    await _manager()._as_said(stored, SAID, history_of=None)

    assert stored.valid_from == since
    assert "valid_from" not in _set_values(written[0])
    assert memory_item(stored, ARRIVED, Budget()).world_time_known is True


async def test_history_of_a_newer_value_also_moves_valid_from(written):
    stored = _stored(valid_from=ARRIVED)
    newer = str(uuid.uuid4())
    await _manager()._as_said(stored, SAID, history_of=newer)

    assert stored.status == "superseded"
    assert stored.valid_from == SAID
