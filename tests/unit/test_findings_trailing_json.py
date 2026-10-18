from life_graph.services.findings_bridge import trailing_json_array


def test_trailing_json_array_found():
    text = "Hello world [1, 2, 3]"
    result = trailing_json_array(text)
    assert result is not None
    start, end, array = result
    # The array should be parsed correctly
    assert array == [1, 2, 3]
    # The slice of text that was parsed should match the JSON string
    assert text[start:end].strip() == "[1, 2, 3]"


def test_trailing_json_array_with_fence():
    text = "Update: [42]```"
    result = trailing_json_array(text)
    assert result is not None
    start, end, array = result
    assert array == [42]
    # The trailing fence should be ignored
    assert text[end:].strip() == "```"


def test_trailing_json_array_none():
    text = "Just some text without JSON"
    assert trailing_json_array(text) is None


def test_trailing_json_array_malformed():
    text = "Broken [1, 2, 3"
    assert trailing_json_array(text) is None


def test_trailing_json_array_not_trailing():
    text = "[1, 2] middle"
    assert trailing_json_array(text) is None
