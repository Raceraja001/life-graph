"""Intention extraction unit tests (T-031).

Tests for the IntentionExtractor regex-based engine — pattern matching
for TODO/FIXME, 'remind me', 'I should', time/event triggers, and
priority detection. No LLM, database, or spaCy required.
"""

from __future__ import annotations

import pytest

from life_graph.extraction.intentions import IntentionExtractor


@pytest.fixture
def extractor() -> IntentionExtractor:
    """Shared IntentionExtractor instance for all tests."""
    return IntentionExtractor()


# ── Basic pattern matching ────────────────────────────────────────────────


class TestBasicPatterns:
    """Tests for core intention-pattern extraction."""

    def test_extracts_i_should(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I should refactor the auth module")
        assert len(results) > 0
        assert "refactor the auth module" in results[0]["content"].lower()
        assert results[0]["trigger_type"] in ("event", "context")

    def test_extracts_i_need_to(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I need to fix the login bug")
        assert len(results) > 0
        assert "fix the login bug" in results[0]["content"].lower()

    def test_extracts_i_will_later(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I will update the schema later")
        assert len(results) > 0
        assert "update the schema" in results[0]["content"].lower()

    def test_extracts_let_me_later(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("let me check the logs later")
        assert len(results) > 0

    def test_extracts_remind_me_to(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("Remind me to update the dependencies")
        assert len(results) > 0
        content_lower = results[0]["content"].lower()
        assert "update the dependencies" in content_lower or "dependencies" in content_lower

    def test_extracts_remind_me_about(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("remind me about the deployment checklist")
        assert len(results) > 0
        assert "deployment" in results[0]["content"].lower()

    def test_extracts_todo(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("TODO: add rate limiting to API endpoints")
        assert len(results) > 0
        assert "rate limiting" in results[0]["content"].lower()

    def test_extracts_fixme(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("FIXME: the connection pool leaks under load")
        assert len(results) > 0
        assert "connection pool" in results[0]["content"].lower()

    def test_extracts_hack(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("HACK: temporary workaround for date parsing")
        assert len(results) > 0
        assert "workaround" in results[0]["content"].lower()

    def test_no_extraction_from_normal_text(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("The database performance is good today")
        assert len(results) == 0

    def test_no_extraction_from_empty_string(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("")
        assert len(results) == 0

    def test_no_extraction_from_whitespace(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("   \n\t  ")
        assert len(results) == 0


# ── Multiple intentions ──────────────────────────────────────────────────


class TestMultipleIntentions:
    """Tests for extracting multiple intentions from a single text block."""

    def test_multiple_different_patterns(self, extractor: IntentionExtractor) -> None:
        text = "TODO: add caching. I should also refactor the query builder. FIXME: memory leak"
        results = extractor.extract(text)
        assert len(results) >= 2

    def test_two_todos(self, extractor: IntentionExtractor) -> None:
        text = "TODO: fix auth\nTODO: add tests"
        results = extractor.extract(text)
        assert len(results) >= 2

    def test_mixed_todo_and_remind(self, extractor: IntentionExtractor) -> None:
        text = "TODO: clean up imports. Remind me to review the PR."
        results = extractor.extract(text)
        assert len(results) >= 2


# ── Time trigger detection ────────────────────────────────────────────────


class TestTimeTriggers:
    """Tests for time-based trigger extraction."""

    def test_detects_tomorrow_trigger(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("Remind me to deploy by tomorrow")
        assert len(results) > 0
        time_results = [r for r in results if r.get("trigger_type") == "time"]
        assert len(time_results) > 0
        assert time_results[0]["trigger_time"] is not None

    def test_detects_today_trigger(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I need to finish this by today")
        assert len(results) > 0
        time_results = [r for r in results if r.get("trigger_type") == "time"]
        assert len(time_results) > 0

    def test_detects_next_week_trigger(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I should review the design by next week")
        assert len(results) > 0
        time_results = [r for r in results if r.get("trigger_type") == "time"]
        assert len(time_results) > 0

    def test_detects_weekday_trigger(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("Remind me to release by Friday")
        assert len(results) > 0
        time_results = [r for r in results if r.get("trigger_type") == "time"]
        assert len(time_results) > 0

    def test_no_time_trigger_without_time_phrase(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I should refactor the module")
        assert len(results) > 0
        # Should be 'event' (default), not 'time'
        assert results[0]["trigger_type"] != "time"


# ── Event / context trigger detection ─────────────────────────────────────


class TestEventTriggers:
    """Tests for event/context-based trigger extraction."""

    def test_detects_when_i_work_on(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract(
            "When I work on the auth module, remind me to fix the token refresh"
        )
        assert len(results) > 0
        ctx_results = [r for r in results if r.get("trigger_type") == "context"]
        assert len(ctx_results) > 0
        assert ctx_results[0]["context_match"] is not None

    def test_detects_when_i_open(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract(
            "When I open config.py, remind me to update the defaults"
        )
        assert len(results) > 0

    def test_detects_next_time_i(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract(
            "Next time I deploy, remind me to check the migrations"
        )
        assert len(results) > 0


# ── Priority detection ────────────────────────────────────────────────────


class TestPriorityDetection:
    """Tests for urgency/priority keyword detection."""

    def test_detects_urgent_priority(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I need to urgently fix the production bug")
        assert len(results) > 0
        high_priority = [r for r in results if r.get("priority") == "high"]
        assert len(high_priority) > 0

    def test_detects_asap_priority(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I need to deploy the hotfix ASAP")
        assert len(results) > 0
        high_priority = [r for r in results if r.get("priority") == "high"]
        assert len(high_priority) > 0

    def test_detects_critical_priority(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I need to fix the critical security issue")
        assert len(results) > 0
        high_priority = [r for r in results if r.get("priority") == "high"]
        assert len(high_priority) > 0

    def test_normal_priority_default(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I should add more unit tests")
        assert len(results) > 0
        assert results[0]["priority"] == "normal"


# ── Result structure ──────────────────────────────────────────────────────


class TestResultStructure:
    """Verify the dict structure returned by extract()."""

    def test_result_has_required_keys(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("TODO: implement caching layer")
        assert len(results) > 0
        r = results[0]
        required_keys = {
            "content",
            "trigger_type",
            "trigger_condition",
            "trigger_time",
            "context_match",
            "priority",
        }
        assert required_keys.issubset(r.keys())

    def test_content_is_stripped(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("TODO:   add caching   ")
        assert len(results) > 0
        assert not results[0]["content"].startswith(" ")
        assert not results[0]["content"].endswith(" ")

    def test_trigger_time_none_without_time_phrase(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("I should clean up imports")
        assert len(results) > 0
        assert results[0]["trigger_time"] is None

    def test_context_match_none_without_event(self, extractor: IntentionExtractor) -> None:
        results = extractor.extract("TODO: fix the bug")
        assert len(results) > 0
        assert results[0]["context_match"] is None
