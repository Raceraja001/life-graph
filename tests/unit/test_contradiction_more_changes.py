# tests/unit/test_contradiction_more_changes.py
"""Unit tests for the "More changes" contradiction rules (2026-11-28).

The detector used to catch only "X is A" → "X is B". These rules add a
"not" ("no longer eats meat"), a new amount ("₹10,000" → "₹15,000"), a new
person in a one-holder role ("Divya is my manager now"), a new object said
as a change ("uses Linear now") and the Tamil and Tanglish forms. They run
only with ``settings.ingest_supersession_tiers`` on, so prod (flag off) is
unchanged. Every hit becomes an owner approval, so the near misses below
matter as much as the hits.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.config import settings
from life_graph.services.contradiction import (
    ContradictionDetector,
    _check_more_changes,
    _d10_tokens,
    differs_by_negation,
    differs_in_detail,
)

_EMB = [0.1, 0.2, 0.3]

# (new, existing, conflict_type)
HITS = [
    # A "not" or a stop, English
    ("The owner no longer eats meat.", "The owner eats meat.", "negation"),
    ("The owner does not use Jira.", "The owner uses Jira.", "negation"),
    ("The owner doesn't use Jira.", "The owner uses Jira.", "negation"),
    ("The owner has stopped eating meat.", "The owner eats meat.", "negation"),
    ("The owner has stopped smoking.", "The owner smokes.", "negation"),
    ("The owner eats meat again.", "The owner no longer eats meat.", "negation"),
    ("The owner is not allergic to peanuts.", "The owner is allergic to peanuts.", "negation"),
    (
        "The owner never drinks coffee after 6 pm.",
        "The owner drinks coffee after 6 pm.",
        "negation",
    ),
    ("The owner no longer lives in Madurai.", "The owner lives in Madurai.", "negation"),
    # Tamil and Tanglish
    ("நான் காபி குடிப்பதில்லை.", "நான் காபி குடிக்கிறேன்.", "negation"),
    ("நான் கறி சாப்பிட மாட்டேன்.", "நான் கறி சாப்பிடுவேன்.", "negation"),
    ("நான் காபி குடிப்பதை நிறுத்திவிட்டேன்.", "நான் காபி குடிக்கிறேன்.", "negation"),
    ("Naan meat saapda maatten.", "Naan meat saapduven.", "negation"),
    ("Naan ippo coffee kudikkradhilla.", "Naan coffee kudikkiren.", "negation"),
    # A new amount
    (
        "The owner invests ₹15,000 a month in an index fund SIP.",
        "The owner invests ₹10,000 a month in an index fund SIP.",
        "value_change",
    ),
    (
        "The owner runs 8 km on Monday, Wednesday and Friday mornings.",
        "The owner runs 5 km on Monday, Wednesday and Friday mornings.",
        "value_change",
    ),
    ("The owner has 3 dogs.", "The owner has 2 dogs.", "value_change"),
    ("நான் மாதம் ₹15,000 சேமிக்கிறேன்.", "நான் மாதம் ₹10,000 சேமிக்கிறேன்.", "value_change"),
    ("Naan maasam 15k save panren.", "Naan maasam 10k save panren.", "value_change"),
    # A new person in a one-holder role
    ("Divya is my manager now.", "Suresh is my manager.", "value_change"),
    ("Divya is the owner's manager now.", "Suresh is the owner's manager.", "value_change"),
    ("Ippo en manager Divya dhaan.", "En manager Suresh.", "value_change"),
    # A new object, said as a change
    (
        "The owner's team uses Linear for tickets now.",
        "The owner's team uses Jira for tickets.",
        "value_change",
    ),
    ("The owner drives a Nexon these days.", "The owner drives a Swift.", "value_change"),
    # Tamil and Tanglish "only X I like"
    ("Enakku coffee dhaan pidikkum.", "Enakku tea dhaan pidikkum.", "preference_change"),
    ("எனக்கு காபி தான் பிடிக்கும்.", "எனக்கு டீ தான் பிடிக்கும்.", "preference_change"),
]

# (new, existing): both can be true, or the subject or scope differs.
NEAR_MISSES = [
    # Narrower, not opposite
    ("I don't eat meat on Tuesdays.", "I eat meat."),
    ("I eat meat.", "I don't eat meat on Tuesdays."),
    ("The owner does not eat meat on Tuesdays and Saturdays.", "The owner eats meat."),
    # Another subject, a hedge, both negated
    ("Ravi does not eat meat.", "The owner eats meat."),
    ("The owner might not eat meat.", "The owner eats meat."),
    ("The owner doesn't eat fish.", "The owner doesn't eat meat."),
    ("The owner will not eat meat at the wedding.", "The owner eats meat."),
    # Past: "I drank coffee" is no clash with "I don't drink coffee"
    ("நான் காபி குடித்தேன்.", "நான் காபி குடிப்பதில்லை."),
    ("Naan coffee kudichen.", "Naan coffee kudikkradhilla."),
    # Amounts that can both be true
    (
        "The owner scored 75% on the AWS practice test.",
        "The owner scored 68% on the AWS practice test.",
    ),
    ("The owner paid ₹600 for the cab.", "The owner paid ₹500 for the cab."),
    (
        "The owner has finished chapters 1 to 8 of the Rust book.",
        "The owner has finished chapters 1 to 5 of the Rust book.",
    ),
    ("Bus 23 goes to the office.", "Bus 21 goes to the office."),
    (
        "The owner has a meeting at 4 pm on 3 December.",
        "The owner has a meeting at 3 pm on 3 December.",
    ),
    (
        "The owner pays ₹45,000 EMI until March 2034.",
        "The owner pays ₹42,000 EMI until March 2034.",
    ),
    (
        "Arjun's take-home pay is ₹65,000 a month.",
        "The owner's take-home salary is ₹1,50,000 a month.",
    ),
    ("The owner also invests ₹15,000 a month.", "The owner invests ₹10,000 a month."),
    # Roles many people hold, or a different sentence
    ("Divya is my friend now.", "Suresh is my friend."),
    ("Divya is my manager's wife.", "Suresh is my manager."),
    ("Divya is my mentor.", "Divya is my manager."),
    ("Diya (the owner's niece) is 7.", "Ila (the owner's daughter) is 7."),
    # Many-object verbs, no change word, two changes, an activity
    ("The owner speaks English now.", "The owner speaks Tamil."),
    ("The owner uses Linear for tickets.", "The owner uses Jira for tickets."),
    ("The owner uses VS Code now.", "The owner uses Python for scripts."),
    ("Arun uses Linear now.", "Ravi uses Jira."),
    ("The owner is learning Go now.", "The owner is learning Rust."),
    ("The owner also uses Linear now.", "The owner uses Jira."),
    ("The owner's team used Linear for tickets now.", "The owner's team used Jira for tickets."),
    # Tanglish "like" without the "only" emphasis
    ("Enakku coffee pidikkum.", "Enakku tea pidikkum."),
    # The same statement
    ("The owner eats meat.", "The owner eats meat."),
]


@pytest.fixture
def tiers_on(monkeypatch):
    monkeypatch.setattr(settings, "ingest_supersession_tiers", True)


@pytest.fixture
def tiers_off(monkeypatch):
    monkeypatch.setattr(settings, "ingest_supersession_tiers", False)


def _memory(content: str, **props) -> SimpleNamespace:
    return SimpleNamespace(id="m-1", content=content, embedding=_EMB, properties=props)


async def _check(new: str, old: str, new_props: dict | None = None, **old_props):
    detector = ContradictionDetector(store=None)  # type: ignore[arg-type]
    return await detector.check_candidates(
        new, [_memory(old, **old_props)], _EMB, new_properties=new_props or {}
    )


@pytest.mark.parametrize(("new", "old", "kind"), HITS)
def test_rule_flags_the_change(new, old, kind):
    found = _check_more_changes(new, old)
    assert found is not None, (new, old)
    assert found[0] == kind


@pytest.mark.parametrize(("new", "old"), NEAR_MISSES)
def test_rule_leaves_near_misses_alone(new, old):
    assert _check_more_changes(new, old) is None, (new, old)


@pytest.mark.parametrize(("new", "old", "kind"), HITS)
async def test_detector_suggests_a_supersede_with_the_flag_on(tiers_on, new, old, kind):
    found = await _check(new, old)
    assert len(found) == 1
    assert found[0].conflict_type == kind
    assert found[0].resolution == "supersede"


@pytest.mark.parametrize(("new", "old"), NEAR_MISSES)
async def test_detector_ignores_near_misses_with_the_flag_on(tiers_on, new, old):
    assert await _check(new, old) == []


@pytest.mark.parametrize(("new", "old", "kind"), HITS)
async def test_flag_off_keeps_the_old_detector(tiers_off, new, old, kind):
    """Prod runs with the flag off: none of the new rules may fire there."""
    assert await _check(new, old) == []


async def test_scope_still_keeps_both(tiers_on):
    found = await _check(
        "The owner does not use Kafka.",
        "The owner uses Kafka.",
        new_props={"project": "jarvis"},
        project="farmlink",
    )
    assert [c.resolution for c in found] == ["scope"]


async def test_english_preference_change_is_caught_with_the_flag_off(tiers_off):
    """'prefers tea' → 'prefers coffee' was already the entity swap."""
    found = await _check(
        "The owner prefers coffee in the morning.", "The owner prefers tea in the morning."
    )
    assert [c.conflict_type for c in found] == ["preference_change"]


def test_merge_guard_sees_tamil_negation_only_with_the_flag(monkeypatch):
    a, b = "நான் காபி குடிப்பதில்லை.", "நான் காபி குடிக்கிறேன்."
    monkeypatch.setattr(settings, "ingest_supersession_tiers", False)
    assert differs_by_negation(a, b) is False
    monkeypatch.setattr(settings, "ingest_supersession_tiers", True)
    assert differs_by_negation(a, b) is True


def test_merge_guard_keeps_tanglish_preference_apart_only_with_the_flag(monkeypatch):
    a, b = "Enakku coffee dhaan pidikkum.", "Enakku tea dhaan pidikkum."
    monkeypatch.setattr(settings, "ingest_supersession_tiers", False)
    assert differs_in_detail(a, b) is False
    monkeypatch.setattr(settings, "ingest_supersession_tiers", True)
    assert differs_in_detail(a, b) is True


def test_tokens_keep_tamil_words_and_numbers_whole():
    assert _d10_tokens("பள்ளி கட்டணம் ₹1,50,000") == ["பள்ளி", "கட்டணம்", "1,50,000"]
    assert _d10_tokens("Chennai-la 10k, owner's") == ["chennai", "la", "10", "k", "owners"]
