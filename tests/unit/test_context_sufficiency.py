"""The snapshot's word-level sufficiency check (services/memory/sufficiency.py).

Pure functions: no database, no model. The snapshot-level behaviour (what
``insufficient`` and ``missing`` say) is in tests/unit/test_context_snapshot.py.
"""

from __future__ import annotations

import pytest

from life_graph.services.memory import sufficiency
from life_graph.services.memory.sufficiency import asks_for_gaps, assess, query_terms, stems_match

O10 = (
    "What information is missing before you can reliably recommend whether I should take a "
    "second home loan?"
)


def _texts(query: str) -> list[str]:
    return [t.text for t in query_terms(query)]


@pytest.mark.parametrize(
    ("query", "terms"),
    [
        # "score" is a slot noun: it asks for a value of the subject, credit.
        ("What is my credit score?", ["credit"]),
        ("How do I take my coffee?", ["coffee"]),
        ("What is my current job title?", ["job"]),
        ("What tasks do I have on the Billing migration?", ["tasks", "billing migration"]),
        (O10, ["second home loan"]),
        # Punctuation ends a term; a short number is dropped, a year is kept.
        ("Ila's school fee, and which school?", ["ilas school fee", "school"]),
        ("Can I buy a laptop for ₹1,20,000 in 2027?", ["buy", "laptop", "2027"]),
        ("what's up?", []),
    ],
)
def test_terms_are_runs_of_content_words(query, terms):
    assert _texts(query) == terms


def test_tamil_words_stay_whole():
    # Tamil vowel signs are combining marks; a \\w split would cut "பள்ளி" apart.
    (term,) = query_terms("பள்ளி கட்டணம்?")
    assert term.words == ("பள்ளி", "கட்டணம்")
    assert term.needed == 2


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("financial", "financ", True),  # "financial" / "finance" (stemmed)
        ("responsibl", "responsibility", True),
        ("kattanam", "kattanathai", True),  # a case ending on a long word
        ("credit", "credential", False),
        ("car", "card", False),  # short words must be equal
        ("job", "job", True),
    ],
)
def test_stems_match_by_equality_or_a_long_shared_prefix(a, b, same):
    assert stems_match(a, b) is same


def test_one_generic_word_is_not_support_for_a_longer_term():
    # The D7 case: "scored 68%" shares only "score" with "credit score", and
    # "score" is not a term word at all.
    found = assess("What is my credit score?", ["The owner scored 68% on her first AWS test."])
    assert found.unsupported and found.missing == ("credit",)
    # Two words of a term must be in the same item, not spread over two.
    split = assess("What is my blood group?", ["blood test results", "the WhatsApp group"])
    assert split.unsupported and split.missing_terms == ("blood group",)
    together = assess("What is my blood group?", ["My blood group is O positive."])
    assert not together.unsupported and together.supported == ("blood group",)


def test_any_one_supported_term_is_enough():
    found = assess("Am I looking for a new job?", ["I'm not looking for a new job."])
    assert found.supported == ("looking", "new job") and not found.unsupported
    partly = assess("How do I take my coffee at work?", ["filter coffee without sugar"])
    assert partly.supported == ("coffee",) and partly.missing_terms == ("work",)


def test_a_partly_covered_term_reports_the_words_its_best_item_lacks():
    found = assess(O10, ["Home loan statement: EMI of 42,000 a month", "every second Saturday"])
    assert found.supported == ("second home loan",)
    assert found.missing_words == (("second", "second home loan"),)
    assert found.missing == ("second",)
    assert found.describe_missing() == "'second' (in 'second home loan')"


def test_no_terms_means_not_judged():
    found = assess("what's up?", ["anything"])
    assert not found.judged and not found.unsupported and found.missing == ()


def test_no_items_leaves_every_term_missing():
    found = assess("What is my credit score?", [])
    assert found.unsupported and found.missing == ("credit",)


@pytest.mark.parametrize(
    ("query", "gaps"),
    [
        (O10, True),
        ("What's missing?", True),
        ("What am I missing for the visa?", True),
        ("What else do you need to know?", True),
        ("Which facts are unknown about the loan?", True),
        # "missing" naming a thing is not a question about gaps (F4).
        ("Which project is held up by the missing PayFlow sandbox access?", False),
        ("What is my credit score?", False),
    ],
)
def test_asks_for_gaps(query, gaps):
    assert asks_for_gaps(query) is gaps


def test_the_kind_words_are_plain_words():
    # They are matched like any other word of the item's text.
    words = sufficiency.support_words(sufficiency.KIND_WORDS["intention"])
    assert not assess(
        "Which commitments are open?", [sufficiency.KIND_WORDS["intention"]]
    ).unsupported
    assert "deadlin" in sufficiency.support_words(sufficiency.DUE_WORDS)
    assert "commitment" in words
