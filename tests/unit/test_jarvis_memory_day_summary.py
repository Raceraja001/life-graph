from life_graph.services.jarvis_memory import day_summary


def test_day_summary_jarvis_with_colon():
    content = "Conversations with Jarvis on Sunday 25 October 2026: The user asked about memory summaries."
    result = day_summary(content)
    assert result == "The user asked about memory summaries."


def test_day_summary_work_with_colon():
    content = "Work with the coding assistant on Monday 26 October 2026: The developer fixed a bug."
    result = day_summary(content)
    assert result == "The developer fixed a bug."


def test_day_summary_no_label():
    content = "This is just a plain memory without a label."
    result = day_summary(content)
    assert result == content


def test_day_summary_label_no_colon():
    content = "Conversations with Jarvis on Sunday 25 October 2026"
    result = day_summary(content)
    assert result == content


def test_day_summary_empty_string():
    result = day_summary("")
    assert result == ""
