"""Preference -> knowledge graph sync, driven through the EventBus.

``PreferenceGraphService`` subscribes to PREFERENCE_CREATED, PREFERENCE_UPDATED
and EVIDENCE_ADDED and mirrors each into the Apache AGE graph. It reads payload
keys the producers did not emit, so the defaults were used instead — silently,
because handler exceptions are caught and ``.get(key, default)`` never raises.

``sync_preference`` calls ``create_preference_node``, which upserts. So the
update path did not merely fail to add information, it overwrote the node with
``topic="unknown", choice="", confidence=0.5``, discarding the topic that had
been written correctly at creation.

These tests drive the handlers with the payloads the producers actually emit.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from life_graph.core.events import Event, EventType
from life_graph.services.preference_graph import PreferenceGraphService


@pytest.fixture
def graph(monkeypatch):
    """Capture what reaches the graph store."""
    store = MagicMock()
    store.create_preference_node = AsyncMock()
    store.create_evidence_node = AsyncMock()
    store.create_edge = AsyncMock()
    monkeypatch.setattr("life_graph.services.preference_graph._get_graph_store", lambda: store)
    # Apache AGE is optional, and the sync methods now skip the graph when it
    # is unavailable rather than ERROR-logging on every preference write. These
    # tests are about what reaches the store, so force the graph on.
    monkeypatch.setattr(
        "life_graph.services.preference_graph.graph_available", AsyncMock(return_value=True)
    )
    return store


def _event(event_type: EventType, payload: dict) -> Event:
    return Event(type=event_type, payload=payload, source="test")


class TestPreferenceCreated:
    @pytest.mark.asyncio
    async def test_choice_and_confidence_reach_the_graph(self, graph):
        """The payload PreferenceStore.create() actually emits."""
        pref_id = str(uuid.uuid4())
        payload = {
            "id": pref_id,
            "tenant_id": "acme",
            "topic": "database",
            "choice": "PostgreSQL",
            "confidence": 0.9,
        }

        await PreferenceGraphService()._on_preference_created(
            _event(EventType.PREFERENCE_CREATED, payload)
        )

        graph.create_preference_node.assert_awaited_once()
        kwargs = graph.create_preference_node.await_args.kwargs
        assert kwargs["topic"] == "database"
        assert kwargs["choice"] == "PostgreSQL", "choice was lost between emit and graph"
        assert kwargs["confidence"] == 0.9, "confidence was lost between emit and graph"

    @pytest.mark.asyncio
    async def test_defaults_apply_only_when_genuinely_absent(self, graph):
        await PreferenceGraphService()._on_preference_created(
            _event(EventType.PREFERENCE_CREATED, {"id": "p", "tenant_id": "acme"})
        )
        kwargs = graph.create_preference_node.await_args.kwargs
        assert kwargs["topic"] == "unknown"
        assert kwargs["choice"] == ""
        assert kwargs["confidence"] == 0.5


class TestPreferenceUpdated:
    @pytest.mark.asyncio
    async def test_update_carries_the_new_values(self, graph):
        payload = {
            "id": str(uuid.uuid4()),
            "tenant_id": "acme",
            "topic": "database",
            "choice": "SQLite",
            "confidence": 0.4,
        }

        await PreferenceGraphService()._on_preference_updated(
            _event(EventType.PREFERENCE_UPDATED, payload)
        )

        kwargs = graph.create_preference_node.await_args.kwargs
        assert kwargs["topic"] == "database"
        assert kwargs["choice"] == "SQLite"
        assert kwargs["confidence"] == 0.4

    @pytest.mark.asyncio
    async def test_an_id_only_payload_would_clobber_the_node(self, graph):
        """Documents why the producer must send the full record.

        create_preference_node upserts. An update carrying only id and
        tenant_id therefore rewrites a correct node as
        topic="unknown", choice="", confidence=0.5.
        """
        await PreferenceGraphService()._on_preference_updated(
            _event(EventType.PREFERENCE_UPDATED, {"id": "p", "tenant_id": "acme"})
        )

        kwargs = graph.create_preference_node.await_args.kwargs
        assert (kwargs["topic"], kwargs["choice"], kwargs["confidence"]) == (
            "unknown",
            "",
            0.5,
        )


class TestEvidenceAdded:
    @pytest.mark.asyncio
    async def test_weight_reaches_the_graph_as_strength(self, graph):
        service = PreferenceGraphService()
        service.sync_evidence = AsyncMock()

        payload = {
            "id": str(uuid.uuid4()),
            "tenant_id": "acme",
            "preference_id": str(uuid.uuid4()),
            "stance": "supports",
            "weight": 0.75,
            "credibility": 0.6,
        }
        await service._on_evidence_added(_event(EventType.EVIDENCE_ADDED, payload))

        assert service.sync_evidence.await_args.kwargs["strength"] == 0.75

    @pytest.mark.asyncio
    async def test_credibility_is_the_fallback_when_weight_is_absent(self, graph):
        service = PreferenceGraphService()
        service.sync_evidence = AsyncMock()

        payload = {
            "id": "e",
            "tenant_id": "acme",
            "preference_id": "p",
            "stance": "contradicts",
            "credibility": 0.6,
        }
        await service._on_evidence_added(_event(EventType.EVIDENCE_ADDED, payload))

        assert service.sync_evidence.await_args.kwargs["strength"] == 0.6
        assert service.sync_evidence.await_args.kwargs["stance"] == "contradicts"

    @pytest.mark.asyncio
    async def test_strength_falls_back_to_one_when_neither_is_sent(self, graph):
        service = PreferenceGraphService()
        service.sync_evidence = AsyncMock()

        await service._on_evidence_added(
            _event(
                EventType.EVIDENCE_ADDED,
                {"id": "e", "tenant_id": "acme", "preference_id": "p"},
            )
        )
        assert service.sync_evidence.await_args.kwargs["strength"] == 1.0


class TestProducerPayloads:
    """The emitted payloads must contain what the handlers read."""

    @staticmethod
    def _emitted_keys(module, event_name: str) -> set[str]:
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(module))
        keys: set[str] = set()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "emit"
                and node.args
            ):
                continue
            target = node.args[0]
            if not (isinstance(target, ast.Attribute) and target.attr == event_name):
                continue
            payload = node.args[1] if len(node.args) > 1 else None
            if isinstance(payload, ast.Dict):
                keys |= {
                    k.value
                    for k in payload.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                }
        return keys

    def test_preference_created_payload_is_complete(self):
        from life_graph.services import preference_store

        keys = self._emitted_keys(preference_store, "PREFERENCE_CREATED")
        assert {"id", "tenant_id", "topic", "choice", "confidence"} <= keys

    def test_preference_updated_payload_is_complete(self):
        from life_graph.services import preference_store

        keys = self._emitted_keys(preference_store, "PREFERENCE_UPDATED")
        assert {"id", "tenant_id", "topic", "choice", "confidence"} <= keys, (
            "an id-only update payload clobbers the graph node"
        )

    def test_evidence_added_payload_is_complete(self):
        from life_graph.services import evidence_store

        keys = self._emitted_keys(evidence_store, "EVIDENCE_ADDED")
        assert {"id", "tenant_id", "preference_id", "stance", "weight"} <= keys
