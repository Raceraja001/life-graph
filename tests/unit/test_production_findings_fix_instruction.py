import re

from life_graph.services.production_findings import fix_instruction

# Helper to extract the 'What was observed' section content


def extract_observed_section(message: str) -> str:
    """Return the string inside the 'What was observed:' section.
    The format is: 'What was observed:\n<content>\n\n', so we split on that
    marker and strip the trailing newlines.
    """
    pattern = r"What was observed:\n(.*?)\n\n"
    match = re.search(pattern, message, re.DOTALL)
    return match.group(1) if match else ""


class TestFixInstruction:
    def test_basic_includes_kind_title_and_detail(self):
        kind = "error"
        title = "Crash on startup"
        detail = "The app crashed due to a NullPointerException."
        message = fix_instruction(kind, title, detail)

        # Basic structure
        assert f"A production check failed ({kind}): {title}" in message
        assert "What was observed:" in message
        assert detail in message

    def test_truncates_long_detail(self):
        kind = "timeout"
        title = "Long running request"
        long_detail = "x" * 5000  # 5000 chars
        message = fix_instruction(kind, title, long_detail)

        observed = extract_observed_section(message)
        # Should be truncated to 4000 chars
        assert len(observed) == 4000
        assert observed == "x" * 4000

    def test_strips_whitespace_and_newlines(self):
        kind = "bug"
        title = "Unexpected output"
        detail = "   \n  Some details with leading and trailing whitespace   \n  "
        message = fix_instruction(kind, title, detail)

        observed = extract_observed_section(message)
        # After stripping, whitespace and newlines should be removed
        assert observed == "Some details with leading and trailing whitespace"

    def test_empty_detail(self):
        kind = "info"
        title = "No error"
        detail = ""
        message = fix_instruction(kind, title, detail)

        observed = extract_observed_section(message)
        # Empty detail should result in an empty string for the section
        assert observed == ""

    def test_detail_with_internal_newlines(self):
        kind = "format"
        title = "Wrong format"
        detail = "Line1\nLine2\nLine3"
        message = fix_instruction(kind, title, detail)

        observed = extract_observed_section(message)
        assert observed == detail
