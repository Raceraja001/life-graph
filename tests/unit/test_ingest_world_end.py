"""World end on the save path (ADR m8-ingestion §5.1, flag ``ingest_world_end``).

``services/memory/world_time.py`` ``end_for_fact`` wires the end rules of
``extraction/world_time.py`` into ``MemoryManager._process_fact``. Off, the
extractor's ``valid_until`` is stored exactly as before. On, a fact's own words
give ``valid_until`` and ``properties.world_time.end`` with ``valid_until_by =
"rules"``; the model's own ``valid_until`` is kept only when a rule agrees.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from life_graph.config import settings
from life_graph.core.memory_manager import MemoryManager
from life_graph.extraction import world_time as rules
from life_graph.extraction.rules import ExtractedFact
from life_graph.services.memory import retrieval, supersession, world_time

IST = ZoneInfo("Asia/Kolkata")
#: Saturday 14 Nov 2026, 10:00 in Chennai.
NOW = datetime(2026, 11, 14, 4, 30, tzinfo=UTC)
END_20_NOV = datetime(2026, 11, 21, tzinfo=IST)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "ingest_world_end", True)
    monkeypatch.setattr(settings, "ingest_world_time", False)
    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(world_time, "anchor", lambda: NOW)


@pytest.fixture
def off(monkeypatch):
    monkeypatch.setattr(settings, "ingest_world_end", False)
    monkeypatch.setattr(settings, "ingest_world_time", True)  # prod today
    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(world_time, "anchor", lambda: NOW)


def _f(content, said="", **kw) -> ExtractedFact:
    kw.setdefault("fact_type", "fact")
    return ExtractedFact(content=content, confidence=0.9, source_text=said, **kw)


def test_the_flag_defaults_off():
    from life_graph.config.memory import MemorySettings

    assert MemorySettings.model_fields["ingest_world_end"].default is False


# ── Which facts get an end ───────────────────────────────────


def test_a_fact_with_until_gets_its_end(on):
    found = world_time.end_for_fact(_f("The owner is on leave from work until 20 November."))
    assert found is not None
    assert (found.end, found.precision, found.rule, found.source) == (
        END_20_NOV,
        "day",
        "until.date",
        "content",
    )


@pytest.mark.parametrize(
    "fact",
    [
        _f("The owner is in Pune until March.", fact_type="intention"),
        _f("The owner is in Pune until March.", certainty="hedged"),
        _f("The owner is in Pune until March.", polarity="negate"),
        _f("The owner is in Pune."),
        _f("The owner is in Pune until the flat is ready."),
    ],
)
def test_hedged_negated_intention_and_unknown_facts_get_no_end(on, fact):
    assert world_time.end_for_fact(fact) is None


def test_the_flag_off_gives_no_end(off):
    assert world_time.end_for_fact(_f("The owner is on leave until 20 November.")) is None


def test_a_day_summary_gets_no_end(on):
    fact = _f("The owner is on leave until 20 November.")
    assert world_time.end_for_fact(fact, {"kind": "episode"}) is None


def test_an_end_at_or_before_the_known_start_is_dropped(on):
    fact = _f("The owner is on leave until 20 November.")
    late_start = rules.WorldTime(datetime(2026, 11, 25, tzinfo=IST), "day", "date")
    early_start = rules.WorldTime(datetime(2026, 11, 2, tzinfo=IST), "day", "date")
    assert world_time.end_for_fact(fact, None, late_start) is None
    assert world_time.end_for_fact(fact, None, early_start) is not None


def test_the_models_end_needs_a_rule_that_agrees(on):
    # 2026-11-20 is a Friday, within a week of Saturday 14 November.
    friday = _f("The owner is in Bangalore until Friday.", valid_until="2026-11-20")
    found = world_time.end_for_fact(friday)
    assert found is not None and found.source == "model"
    assert found.end == datetime(2026, 11, 21, tzinfo=IST)
    # A bare model date, with no "until" in the fact's words, is dropped.
    assert world_time.end_for_fact(_f("The owner is on leave.", valid_until="2026-11-20")) is None
    # The owner's words carry the "until": checked there.
    said = _f("The owner is in Bangalore.", "Velli varaikum Bangalore la", valid_until="2026-11-20")
    assert world_time.end_for_fact(said).source == "model"


def test_record_end_keeps_the_start_and_marks_rules():
    props = {"world_time": {"start": "2026-11-01T00:00:00+05:30", "precision": "month"}}
    found = rules.WorldEnd(END_20_NOV, "day", "until.date", "content")
    world_time.record_end(props, found)
    assert props["world_time"]["start"] == "2026-11-01T00:00:00+05:30"
    assert props["world_time"]["end"] == {
        "end": END_20_NOV.isoformat(),
        "precision": "day",
        "rule": "until.date",
        "source": "content",
    }
    assert props["valid_until_by"] == world_time.VALID_UNTIL_BY == "rules"


# ── Readers ──────────────────────────────────────────────────


def test_a_future_end_reads_as_current_until_then():
    row = SimpleNamespace(
        properties={}, valid_from=datetime(2026, 11, 14, tzinfo=IST), valid_until=END_20_NOV
    )
    assert retrieval.is_valid_at(row, datetime(2026, 11, 20, 23, 0, tzinfo=IST))
    assert not retrieval.is_valid_at(row, END_20_NOV)
    assert not retrieval.is_valid_at(row, datetime(2026, 11, 28, tzinfo=IST))


def test_an_end_alone_is_not_a_known_start_for_supersession():
    recorded = datetime(2026, 11, 14, tzinfo=UTC)
    new = SimpleNamespace(
        properties={"world_time": {"end": {"end": END_20_NOV.isoformat()}}},
        valid_from=recorded,
        created_at=recorded,
    )
    assert supersession.world_start(new) is None
    new.properties["world_time"]["start"] = recorded.isoformat()
    assert supersession.world_start(new) == recorded


def test_the_supersession_undo_keeps_a_rules_end():
    old_id, new_id = uuid.uuid4(), uuid.uuid4()
    old = SimpleNamespace(
        id=old_id,
        tenant_id="t",
        status="superseded",
        superseded_by=new_id,
        valid_until=END_20_NOV,
        properties={"valid_until_by": "rules", "superseded_at": "x"},
    )
    new = SimpleNamespace(id=new_id, tenant_id="t", supersedes=old_id)
    assert supersession.undo("t", old, new)
    assert old.valid_until == END_20_NOV
    assert old.properties == {"valid_until_by": "rules"}


# ── _process_fact ────────────────────────────────────────────


def _manager(monkeypatch):
    monkeypatch.setattr(settings, "dedup_enabled", False)
    monkeypatch.setattr("life_graph.core.memory_manager.get_current_tenant_id", lambda: "t_we")

    async def store_row(create, **kw):
        return SimpleNamespace(
            id=uuid.uuid4(),
            tenant_id="t_we",
            content=create.content,
            properties=create.properties,
            created_at=NOW,
            valid_from=kw.get("valid_from") or NOW,
            valid_until=kw.get("valid_until"),
        )

    store = SimpleNamespace(store=AsyncMock(side_effect=store_row))
    tagger = SimpleNamespace(score=lambda content, context: (0.5, "normal"))
    mgr = MemoryManager(store=store, extractor=None, tagger=tagger, contradiction_detector=None)
    monkeypatch.setattr(mgr, "_generate_embedding", AsyncMock(return_value=None))
    monkeypatch.setattr(mgr, "_file_slot", AsyncMock())
    monkeypatch.setattr(mgr, "_learn_names", AsyncMock())
    return mgr, store


async def test_flag_off_process_fact_stores_the_extractors_valid_until_as_before(off, monkeypatch):
    mgr, store = _manager(monkeypatch)
    fact = _f("The owner is on leave.", valid_until="2026-12-10")
    stored = await mgr._process_fact(fact, None, "chat")

    assert store.store.await_args.kwargs["valid_until"] == datetime.combine(
        datetime(2026, 12, 10).date(), time.max, tzinfo=IST
    )
    assert "valid_until_by" not in stored.properties
    # And the words' own "until" sets nothing with the flag off.
    stored = await mgr._process_fact(_f("The owner is on leave until 20 November."), None, "chat")
    assert store.store.await_args.kwargs["valid_until"] is None
    assert "end" not in (stored.properties.get("world_time") or {})


async def test_flag_on_process_fact_stores_and_records_the_end(on, monkeypatch):
    mgr, store = _manager(monkeypatch)
    stored = await mgr._process_fact(
        _f("The owner is on leave from work until 20 November."), None, "capture"
    )

    assert store.store.await_args.kwargs["valid_until"] == END_20_NOV
    assert stored.properties["world_time"] == {
        "end": {
            "end": END_20_NOV.isoformat(),
            "precision": "day",
            "rule": "until.date",
            "source": "content",
        }
    }
    assert stored.properties["valid_until_by"] == "rules"


async def test_flag_on_drops_a_model_valid_until_no_rule_backs(on, monkeypatch):
    mgr, store = _manager(monkeypatch)
    stored = await mgr._process_fact(
        _f("The owner is on leave.", valid_until="2026-12-10"), None, "chat"
    )

    assert store.store.await_args.kwargs["valid_until"] is None
    assert "world_time" not in stored.properties
    assert "valid_until_by" not in stored.properties


async def test_both_flags_on_keep_start_and_end_apart(on, monkeypatch):
    monkeypatch.setattr(settings, "ingest_world_time", True)
    mgr, store = _manager(monkeypatch)
    stored = await mgr._process_fact(_f("The owner joined Zoho last month."), None, "chat")
    assert store.store.await_args.kwargs["valid_until"] is None
    assert set(stored.properties["world_time"]) == {"start", "precision", "rule", "source"}
