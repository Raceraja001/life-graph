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
    for text in (
        "What is the capital of France?",
        "how do I reverse a list in Python",
        "how do I save a dataframe to csv",
    ):
        assert is_personal(text) is None, text


def test_asking_jarvis_to_keep_something_runs_locally():
    # memory_save is never offered to a cloud model and the phone's extractor
    # skips explicit saves, so one of these routed "general" was saved by nothing.
    for text in (
        "note that the school fees are due Friday",
        "Don't forget the school fees are due Friday",
        "keep in mind I prefer morning meetings",
        "make a note: the gate opens at six",
        "save this: the gate opens at six",
        "jot down that the gate opens at six",
        "write this down, the gate opens at six",
    ):
        assert is_personal(text), text
