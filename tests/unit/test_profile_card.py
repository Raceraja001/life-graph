"""The owner's lasting facts, always in front of Jarvis (services/profile_card.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from life_graph.services import profile_card as pc

NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)


def _m(content, *, source="capture", tier="self", props=None, valid_until=None):
    return SimpleNamespace(
        content=content,
        source_type=source,
        trust_tier=tier,
        properties=props or {},
        valid_until=valid_until,
    )


def test_only_what_the_owner_said_or_a_document_states():
    rows = [
        _m("My phone is a Realme X2 Pro.", props={"fact_type": "fact"}),
        _m("Car insurance renews in March.", source="document", tier="verified"),
        _m("Pasted page posing as a document.", source="document", tier="external"),
        _m("The owner seems to like short answers.", source="distillation", tier="verified"),
        _m("Test via proxy", source="inferred", tier="external"),
        _m("Talked about the week's plan.", source="episode", props={"kind": "episode"}),
    ]
    assert [m.content for m in pc.pick(rows, 25, NOW)] == [
        "My phone is a Realme X2 Pro.",
        "Car insurance renews in March.",
    ]


def test_events_expired_facts_and_duplicates_stay_off():
    rows = [
        _m("Prefers local HTML files.", props={"fact_type": "preference"}),
        _m("prefers   local HTML files.", props={"fact_type": "preference"}),
        _m("Fixed the login bug today.", props={"fact_type": "experience"}),
        _m("In Chennai until Friday.", valid_until=NOW - timedelta(days=1)),
        _m("Remember that my laptop is a ThinkPad"),  # stored as written: no fact type
    ]
    assert [m.content for m in pc.pick(rows, 25, NOW)] == [
        "Prefers local HTML files.",
        "Remember that my laptop is a ThinkPad",
    ]


def test_the_card_stays_short():
    rows = [_m(f"Fact number {i} " + "x" * 150, props={"fact_type": "fact"}) for i in range(40)]
    picked = pc.pick(rows, 25, NOW)
    assert 0 < len(picked) < 25
    assert len(pc.render([{"content": m.content} for m in picked])) <= pc.MAX_CHARS + 200
    assert len(pc.pick(rows, 3, NOW)) == 3


def test_render():
    out = pc.render(
        [
            {"content": "Lives in Coimbatore.", "created_at": NOW, "changes_over_time": True},
            {"content": "Blood group O+.", "created_at": NOW},
        ]
    )
    assert out.startswith(pc.HEADER)
    assert out.splitlines()[-2:] == [
        "- (as of 2026-10-29) Lives in Coimbatore.",
        "- Blood group O+.",
    ]
    assert pc.render([]) == ""


async def test_off_when_max_items_is_zero(monkeypatch):
    from life_graph.config import settings

    monkeypatch.setattr(settings, "profile_card_max_items", 0)
    assert await pc.card_items("raja") == []
