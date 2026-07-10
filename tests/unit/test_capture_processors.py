"""Unit tests for capture spine processors — decision & procedure detection."""

from __future__ import annotations

import pytest

from life_graph.services.capture_processors import CaptureProcessors


class TestDecisionDetection:
    """Test regex-based decision candidate extraction."""

    @pytest.fixture()
    def processor(self) -> CaptureProcessors:
        return CaptureProcessors()

    def test_decided_to(self, processor: CaptureProcessors) -> None:
        decisions = processor._detect_decisions("I decided to use FastAPI for the backend")
        assert len(decisions) >= 1
        assert any("FastAPI" in d for d in decisions)

    def test_going_with(self, processor: CaptureProcessors) -> None:
        decisions = processor._detect_decisions("We're going with PostgreSQL instead of MongoDB")
        assert len(decisions) >= 1
        assert any("PostgreSQL" in d for d in decisions)

    def test_lets_use(self, processor: CaptureProcessors) -> None:
        decisions = processor._detect_decisions("let's use Redis for caching")
        assert len(decisions) >= 1
        assert any("Redis" in d for d in decisions)

    def test_the_plan_is(self, processor: CaptureProcessors) -> None:
        decisions = processor._detect_decisions("the plan is to deploy on Friday")
        assert len(decisions) >= 1
        assert any("deploy" in d.lower() for d in decisions)

    def test_chose_over(self, processor: CaptureProcessors) -> None:
        decisions = processor._detect_decisions("I chose Vite over Webpack for bundling")
        assert len(decisions) >= 1
        assert any("Vite" in d for d in decisions)

    def test_switched_to(self, processor: CaptureProcessors) -> None:
        decisions = processor._detect_decisions("We switched to TypeScript last month")
        assert len(decisions) >= 1
        assert any("TypeScript" in d for d in decisions)

    def test_final_decision(self, processor: CaptureProcessors) -> None:
        decisions = processor._detect_decisions("final decision: we ship on Monday")
        assert len(decisions) >= 1

    def test_no_decisions_in_plain_text(self, processor: CaptureProcessors) -> None:
        decisions = processor._detect_decisions("The weather is nice today")
        assert len(decisions) == 0

    def test_dedup_same_decision(self, processor: CaptureProcessors) -> None:
        text = "I decided to use React. Yes, I decided to use React."
        decisions = processor._detect_decisions(text)
        # Should deduplicate
        assert len(decisions) == 1

    def test_multiple_decisions(self, processor: CaptureProcessors) -> None:
        text = (
            "I decided to use FastAPI for the backend. "
            "Let's use React for the frontend. "
            "We're going with Docker for deployment."
        )
        decisions = processor._detect_decisions(text)
        assert len(decisions) >= 2

    def test_short_decisions_filtered(self, processor: CaptureProcessors) -> None:
        """Decisions shorter than 5 chars are filtered out."""
        decisions = processor._detect_decisions("I decided to go")
        # "go" is only 2 chars, should be filtered
        assert all(len(d) > 5 for d in decisions)


class TestProcedureDetection:
    """Test regex-based procedure candidate extraction."""

    @pytest.fixture()
    def processor(self) -> CaptureProcessors:
        return CaptureProcessors()

    def test_every_time_pattern(self, processor: CaptureProcessors) -> None:
        procs = processor._detect_procedures(
            "Every time I deploy, I run the test suite first"
        )
        assert len(procs) >= 1

    def test_always_start_by(self, processor: CaptureProcessors) -> None:
        procs = processor._detect_procedures(
            "I always start by reading the spec document"
        )
        assert len(procs) >= 1
        assert any("reading" in p.lower() for p in procs)

    def test_my_process_is(self, processor: CaptureProcessors) -> None:
        procs = processor._detect_procedures(
            "My usual process for code review is checking tests first"
        )
        assert len(procs) >= 1

    def test_no_procedures_in_plain_text(self, processor: CaptureProcessors) -> None:
        procs = processor._detect_procedures("The server is running on port 8000")
        assert len(procs) == 0

    def test_step_pattern(self, processor: CaptureProcessors) -> None:
        procs = processor._detect_procedures("Step 1: Set up the database connection")
        assert len(procs) >= 1


class TestCaptureProcessorsSubscription:
    """Test the subscription lifecycle."""

    def test_subscribe_idempotent(self) -> None:
        proc = CaptureProcessors()
        assert not proc._subscribed
        proc.subscribe()
        assert proc._subscribed
        proc.subscribe()  # Should not error
        assert proc._subscribed
        proc.unsubscribe()
        assert not proc._subscribed

    def test_unsubscribe_when_not_subscribed(self) -> None:
        proc = CaptureProcessors()
        proc.unsubscribe()  # Should not error
        assert not proc._subscribed
