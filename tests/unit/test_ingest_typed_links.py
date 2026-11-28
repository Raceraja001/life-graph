"""Typed links at extraction (M8 ingestion ADR §5.3, services/memory/typed_links.py).

BECAUSE comes from the extractor's ``reason``; LEADS_TO needs the model's
``leads_to`` proposal and a cue word in the owner's words. Only facts of one
message, only memories that message stored new, never with the flag off.

``CASES`` are the labelled ingestion cases for links (the ADR's
``evals/ingestion_structure`` set is not on master yet, so they live here):
English, Tamil and Tanglish, with the links each must give, and nothing else.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.core import memory_manager as mm
from life_graph.core.errors import ConflictError
from life_graph.core.tenant import tenant_scope
from life_graph.extraction.llm import _EXTRACTION_SCHEMA, LLMExtractor, extraction_schema
from life_graph.extraction.rules import ExtractedFact
from life_graph.services.memory import typed_links


def _f(content, *, reason=None, leads_to=(), said="", confidence=0.9) -> ExtractedFact:
    return ExtractedFact(
        content=content,
        fact_type="fact",
        confidence=confidence,
        source_text=said,
        reason=reason,
        leads_to=list(leads_to),
    )


SUPABASE = "The owner moved FarmLink to Supabase because Firebase got too expensive."
FIREBASE = "Firebase became too expensive for FarmLink."
SYNC = "The owner rewrote the FarmLink sync service."
CAR = "The owner sold the old car."
BUS = "The owner takes the bus to work."

#: (name, said, facts, expected links as (source, target, type)).
CASES = [
    (
        "because, from the reason field",
        "I moved FarmLink to Supabase because Firebase got too expensive",
        [_f(SUPABASE, reason="Firebase got too expensive"), _f(FIREBASE)],
        {(0, 1, "BECAUSE")},
    ),
    (
        "reason said by no other fact",
        "I moved FarmLink to Supabase because Firebase got too expensive",
        [_f(SUPABASE, reason="Firebase got too expensive"), _f(SYNC)],
        set(),
    ),
    (
        "no reason, no because",
        "I moved FarmLink to Supabase. Firebase is expensive.",
        [_f(SUPABASE), _f(FIREBASE)],
        set(),
    ),
    (
        "leads_to with 'so'",
        "I sold the old car, so now I take the bus to work",
        [_f(CAR, leads_to=[BUS]), _f(BUS)],
        {(0, 1, "LEADS_TO")},
    ),
    (
        "leads_to with 'therefore'",
        "I sold the old car; therefore I take the bus to work",
        [_f(CAR, leads_to=[BUS]), _f(BUS)],
        {(0, 1, "LEADS_TO")},
    ),
    (
        "leads_to proposed, no cue in the text",
        "I sold the old car. I take the bus to work.",
        [_f(CAR, leads_to=[BUS]), _f(BUS)],
        set(),
    ),
    (
        "'also' and 'sofa' are not the cue 'so'",
        "I sold the old car and the sofa. I also take the bus to work.",
        [_f(CAR, leads_to=[BUS]), _f(BUS)],
        set(),
    ),
    (
        "cue in the text, no proposal",
        "I sold the old car, so now I take the bus to work",
        [_f(CAR), _f(BUS)],
        set(),
    ),
    (
        "Tamil cue அதனால்",
        "பழைய காரை விற்றுவிட்டேன், அதனால் இப்போது பஸ்ஸில் வேலைக்கு போகிறேன்",
        [_f(CAR, leads_to=[BUS]), _f(BUS)],
        {(0, 1, "LEADS_TO")},
    ),
    (
        "Tamil cue அப்புறம் with a case ending",
        "காரை வித்துட்டேன். அப்புறமா பஸ்ல போறேன்",
        [_f(CAR, leads_to=[BUS]), _f(BUS)],
        {(0, 1, "LEADS_TO")},
    ),
    (
        "Tamil, no cue",
        "பழைய காரை விற்றுவிட்டேன். பஸ்ஸில் வேலைக்கு போகிறேன்",
        [_f(CAR, leads_to=[BUS]), _f(BUS)],
        set(),
    ),
    (
        "Tanglish cue adhanala",
        "old car-a vithuten, adhanala bus la office poren",
        [_f(CAR, leads_to=[BUS]), _f(BUS)],
        {(0, 1, "LEADS_TO")},
    ),
    (
        "Tanglish cue apram",
        "car vithuten apram bus la poren",
        [_f(CAR, leads_to=[BUS]), _f(BUS)],
        {(0, 1, "LEADS_TO")},
    ),
    (
        "Tamil words, reason in English from the extractor",
        "Firebase ரொம்ப காஸ்ட்லி ஆயிடுச்சு, அதனால Supabase-க்கு மாத்திட்டேன்",
        [_f(SUPABASE, reason="Firebase got too expensive"), _f(FIREBASE)],
        {(0, 1, "BECAUSE")},
    ),
    (
        "both kinds from one message",
        "Firebase got too expensive so I moved FarmLink to Supabase, then rewrote the sync",
        [
            _f(SUPABASE, reason="Firebase got too expensive", leads_to=[SYNC]),
            _f(FIREBASE),
            _f(SYNC),
        ],
        {(0, 1, "BECAUSE"), (0, 2, "LEADS_TO")},
    ),
    (
        "leads_to naming a fact of another message",
        "I sold the old car, so now I take the bus to work",
        [_f(CAR, leads_to=["The owner bought a scooter last year."]), _f(BUS)],
        set(),
    ),
]


def _with_said(facts, said):
    for fact in facts:
        fact.source_text = said
    return facts


@pytest.mark.parametrize(("name", "said", "facts", "expected"), CASES, ids=[c[0] for c in CASES])
def test_cases(name, said, facts, expected):
    outcome = typed_links.propose(_with_said(facts, said))
    got = {(p.source, p.target, p.link_type) for p in outcome.proposed}
    assert got == expected, name
    for p in outcome.proposed:
        assert p.properties["why"].startswith(typed_links.WHY_PREFIX)


def test_cases_cover_tamil_and_tanglish():
    non_english = [c for c in CASES if any(ord(ch) > 127 for ch in c[1]) or "adhanala" in c[1]]
    assert len(non_english) * 4 >= len(CASES)


def test_link_carries_the_lower_confidence_and_the_rule():
    said = "I sold the old car, so now I take the bus to work"
    facts = [
        _f(CAR, leads_to=[BUS], said=said, confidence=0.95),
        _f(BUS, said=said, confidence=0.7),
    ]
    (link,) = typed_links.propose(facts).proposed
    assert link.strength == 0.7
    assert link.properties == {"why": "extraction:leads_to", "cue": "so"}


def test_because_overlap_needs_most_of_the_reason():
    assert typed_links.reason_overlap("Firebase got too expensive", FIREBASE) >= 0.6
    assert typed_links.reason_overlap("Firebase got too expensive", "Firebase is free.") < 0.6
    # Only "owner" in common: the frame word every fact has is no evidence.
    assert typed_links.reason_overlap("the owner was tired", "The owner sold the car.") == 0.0


def test_tamil_tokens_keep_their_vowel_signs():
    assert typed_links.tokens("அதனால், நான் போனேன்.") == ["அதனால்", "நான்", "போனேன்"]
    assert typed_links.sequence_cue("அதனாலே வந்தேன்") == "அதனாலே"


def test_a_refused_proposal_says_why():
    said = "I sold the old car. I take the bus."
    outcome = typed_links.propose([_f(CAR, leads_to=[BUS], said=said), _f(BUS, said=said)])
    assert outcome.proposed == []
    assert outcome.refused == [(0, "no sequence cue in the text")]
    said = "I sold the old car, so I take the bus."
    outcome = typed_links.propose([_f(CAR, leads_to=["elsewhere"], said=said), _f(BUS, said=said)])
    assert outcome.refused == [(0, "target is not another fact of this message")]


# ── writing: only this message's new memories ─────────────────────────────────


def _mem(tier="self"):
    return SimpleNamespace(id=uuid.uuid4(), trust_tier=tier)


@pytest.fixture
def created(monkeypatch):
    calls = []

    async def fake_create_link(source, target, link_type, **kw):
        calls.append((source, target, link_type, kw))
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(typed_links.links, "create_link", fake_create_link)
    return calls


def _because_pair():
    return [_f(SUPABASE, reason="Firebase got too expensive"), _f(FIREBASE)]


@pytest.mark.asyncio
async def test_new_memories_of_one_message_are_linked(created):
    a, b = _mem(), _mem()
    facts = _because_pair()
    n = await typed_links.link_message("t1", list(zip(facts, [a, b], strict=True)), {a.id, b.id})
    assert n == 1
    (source, target, kind, kw) = created[0]
    assert (source, target, kind) == (a.id, b.id, "BECAUSE")
    assert kw["tenant_id"] == "t1"
    assert kw["properties"]["why"] == "extraction:because"


@pytest.mark.asyncio
async def test_a_memory_from_an_earlier_message_is_never_linked(created):
    """The fact matched an existing memory (a duplicate, maybe the owner's own):
    it was not stored new by this message, so no link touches it."""
    a, earlier = _mem(), _mem()  # same tier: only "new in this message" refuses it
    facts = _because_pair()
    assert (
        await typed_links.link_message("t1", list(zip(facts, [a, earlier], strict=True)), {a.id})
        == 0
    )
    assert created == []


@pytest.mark.asyncio
async def test_memories_of_different_trust_tiers_are_not_linked(created):
    a, b = _mem(tier="self"), _mem(tier="external")
    facts = _because_pair()
    assert (
        await typed_links.link_message("t1", list(zip(facts, [a, b], strict=True)), {a.id, b.id})
        == 0
    )
    assert created == []


@pytest.mark.asyncio
async def test_two_facts_merged_into_one_memory_get_no_self_link(created):
    a = _mem()
    facts = _because_pair()
    assert await typed_links.link_message("t1", list(zip(facts, [a, a], strict=True)), {a.id}) == 0


@pytest.mark.asyncio
async def test_an_existing_link_or_a_failure_never_fails_the_save(monkeypatch):
    async def exists(*a, **kw):
        raise ConflictError("exists")

    monkeypatch.setattr(typed_links.links, "create_link", exists)
    a, b = _mem(), _mem()
    assert (
        await typed_links.link_message(
            "t", list(zip(_because_pair(), [a, b], strict=True)), {a.id, b.id}
        )
        == 0
    )

    async def boom(*a, **kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(typed_links.links, "create_link", boom)
    assert (
        await typed_links.link_message(
            "t", list(zip(_because_pair(), [a, b], strict=True)), {a.id, b.id}
        )
        == 0
    )


# ── the flag, in MemoryManager.store_facts ────────────────────────────────────


def _manager(monkeypatch, memories):
    mgr = mm.MemoryManager.__new__(mm.MemoryManager)
    by_content = dict(memories)

    async def fake_process(
        fact, context, source, skip_dedup=False, trust_tier=None, embedding=None
    ):
        memory = by_content[fact.content]
        new = mm._new_this_message.get()
        if new is not None:  # what the real _process_fact does for a row it stored
            new.add(memory.id)
        return memory

    async def fake_embed(text):
        return None

    async def no_assoc(memories):
        return None

    monkeypatch.setattr(mgr, "_process_fact", fake_process)
    monkeypatch.setattr(mgr, "_generate_embedding", fake_embed)
    monkeypatch.setattr(mm, "_link_said_together", no_assoc)
    return mgr


@pytest.mark.asyncio
async def test_flag_off_writes_no_typed_links(monkeypatch, created):
    monkeypatch.setattr(settings, "ingest_typed_links", False)
    a, b = _mem(), _mem()
    mgr = _manager(monkeypatch, [(SUPABASE, a), (FIREBASE, b)])
    with tenant_scope("t-typed"):
        stored = await mgr.store_facts(_because_pair(), trust_tier="self")
    assert stored == [a, b]
    assert created == []
    assert mm._new_this_message.get() is None


@pytest.mark.asyncio
async def test_flag_on_links_the_message(monkeypatch, created):
    monkeypatch.setattr(settings, "ingest_typed_links", True)
    a, b = _mem(), _mem()
    mgr = _manager(monkeypatch, [(SUPABASE, a), (FIREBASE, b)])
    with tenant_scope("t-typed"):
        stored = await mgr.store_facts(_because_pair(), trust_tier="self")
    assert stored == [a, b]
    assert [(c[0], c[1], c[2], c[3]["tenant_id"]) for c in created] == [
        (a.id, b.id, "BECAUSE", "t-typed")
    ]
    assert mm._new_this_message.get() is None  # reset after the message


# ── the extraction request and its parsing ────────────────────────────────────


class _Client:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.sent: list[dict] = []

    async def chat_local_only(self, **kwargs) -> str:
        self.sent.append(kwargs)
        return self.reply


_REPLY = json.dumps(
    {
        "facts": [
            {
                "content": CAR,
                "fact_type": "fact",
                "confidence": 0.9,
                "entities": [],
                "leads_to": [2, 0, 9, "1", True],
            },
            {"content": "", "fact_type": "fact", "confidence": 0.9, "entities": []},
            {"content": BUS, "fact_type": "fact", "confidence": 0.9, "entities": []},
        ]
    }
)


@pytest.mark.asyncio
@pytest.mark.parametrize("structured", [True, False])
async def test_flag_off_request_and_facts_are_as_before(monkeypatch, structured):
    monkeypatch.setattr(settings, "ingest_typed_links", False)
    monkeypatch.setattr(settings, "lm_structured_output", structured)
    client = _Client(_REPLY)
    facts = await LLMExtractor(lm_client=client)._extract_local("I sold the car, so I take the bus")
    assert extraction_schema() is _EXTRACTION_SCHEMA
    assert "leads_to" not in json.dumps(client.sent, ensure_ascii=False)
    assert [f.leads_to for f in facts] == [[], []]


@pytest.mark.asyncio
async def test_flag_on_asks_for_leads_to_and_maps_positions_to_facts(monkeypatch):
    monkeypatch.setattr(settings, "ingest_typed_links", True)
    monkeypatch.setattr(settings, "lm_structured_output", True)
    client = _Client(_REPLY)
    facts = await LLMExtractor(lm_client=client)._extract_local("I sold the car, so I take the bus")
    (sent,) = client.sent
    schema = sent["response_format"]["json_schema"]["schema"]
    assert "leads_to" in schema["properties"]["facts"]["items"]["properties"]
    assert "leads_to" in sent["messages"][-1]["content"]
    # Position 2 is the bus fact (the empty item 1 was dropped); itself, out of
    # range, a string and a bool are left out.
    assert [f.leads_to for f in facts] == [[BUS], []]
    # One request, as before: no extra model call.
    assert len(client.sent) == 1
    # The module constant is untouched.
    assert "leads_to" not in _EXTRACTION_SCHEMA["properties"]["facts"]["items"]["properties"]
