"""World time on the save path (ADR m8-ingestion §5.1, build step 3).

``services/memory/world_time.py`` wires the rules of ``extraction/world_time.py``
into ``MemoryManager._process_fact``, the Jarvis tool ``memory_save`` and the
verbatim store of ``POST /memories``, behind ``ingest_world_time``. Off, every
save is exactly as before. On, a fact's own words give ``valid_from`` and
``properties.world_time``; unknown keeps ``valid_from`` at the recorded time.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from life_graph.config import settings
from life_graph.core.memory_manager import MemoryManager
from life_graph.core.said_at import said_at
from life_graph.extraction import llm
from life_graph.extraction import world_time as rules
from life_graph.extraction.rules import ExtractedFact
from life_graph.services.memory import world_time

IST = ZoneInfo("Asia/Kolkata")
#: Saturday 28 Nov 2026, 10:00 in Chennai.
NOW = datetime(2026, 11, 28, 4, 30, tzinfo=UTC)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "ingest_world_time", True)
    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(world_time, "anchor", lambda: NOW)


@pytest.fixture
def off(monkeypatch):
    monkeypatch.setattr(settings, "ingest_world_time", False)
    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(world_time, "anchor", lambda: NOW)


def _f(content, said="", **kw) -> ExtractedFact:
    kw.setdefault("fact_type", "fact")
    return ExtractedFact(content=content, confidence=0.9, source_text=said, **kw)


def _start(found) -> tuple | None:
    if found is None:
        return None
    return (found.start.date(), found.precision, found.source)


# ── Which facts get a start ──────────────────────────────────


@pytest.mark.parametrize(
    ("content", "said", "expected"),
    [
        # English, from the model's sentence.
        (
            "The owner moved to Coimbatore last month.",
            "",
            (date(2026, 10, 1), rules.MONTH, rules.CONTENT),
        ),
        ("The owner has worked at Zoho since 2019.", "", (date(2019, 1, 1), rules.YEAR, "content")),
        ("The owner joined the gym yesterday.", "", (date(2026, 11, 27), rules.DAY, "content")),
        # Tamil: the content is English with no time; the owner's words hold one phrase.
        (
            "The owner moved to Chennai.",
            "நான் போன மாதம் சென்னைக்கு வந்தேன்",
            (date(2026, 10, 1), rules.MONTH, rules.SOURCE_TEXT),
        ),
        (
            "The owner joined a new job.",
            "நேற்று புது வேலையில் சேர்ந்தேன்",
            (date(2026, 11, 27), rules.DAY, rules.SOURCE_TEXT),
        ),
        # Tanglish.
        (
            "The owner shifted to Coimbatore.",
            "nethu Coimbatore ku shift aanen",
            (date(2026, 11, 27), rules.DAY, rules.SOURCE_TEXT),
        ),
        (
            "The owner bought a car.",
            "pona maasam car vaanginen",
            (date(2026, 10, 1), rules.MONTH, rules.SOURCE_TEXT),
        ),
    ],
)
def test_a_fact_said_with_a_time_gets_its_start(on, content, said, expected):
    assert _start(world_time.for_fact(_f(content, said))) == expected


@pytest.mark.parametrize(
    ("fact"),
    [
        _f("The owner will move to Chennai next week."),  # future, and "will"
        _f("The owner moves to Chennai next week."),  # future phrase alone
        _f("The owner moves to Chennai.", "adutha vaaram Chennai ku poren"),  # Tanglish plan
        _f("The owner might have moved to Chennai last month."),  # hedged words
        _f("The owner moved to Chennai last month.", certainty="hedged"),  # hedged by the model
        _f("The owner no longer lives in Madurai since March."),  # negated words
        _f("The owner moved to Chennai last month.", polarity="negate"),  # negated by the model
        _f("The owner plans to learn Tamil since March.", fact_type="intention"),
        _f("The owner currently lives in Chennai."),  # "now" is not a start
        _f("The owner lives in Chennai."),  # no phrase: unknown
        # Two facts with two times in one message: the owner's words are not used.
        _f("The owner moved to Chennai.", "moved to Chennai last month, joined Zoho yesterday"),
    ],
)
def test_future_hedged_intention_and_unknown_facts_get_no_start(on, fact):
    assert world_time.for_fact(fact) is None


def test_a_day_summary_keeps_its_own_date(on):
    fact = _f("The owner went to Ooty yesterday.")
    assert world_time.for_fact(fact, {"kind": "episode", "date": "2026-11-27"}) is None


def test_the_flag_off_gives_no_start(off):
    assert world_time.for_fact(_f("The owner has worked at Zoho since 2019.")) is None
    assert world_time.for_text("Since 2019 I use Postgres") is None


def test_the_time_zone_is_the_owners_setting(on, monkeypatch):
    # 21:00 UTC on the 27th is already the 28th in Chennai.
    monkeypatch.setattr(world_time, "anchor", lambda: datetime(2026, 11, 27, 21, 0, tzinfo=UTC))
    found = world_time.for_fact(_f("The owner joined the gym yesterday."))
    assert found is not None and found.start == datetime(2026, 11, 27, tzinfo=IST)
    monkeypatch.setattr(settings, "user_timezone", "UTC")
    found = world_time.for_fact(_f("The owner joined the gym yesterday."))
    assert found is not None and found.start == datetime(2026, 11, 26, tzinfo=UTC)


def test_the_anchor_is_when_it_was_said(monkeypatch):
    said = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    token = said_at.set(said)
    try:
        assert world_time.anchor() == said
    finally:
        said_at.reset(token)
    assert abs(world_time.anchor() - datetime.now(UTC)) < timedelta(seconds=5)


# ── The model's date needs a rule to agree ───────────────────


def test_a_model_date_without_a_phrase_is_rejected(on):
    assert world_time.for_fact(_f("The owner moved to Chennai.", valid_from="2026-03-10")) is None
    fact = _f("The owner moved to Chennai.", "moved to Chennai", valid_from="2026-03-10")
    assert world_time.for_fact(fact) is None


def test_a_model_date_for_a_phrase_the_rules_cannot_place_is_kept(on):
    fact = _f("The owner shifted to Chennai last Pongal.", valid_from="2026-01-14")
    assert _start(world_time.for_fact(fact)) == (date(2026, 1, 14), rules.DAY, rules.MODEL)
    # From the owner's words, when they hold exactly one phrase.
    fact = _f(
        "The owner shifted to Chennai.", "Pongal appo Chennai ku shift", valid_from="2026-01-14"
    )
    assert _start(world_time.for_fact(fact)) == (date(2026, 1, 14), rules.DAY, rules.MODEL)


def test_a_model_date_outside_every_placed_period_is_rejected(on):
    # Two starts: the rules cannot say which; the model may pick one, not invent a third.
    content = "The owner lived in Madurai in 2019 and moved to Chennai in 2021."
    assert world_time.for_fact(_f(content, valid_from="2018-05-01")) is None
    assert _start(world_time.for_fact(_f(content, valid_from="2021-06-01"))) == (
        date(2021, 6, 1),
        rules.DAY,
        rules.MODEL,
    )
    assert rules.from_model("2026-03-10", "moved last month", NOW, IST) is None
    assert rules.from_model("2026-10-15", "moved last month", NOW, IST) is not None


def test_a_model_date_on_a_blocked_fact_is_rejected(on):
    fact = _f("The owner may have shifted last Pongal.", valid_from="2026-01-14")
    assert world_time.for_fact(fact) is None


# ── The extraction request ───────────────────────────────────


def test_flag_off_the_request_and_the_parse_are_as_before(off, monkeypatch):
    monkeypatch.setattr(settings, "ingest_typed_links", False)
    assert llm.extraction_schema() is llm._EXTRACTION_SCHEMA
    assert "valid_from" not in llm._validity({"valid_from": "2026-01-14"})


def test_flag_on_asks_for_valid_from_and_checks_it(on, monkeypatch):
    monkeypatch.setattr(settings, "ingest_typed_links", False)
    fields = llm.extraction_schema()["properties"]["facts"]["items"]["properties"]
    assert fields["valid_from"] is llm._VALID_FROM_FIELD
    assert "valid_from" not in llm._EXTRACTION_SCHEMA["properties"]["facts"]["items"]["properties"]
    assert llm._validity({"valid_from": "2026-01-14"})["valid_from"] == "2026-01-14"
    assert llm._validity({"valid_from": "last Pongal"})["valid_from"] is None


# ── _process_fact: store(valid_from=...), properties, late captures ──


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


def _manager(monkeypatch, recorded: datetime):
    """A MemoryManager whose store keeps the row it was asked for."""
    monkeypatch.setattr(settings, "dedup_enabled", False)
    monkeypatch.setattr("life_graph.storage.database.async_session", lambda: _Session([]))
    monkeypatch.setattr("life_graph.core.memory_manager.get_current_tenant_id", lambda: "t_wt")

    async def store_row(create, **kw):
        return SimpleNamespace(
            id=uuid.uuid4(),
            tenant_id="t_wt",
            content=create.content,
            properties=create.properties,
            created_at=recorded,
            updated_at=recorded,
            last_accessed=recorded,
            valid_from=kw.get("valid_from") or recorded,
        )

    store = SimpleNamespace(store=AsyncMock(side_effect=store_row))
    tagger = SimpleNamespace(score=lambda content, context: (0.5, "normal"))
    mgr = MemoryManager(store=store, extractor=None, tagger=tagger, contradiction_detector=None)
    monkeypatch.setattr(mgr, "_generate_embedding", AsyncMock(return_value=None))
    monkeypatch.setattr(mgr, "_file_slot", AsyncMock())
    monkeypatch.setattr(mgr, "_learn_names", AsyncMock())
    return mgr, store


async def test_flag_off_process_fact_stores_as_before(off, monkeypatch):
    mgr, store = _manager(monkeypatch, NOW)
    stored = await mgr._process_fact(_f("The owner has worked at Zoho since 2019."), None, "chat")

    assert "valid_from" not in store.store.await_args.kwargs
    assert "world_time" not in stored.properties
    assert stored.valid_from == NOW


async def test_flag_on_process_fact_passes_valid_from_and_records_it(on, monkeypatch):
    mgr, store = _manager(monkeypatch, NOW)
    stored = await mgr._process_fact(
        _f("The owner moved to Chennai.", "நான் போன மாதம் சென்னைக்கு வந்தேன்"), None, "capture"
    )

    start = datetime(2026, 10, 1, tzinfo=IST)
    assert store.store.await_args.kwargs["valid_from"] == start
    assert stored.properties["world_time"] == {
        "start": start.isoformat(),
        "precision": "month",
        "rule": "ta.last_month",
        "source": "source_text",
    }


async def test_flag_on_unknown_keeps_valid_from_at_the_recorded_time(on, monkeypatch):
    mgr, store = _manager(monkeypatch, NOW)
    stored = await mgr._process_fact(_f("The owner currently lives in Chennai."), None, "chat")

    assert "valid_from" not in store.store.await_args.kwargs
    assert "world_time" not in stored.properties
    assert stored.valid_from == NOW


async def test_a_late_capture_anchors_at_when_it_was_said(monkeypatch):
    monkeypatch.setattr(settings, "ingest_world_time", True)
    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    said = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)  # 14:30 on Monday 2 Nov in Chennai
    mgr, store = _manager(monkeypatch, recorded=datetime.now(UTC))  # arrives now
    token = said_at.set(said)
    try:
        stored = await mgr._process_fact(
            _f("The owner started at Zoho.", "nethu Zoho la join panninen"), None, "capture"
        )
    finally:
        said_at.reset(token)

    start = datetime(2026, 11, 1, tzinfo=IST)  # the day before it was said, not before today
    assert store.store.await_args.kwargs["valid_from"] == start
    # _as_said dates the row as said and keeps the earlier rule start (#429).
    assert stored.created_at == said
    assert stored.valid_from == start


async def test_a_late_capture_with_no_time_still_equals_its_said_time(monkeypatch):
    monkeypatch.setattr(settings, "ingest_world_time", True)
    said = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    mgr, store = _manager(monkeypatch, recorded=datetime.now(UTC))
    token = said_at.set(said)
    try:
        stored = await mgr._process_fact(_f("The owner lives in Chennai."), None, "capture")
    finally:
        said_at.reset(token)

    assert "valid_from" not in store.store.await_args.kwargs
    assert stored.valid_from == said == stored.created_at


# ── memory_save and the verbatim store ───────────────────────


@pytest.fixture
def save_store(monkeypatch):
    from life_graph import runtime
    from life_graph.services import entities, profile_card
    from life_graph.tools import memory_search

    async def store_row(create, **_kw):
        return SimpleNamespace(id=uuid.uuid4(), content=create.content)

    store = SimpleNamespace(
        find_exact_duplicate=AsyncMock(return_value=None),
        find_similar=AsyncMock(return_value=[]),
        store=AsyncMock(side_effect=store_row),
    )
    manager = SimpleNamespace(generate_embedding=AsyncMock(return_value=None))
    monkeypatch.setattr(runtime, "get_store", lambda: store)
    monkeypatch.setattr(runtime, "get_memory_manager", lambda: manager)
    monkeypatch.setattr(
        memory_search,
        "_owner_message",
        AsyncMock(return_value="remember this, nethu Coimbatore ku shift aanen"),
    )
    monkeypatch.setattr(entities, "known_in_text", AsyncMock(return_value=[]), raising=False)
    monkeypatch.setattr(entities, "link", AsyncMock(), raising=False)
    monkeypatch.setattr(profile_card, "invalidate", lambda tenant: None)
    return store


async def _save(content):
    from life_graph.core.tenant import tenant_scope
    from life_graph.tools.memory_search import memory_save

    with tenant_scope("t_wt_save"):
        return await memory_save(content)


async def test_memory_save_flag_off_stores_as_before(off, save_store):
    await _save("The owner shifted to Coimbatore.")
    kwargs = save_store.store.await_args.kwargs
    assert "valid_from" not in kwargs
    assert "world_time" not in save_store.store.await_args.args[0].properties


async def test_memory_save_reads_the_owners_message(on, save_store):
    await _save("The owner shifted to Coimbatore.")
    assert save_store.store.await_args.kwargs["valid_from"] == datetime(2026, 11, 27, tzinfo=IST)
    props = save_store.store.await_args.args[0].properties
    assert props["world_time"]["source"] == "source_text"
    assert props["saved_by"] == "jarvis"


async def test_verbatim_store_flag_off_and_on(monkeypatch):
    from life_graph.api.memories import _store_verbatim
    from life_graph.models.schemas import MemoryCreate

    monkeypatch.setattr(settings, "user_timezone", "Asia/Kolkata")
    monkeypatch.setattr(world_time, "anchor", lambda: NOW)
    manager = SimpleNamespace(generate_embedding=AsyncMock(return_value=[0.1]))
    store = SimpleNamespace(
        find_exact_duplicate=AsyncMock(return_value=None), store=AsyncMock(return_value=None)
    )
    body = MemoryCreate(
        content="Using Postgres since 2019", tags=["tool"], importance=0.4, properties={"a": 1}
    )

    monkeypatch.setattr(settings, "ingest_world_time", False)
    await _store_verbatim(body, manager=manager, store=store, tier="self")
    assert store.store.await_args.args[0] is body
    assert store.store.await_args.kwargs == {
        "embedding": [0.1],
        "trust_tier": "self",
        "extraction_tier": "manual",
    }

    monkeypatch.setattr(settings, "ingest_world_time", True)
    await _store_verbatim(body, manager=manager, store=store, tier="self")
    assert store.store.await_args.kwargs["valid_from"] == datetime(2019, 1, 1, tzinfo=IST)
    sent = store.store.await_args.args[0]
    assert sent.properties["a"] == 1 and sent.properties["world_time"]["rule"] == "year"
    assert body.properties == {"a": 1}  # the caller's body is not changed
