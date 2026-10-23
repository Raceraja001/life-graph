from life_graph.services.lead import is_personal


def test_is_personal_empty_returns_none():
    """Empty input should return None."""
    assert is_personal("") is None


def test_is_personal_mentions_match_returns_mention():
    """A string that matches the _PERSONAL regex should return a mention.
    The matched substring is lower‑cased and quoted."""
    text = "My calendar is full"
    result = is_personal(text)
    assert result == "mentions 'my calendar'"


def test_is_personal_carries_personal_detail_returns_carries():
    """If the text contains a personal detail that scrub replaces, the function
    should indicate that it carries a personal detail."""
    text = "Contact me at test@example.com"
    result = is_personal(text)
    assert result == "carries a personal detail"


def test_a_question_about_the_owners_own_anything_is_personal():
    # Went to the cloud model, which cannot see memories (2026-10-23).
    for text in (
        "What is my test locker code?",
        "what's my wifi name",
        "Where is my spare key?",
        "When was my last service?",
        "my home address please",
    ):
        assert is_personal(text), text


def test_general_questions_stay_general():
    for text in ("What is the capital of France?", "how do I reverse a list in Python"):
        assert is_personal(text) is None, text
