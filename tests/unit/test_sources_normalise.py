from life_graph.services.sources import normalise

# Basic URL normalization


def test_normalise_basic_url():
    assert normalise("https://example.com/path/") == "example.com/path"
    assert normalise("https://example.com/path?query=1") == "example.com/path?query=1"


# Handling www prefix and trailing slash


def test_normalise_www_and_trailing_slash():
    assert normalise("https://www.example.com") == "example.com"
    assert normalise("https://www.example.com/") == "example.com"


# Trailing punctuation is stripped before parsing


def test_normalise_trailing_punctuation():
    assert normalise("https://example.com/path.,") == "example.com/path"
    assert normalise("https://example.com/path?x=1,") == "example.com/path?x=1"
    assert normalise("https://example.com/path#frag.") == "example.com/path"


# Uppercase hosts are lowercased and www removed


def test_normalise_uppercase_and_www():
    assert normalise("HTTPS://WWW.EXAMPLE.COM/PATH/") == "example.com/PATH"


# URLs without scheme are treated as host/path


def test_normalise_no_scheme():
    assert normalise("example.com/path") == "example.com/path"
    assert normalise("example.com/") == "example.com"


# Empty string returns empty string


def test_normalise_empty_string():
    assert normalise("") == ""


# URLs with query and fragment are correctly handled


def test_normalise_query_and_fragment():
    assert normalise("https://example.com/path?x=1&y=2#frag") == "example.com/path?x=1&y=2"
    assert normalise("https://example.com/path?x=1&y=2#frag,") == "example.com/path?x=1&y=2"
