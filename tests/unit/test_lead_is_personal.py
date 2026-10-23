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
