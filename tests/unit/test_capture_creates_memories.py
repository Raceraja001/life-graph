"""The capture spine must actually create memories.

``CaptureProcessors._on_capture_received`` used to run the extraction pipeline,
count the facts, and throw them away — nothing on the capture path ever called
``MemoryManager``, so ``POST /api/v1/capture/`` produced zero memories. These
tests pin the closed loop: extracted facts reach ``store_facts``, the capture's
trust tier (default-deny, derived from its surface) rides along so untrusted
content stays marked, the yield count reflects what was actually stored rather
than the raw fact count, and a persistence failure never breaks ingestion.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.core.events import Event, EventType
from life_graph.core.trust import TrustTier
from life_graph.extraction.rules import ExtractedFact
from life_graph.services import saved_by_tool
from life_graph.services.capture_processors import CaptureProcessors


def _fact(content: str) -> ExtractedFact:
    return ExtractedFact(content=content, fact_type="fact", confidence=0.8)


def _memory(content: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), content=content, tags=[])


class _FakeSession:
    """Stands in for ``async_session()`` — returns one prepared CaptureEvent."""

    def __init__(self, capture_evt) -> None:
        self._capture_evt = capture_evt
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def execute(self, _stmt):
        evt = self._capture_evt
        return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: evt))

    async def commit(self) -> None:
        self.committed = True


@pytest.fixture
def capture_evt():
    """A text capture from an unlisted surface (default-deny → EXTERNAL)."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id="acme",
        surface="unknown_surface",
        trust_tier=None,
        modality="text",
        content="I use PostgreSQL for everything.",
        status="received",
        yield_count=0,
    )


@pytest.fixture
def harness(monkeypatch, capture_evt):
    """Wire the handler to a fake session, a fake pipeline, and a mock manager.

    Returns a namespace with ``run(**overrides)`` to drive one capture event.
    """
    session = _FakeSession(capture_evt)
    monkeypatch.setattr("life_graph.services.capture_processors.async_session", lambda: session)
    # No tenant middleware in a unit test; the handler sets the contextvar
    # itself from the payload, so make that a no-op we can observe.
    tenant_calls: list[tuple] = []
    monkeypatch.setattr(
        "life_graph.core.tenant.set_tenant_context",
        lambda tid, uid="": tenant_calls.append((tid, uid)),
    )
    monkeypatch.setattr("life_graph.core.tenant.has_tenant_context", lambda: False)

    facts = [_fact("Uses PostgreSQL")]
    extraction = SimpleNamespace(facts=facts, tier1_count=1, tier2_count=0, tier3_count=0)

    class _FakePipeline:
        def __init__(self) -> None:
            self.capture_flags: list[bool] = []

        async def extract(self, _content, *, capture=False):
            self.capture_flags.append(capture)
            return extraction

    pipeline = _FakePipeline()
    # The processor takes the shared, client-backed pipeline from the DI module,
    # not a bare ExtractionPipeline() whose LLM tier ignores this deployment's
    # configuration — so that is what has to be patched here.
    monkeypatch.setattr("life_graph.api.dependencies.get_extraction_pipeline", lambda: pipeline)

    manager = SimpleNamespace(store_facts=AsyncMock(return_value=[_memory("Uses PostgreSQL")]))
    monkeypatch.setattr("life_graph.api.dependencies.get_memory_manager", lambda: manager)

    processors = CaptureProcessors(bus=SimpleNamespace(emit=AsyncMock()))

    async def run():
        await processors._on_capture_received(
            Event(
                type=EventType.CAPTURE_RECEIVED,
                payload={
                    "capture_event_id": str(capture_evt.id),
                    "tenant_id": capture_evt.tenant_id,
                    "surface": capture_evt.surface,
                    "modality": capture_evt.modality,
                },
                source="test",
            )
        )

    return SimpleNamespace(
        run=run,
        manager=manager,
        session=session,
        facts=facts,
        extraction=extraction,
        capture_evt=capture_evt,
        tenant_calls=tenant_calls,
        pipeline=pipeline,
    )


class TestFactsArePersisted:
    @pytest.mark.asyncio
    async def test_extraction_runs_in_capture_mode(self, harness):
        """A CaptureEvent is a genuine user capture, so the LLM-first path
        applies — the /memories route already passes capture=True, and the
        ambient path silently took the weaker regex/spaCy result instead."""
        await harness.run()

        assert harness.pipeline.capture_flags == [True]

    @pytest.mark.asyncio
    async def test_extracted_facts_reach_the_memory_manager(self, harness):
        """The whole point: facts are stored, not counted and discarded."""
        await harness.run()

        harness.manager.store_facts.assert_awaited_once()
        passed_facts = harness.manager.store_facts.await_args.args[0]
        assert [f.content for f in passed_facts] == ["Uses PostgreSQL"]

    @pytest.mark.asyncio
    async def test_capture_provenance_travels_with_the_facts(self, harness):
        await harness.run()

        kwargs = harness.manager.store_facts.await_args.kwargs
        assert kwargs["source"] == "capture"
        assert kwargs["context"]["capture_event_id"] == str(harness.capture_evt.id)
        assert kwargs["context"]["surface"] == "unknown_surface"

    @pytest.mark.asyncio
    async def test_tenant_context_is_set_from_the_payload(self, harness):
        """EventBus handlers run outside a request; storage needs the tenant."""
        await harness.run()

        assert harness.tenant_calls and harness.tenant_calls[0][0] == "acme"


class TestTrustTier:
    @pytest.mark.asyncio
    async def test_unknown_surface_is_external_or_worse(self, harness):
        """Default-deny: an unlisted surface must not be persisted as trusted."""
        await harness.run()

        tier = harness.manager.store_facts.await_args.kwargs["trust_tier"]
        assert tier == TrustTier.EXTERNAL.value

    @pytest.mark.asyncio
    async def test_api_surface_is_external(self, harness):
        harness.capture_evt.surface = "api"
        await harness.run()

        assert harness.manager.store_facts.await_args.kwargs["trust_tier"] == (
            TrustTier.EXTERNAL.value
        )

    @pytest.mark.asyncio
    async def test_whatsapp_surface_is_hostile_possible(self, harness):
        harness.capture_evt.surface = "whatsapp"
        await harness.run()

        assert harness.manager.store_facts.await_args.kwargs["trust_tier"] == (
            TrustTier.HOSTILE_POSSIBLE.value
        )

    @pytest.mark.asyncio
    async def test_cli_surface_is_self(self, harness):
        harness.capture_evt.surface = "cli"
        await harness.run()

        assert harness.manager.store_facts.await_args.kwargs["trust_tier"] == TrustTier.SELF.value

    @pytest.mark.asyncio
    async def test_a_stricter_stored_tier_wins_over_the_surface(self, harness):
        """A watcher carrying a raw web body asserts its own tier at capture time."""
        harness.capture_evt.surface = "cli"
        harness.capture_evt.trust_tier = TrustTier.HOSTILE_POSSIBLE.value
        await harness.run()

        assert harness.manager.store_facts.await_args.kwargs["trust_tier"] == (
            TrustTier.HOSTILE_POSSIBLE.value
        )


class TestYieldCount:
    @pytest.mark.asyncio
    async def test_yield_counts_stored_memories_not_raw_facts(self, harness):
        """Three facts in, one deduped away → the capture yielded two."""
        harness.extraction.facts = [_fact("a"), _fact("b"), _fact("c")]
        harness.manager.store_facts.return_value = [_memory("a"), _memory("b")]

        await harness.run()

        assert harness.capture_evt.yield_count == 2
        assert harness.capture_evt.status == "processed"

    @pytest.mark.asyncio
    async def test_decision_and_procedure_candidates_still_count(self, harness):
        harness.capture_evt.content = "I decided to use PostgreSQL for the graph store."
        harness.manager.store_facts.return_value = [_memory("Uses PostgreSQL")]

        await harness.run()

        # 1 memory + 1 decision candidate
        assert harness.capture_evt.yield_count == 2

    @pytest.mark.asyncio
    async def test_zero_stored_memories_yield_nothing(self, harness):
        harness.manager.store_facts.return_value = []

        await harness.run()

        assert harness.capture_evt.yield_count == 0
        assert harness.capture_evt.status == "processed"


class TestFailureIsolation:
    @pytest.mark.asyncio
    async def test_memory_manager_failure_does_not_break_ingestion(self, harness):
        harness.manager.store_facts.side_effect = RuntimeError("pgvector is down")

        await harness.run()  # must not raise

        assert harness.capture_evt.status == "processed"
        assert harness.capture_evt.yield_count == 0
        assert harness.session.committed

    @pytest.mark.asyncio
    async def test_extraction_failure_skips_persistence_but_still_processes(
        self, harness, monkeypatch
    ):
        class _BoomPipeline:
            async def extract(self, _content, *, capture=False):
                raise RuntimeError("spaCy model missing")

        harness.capture_evt.content = "I decided to use PostgreSQL for the graph store."
        monkeypatch.setattr(
            "life_graph.api.dependencies.get_extraction_pipeline", lambda: _BoomPipeline()
        )

        await harness.run()

        harness.manager.store_facts.assert_not_awaited()
        assert harness.capture_evt.status == "processed"
        assert harness.capture_evt.yield_count == 1  # the decision candidate

    @pytest.mark.asyncio
    async def test_non_text_modality_is_skipped_entirely(self, harness):
        await CaptureProcessors(bus=SimpleNamespace(emit=AsyncMock()))._on_capture_received(
            Event(
                type=EventType.CAPTURE_RECEIVED,
                payload={
                    "capture_event_id": str(harness.capture_evt.id),
                    "tenant_id": "acme",
                    "modality": "image",
                },
                source="test",
            )
        )

        harness.manager.store_facts.assert_not_awaited()


class TestActivityTrailSurfaces:
    """Some surfaces are a trail of what happened, not something to remember.

    Every tool call arrives as a capture on ``tool_exhaust``. Extracting it
    produced several LLM-written "facts" per shell command — 4,752 of 4,988
    memories on the author's own instance, all pending, which is what recall
    then fed back into the next session. The event row still lands (that is
    the trail); nothing downstream of it runs.
    """

    @pytest.mark.asyncio
    async def test_tool_exhaust_is_not_extracted(self, harness):
        harness.capture_evt.surface = "tool_exhaust"

        await harness.run()

        assert harness.pipeline.capture_flags == []
        harness.manager.store_facts.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_capture_event_is_still_marked_processed(self, harness):
        """The trail is the point — the row must not be left stuck at 'received'."""
        harness.capture_evt.surface = "tool_exhaust"

        await harness.run()

        assert harness.capture_evt.status == "processed"
        assert harness.capture_evt.yield_count == 0
        assert harness.session.committed

    @pytest.mark.asyncio
    async def test_decision_and_procedure_detection_are_skipped_too(self, harness):
        """Tool output trips the regexes as readily as prose does."""
        emit = AsyncMock()
        harness_bus = CaptureProcessors(bus=SimpleNamespace(emit=emit))
        harness.capture_evt.surface = "tool_exhaust"
        harness.capture_evt.content = "tool:Bash status:ok 12ms args:let's use the plan is to ship"

        await harness_bus._on_capture_received(
            Event(
                type=EventType.CAPTURE_RECEIVED,
                payload={
                    "capture_event_id": str(harness.capture_evt.id),
                    "tenant_id": "acme",
                    "modality": "text",
                },
                source="test",
            )
        )

        emit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_other_surfaces_are_unaffected(self, harness):
        """The setting names one surface; everything else extracts as before."""
        harness.capture_evt.surface = "cli"

        await harness.run()

        harness.manager.store_facts.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_the_list_is_configurable(self, harness, monkeypatch):
        """So the trail can be re-enabled, or another surface silenced, from .env."""
        monkeypatch.setattr(
            "life_graph.services.capture_processors.settings",
            SimpleNamespace(
                capture_no_extract_surfaces_list=[], capture_saved_by_tool_surfaces_list=[]
            ),
        )
        harness.capture_evt.surface = "tool_exhaust"

        await harness.run()

        harness.manager.store_facts.assert_awaited_once()


class TestSavedByJarvisItself:
    """On the phone app Jarvis saves "remember that…" with memory_save; the
    extractor kept it too, so it was stored twice in different words. What
    the run for the message saved decides (services/saved_by_tool.py)."""

    @pytest.fixture
    def jarvis(self, monkeypatch, harness):
        harness.capture_evt.surface = "jarvis_app"
        harness.facts.append(
            ExtractedFact(content="Locker code is 4417", fact_type="explicit_save", confidence=0.95)
        )
        run_saves = AsyncMock(return_value=[])
        monkeypatch.setattr(saved_by_tool, "run_saves", run_saves)
        vectors = {"Uses PostgreSQL": [0.0, 1.0], "Locker code is 4417": [1.0, 0.0]}
        harness.manager.generate_embedding = AsyncMock(side_effect=lambda t: vectors.get(t))
        return run_saves

    @pytest.mark.asyncio
    async def test_what_the_run_saved_is_not_stored_again(self, harness, jarvis):
        jarvis.return_value = [
            saved_by_tool.SavedMemory(uuid.uuid4(), "My locker code is 4417.", [0.99, 0.05])
        ]

        await harness.run()

        stored = harness.manager.store_facts.await_args.args[0]
        assert [f.content for f in stored] == ["Uses PostgreSQL"]

    @pytest.mark.asyncio
    async def test_a_relabelled_copy_is_dropped_too(self, harness, jarvis):
        """The extractor called it a plain fact (2026-10-24); the label is not the test."""
        harness.facts[-1].fact_type = "fact"
        jarvis.return_value = [
            saved_by_tool.SavedMemory(uuid.uuid4(), "My locker code is 4417.", [0.99, 0.05])
        ]

        await harness.run()

        stored = harness.manager.store_facts.await_args.args[0]
        assert [f.content for f in stored] == ["Uses PostgreSQL"]

    @pytest.mark.asyncio
    async def test_when_the_run_saved_nothing_the_explicit_save_is_kept(self, harness, jarvis):
        await harness.run()

        stored = harness.manager.store_facts.await_args.args[0]
        assert [f.fact_type for f in stored] == ["fact", "explicit_save"]

    @pytest.mark.asyncio
    async def test_a_run_still_going_leaves_the_capture_for_the_sweep(self, harness, jarvis):
        jarvis.return_value = None

        await harness.run()

        harness.manager.store_facts.assert_not_awaited()
        assert harness.capture_evt.status == "received"

    @pytest.mark.asyncio
    async def test_no_facts_no_wait(self, harness, jarvis):
        harness.facts.clear()

        await harness.run()

        jarvis.assert_not_awaited()
        assert harness.capture_evt.status == "processed"

    @pytest.mark.asyncio
    async def test_other_surfaces_keep_explicit_saves(self, harness):
        harness.capture_evt.surface = "cli"
        harness.facts.append(
            ExtractedFact(content="Locker code is 4417", fact_type="explicit_save", confidence=0.95)
        )

        await harness.run()

        stored = harness.manager.store_facts.await_args.args[0]
        assert [f.fact_type for f in stored] == ["fact", "explicit_save"]


class TestClaudeCodeSessions:
    """A Claude Code capture's memories carry its session and are linked to a
    memory session for it (services/claude_code_sessions.py)."""

    MEMORY_SESSION = uuid.UUID("00000000-0000-0000-0000-0000000000aa")

    @pytest.fixture
    def sessions(self, monkeypatch, harness):
        from life_graph.services import claude_code_sessions

        ensure = AsyncMock(return_value=self.MEMORY_SESSION)
        request_end = AsyncMock(return_value=True)
        monkeypatch.setattr(claude_code_sessions, "ensure_session", ensure)
        monkeypatch.setattr(claude_code_sessions, "request_end", request_end)
        harness.capture_evt.surface = "cli"
        harness.capture_evt.properties = {
            "integration": "claude_code",
            "hook_event": "UserPromptSubmit",
            "claude_code_session_id": "cc-1",
            "cwd": "/mnt/h/DevTools/Projects/life-graph",
            "project": "life-graph",
        }
        return SimpleNamespace(ensure=ensure, request_end=request_end)

    @pytest.mark.asyncio
    async def test_memories_carry_both_session_ids(self, harness, sessions):
        await harness.run()

        context = harness.manager.store_facts.await_args.kwargs["context"]
        assert context["claude_code_session_id"] == "cc-1"
        # The key the store links a new memory to its session by.
        assert context["session_id"] == str(self.MEMORY_SESSION)
        assert context["project"] == "life-graph"

    @pytest.mark.asyncio
    async def test_the_memory_session_is_made_for_the_tenant_and_project(self, harness, sessions):
        await harness.run()

        sessions.ensure.assert_awaited_once_with(
            "acme", "cc-1", project="life-graph", cwd="/mnt/h/DevTools/Projects/life-graph"
        )

    @pytest.mark.asyncio
    async def test_an_older_hook_spelling_is_still_read(self, harness, sessions):
        """Spooled captures from before the rename carry it as session_id."""
        props = harness.capture_evt.properties
        props["session_id"] = props.pop("claude_code_session_id")

        await harness.run()

        context = harness.manager.store_facts.await_args.kwargs["context"]
        assert context["claude_code_session_id"] == "cc-1"
        assert context["session_id"] == str(self.MEMORY_SESSION)

    @pytest.mark.asyncio
    async def test_a_session_failure_costs_the_link_not_the_memories(self, harness, sessions):
        sessions.ensure.side_effect = RuntimeError("db down")

        await harness.run()

        context = harness.manager.store_facts.await_args.kwargs["context"]
        assert context["claude_code_session_id"] == "cc-1"
        assert "session_id" not in context

    @pytest.mark.asyncio
    async def test_no_facts_no_session(self, harness, sessions):
        harness.facts.clear()

        await harness.run()

        sessions.ensure.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_other_integrations_get_no_session(self, harness, sessions):
        """``session_id`` on anything else is not a Claude Code id."""
        harness.capture_evt.properties = {"session_id": "whatever", "project": "x"}

        await harness.run()

        sessions.ensure.assert_not_awaited()
        context = harness.manager.store_facts.await_args.kwargs["context"]
        assert "session_id" not in context
        assert "claude_code_session_id" not in context

    @pytest.mark.asyncio
    async def test_the_session_end_marker_asks_for_the_end_and_is_not_extracted(
        self, harness, sessions
    ):
        harness.capture_evt.surface = "tool_exhaust"
        harness.capture_evt.properties.update(
            {"hook_event": "SessionEnd", "kind": "session_end", "reason": "clear"}
        )

        await harness.run()

        sessions.request_end.assert_awaited_once_with("acme", "cc-1", "clear")
        harness.manager.store_facts.assert_not_awaited()
        assert harness.pipeline.capture_flags == []
        assert harness.capture_evt.status == "processed"
        assert harness.session.committed

    @pytest.mark.asyncio
    async def test_the_marker_is_never_extracted_even_if_the_surface_would_be(
        self, harness, sessions, monkeypatch
    ):
        monkeypatch.setattr(
            "life_graph.services.capture_processors.settings",
            SimpleNamespace(
                capture_no_extract_surfaces_list=[], capture_saved_by_tool_surfaces_list=[]
            ),
        )
        harness.capture_evt.surface = "tool_exhaust"
        harness.capture_evt.properties.update({"kind": "session_end", "reason": "clear"})

        await harness.run()

        assert harness.pipeline.capture_flags == []
        sessions.request_end.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_failed_end_request_still_marks_the_capture_processed(self, harness, sessions):
        sessions.request_end.side_effect = RuntimeError("db down")
        harness.capture_evt.properties.update({"kind": "session_end", "reason": "clear"})

        await harness.run()

        assert harness.capture_evt.status == "processed"
