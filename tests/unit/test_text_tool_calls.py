import pytest

from life_graph.drivers.local import _TEXT_TOOL_CALL_MARKERS, _looks_like_text_tool_calls


@pytest.mark.parametrize("marker", _TEXT_TOOL_CALL_MARKERS)
def test_looks_like_text_tool_calls_with_marker(marker: str) -> None:
    """Each marker should cause the function to return True."""
    output = f"Here is a call: {marker} and some more text."
    assert _looks_like_text_tool_calls(output) is True


def test_looks_like_text_tool_calls_without_marker() -> None:
    """A plain reply without any marker should return False."""
    output = "I changed the function and the tests pass."
    assert _looks_like_text_tool_calls(output) is False


def test_looks_like_text_tool_calls_empty_string() -> None:
    """An empty string should also return False."""
    output = ""
    assert _looks_like_text_tool_calls(output) is False
