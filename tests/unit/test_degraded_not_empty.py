"""An infrastructure failure is a 503 or a degraded flag, never a quiet 200 empty (audit M20).

- HybridQueryEngine.entity_context swallowed graph *and* database errors, so
  GET /graph/entity/{name} answered 200 with no memories while Postgres was
  down — and the route's own 503 could never fire.
- study.write_cards answered [] when the local model was down, and the drafts
  route reported that as "nothing to study".
"""

from __future__ import annotations

import contextlib
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from life_graph.api import middleware
from life_graph.main import app
from life_graph.services import study
from life_graph.storage.hybrid import HybridQueryEngine

TENANT = "degraded-not-empty"


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setitem(middleware._tenant_status_cache, TENANT, (time.monotonic() + 3600, None))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-Tenant-ID": TENANT}
    ) as http:
        yield http


def _engine(*, graph_error: Exception | None = None, db_error: Exception | None = None):
    engine = HybridQueryEngine()
    engine._graph_store = MagicMock()
    engine.graph_store.get_vertex = AsyncMock(
        side_effect=graph_error, return_value={"label": "Person", "properties": {"name": "Ana"}}
    )
    engine.graph_store.get_neighbors = AsyncMock(return_value=[{"properties": {"name": "Bo"}}])
    row = SimpleNamespace(
        id="m1", content="Ana likes tea", tags=["Ana"], importance=0.6, created_at=None
    )
    engine._memory_store = MagicMock()
    engine.memory_store.list_memories = AsyncMock(side_effect=db_error, return_value=([row], False))
    return engine


# ── entity_context ─────────────────────────────────────────


async def test_entity_context_healthy_has_no_degraded_reasons():
    out = await _engine().entity_context("Ana")

    assert out["degraded"] == []
    assert out["neighbors"] == [{"name": "Bo"}]
    assert [m["id"] for m in out["memories"]] == ["m1"]


async def test_entity_context_database_failure_raises():
    with pytest.raises(ConnectionError):
        await _engine(db_error=ConnectionError("db down")).entity_context("Ana")


async def test_entity_context_graph_failure_is_flagged_not_hidden():
    out = await _engine(graph_error=RuntimeError("age down")).entity_context("Ana")

    assert out["degraded"] == ["graph_query_failed"]
    assert out["neighbors"] == []
    assert [m["id"] for m in out["memories"]] == ["m1"]  # the memories half still answered


async def test_entity_context_without_the_graph_does_not_try_it():
    engine = _engine()
    out = await engine.entity_context("Ana", use_graph=False)

    engine.graph_store.get_vertex.assert_not_called()
    assert out["degraded"] == []


# ── GET /graph/entity/{name} ───────────────────────────────


async def test_entity_route_db_failure_is_503(client, monkeypatch):
    from life_graph.api import graph as graph_api

    monkeypatch.setattr(graph_api, "graph_available", AsyncMock(return_value=True))
    monkeypatch.setattr(graph_api, "_get_hybrid_engine", lambda: _engine(db_error=OSError("down")))

    response = await client.get("/api/v1/graph/entity/Ana")

    assert response.status_code == 503


async def test_entity_route_graph_failure_sets_meta_degraded(client, monkeypatch):
    from life_graph.api import graph as graph_api

    monkeypatch.setattr(graph_api, "graph_available", AsyncMock(return_value=True))
    monkeypatch.setattr(
        graph_api, "_get_hybrid_engine", lambda: _engine(graph_error=RuntimeError("age"))
    )

    response = await client.get("/api/v1/graph/entity/Ana")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"degraded": True, "degraded_reasons": ["graph_query_failed"]}
    assert "degraded" not in body["data"]


async def test_entity_route_without_age_keeps_graph_enabled_false(client, monkeypatch):
    from life_graph.api import graph as graph_api

    engine = _engine()
    monkeypatch.setattr(graph_api, "graph_available", AsyncMock(return_value=False))
    monkeypatch.setattr(graph_api, "_get_hybrid_engine", lambda: engine)

    response = await client.get("/api/v1/graph/entity/Ana")

    assert response.status_code == 200
    assert response.json()["meta"] == {"graph_enabled": False}
    engine.graph_store.get_vertex.assert_not_called()


async def test_entity_route_healthy_has_no_meta(client, monkeypatch):
    from life_graph.api import graph as graph_api

    monkeypatch.setattr(graph_api, "graph_available", AsyncMock(return_value=True))
    monkeypatch.setattr(graph_api, "_get_hybrid_engine", lambda: _engine())

    response = await client.get("/api/v1/graph/entity/Ana")

    assert response.status_code == 200
    assert "meta" not in response.json()


# ── study cards ────────────────────────────────────────────


class _DownLM:
    async def chat_local_only(self, **_kw):
        raise ConnectionError("ollama down")


class _GarbageLM:
    async def chat_local_only(self, **_kw):
        return "not json"


class _EmptyLM:
    async def chat_local_only(self, **_kw):
        return '{"cards": []}'


async def test_write_cards_checked_names_the_failure():
    assert await study.write_cards_checked("notes", client=_DownLM()) == (
        [],
        study.MODEL_UNAVAILABLE,
    )
    assert await study.write_cards_checked("notes", client=_GarbageLM()) == (
        [],
        study.MODEL_OUTPUT_INVALID,
    )
    # Nothing worth a card is not a failure.
    assert await study.write_cards_checked("notes", client=_EmptyLM()) == ([], None)
    assert await study.write_cards_checked("  ", client=_DownLM()) == ([], None)


async def test_draft_flags_a_model_failure():
    out = await study.draft(
        MagicMock(), TENANT, today=None, source="text", text="notes", client=_DownLM()
    )

    assert out["drafted"] == 0
    assert (out["degraded"], out["degraded_reason"]) == (True, study.MODEL_UNAVAILABLE)


async def test_draft_with_nothing_to_learn_is_not_degraded():
    out = await study.draft(
        MagicMock(), TENANT, today=None, source="text", text="notes", client=_EmptyLM()
    )

    assert "degraded" not in out


async def test_drafts_route_moves_the_flag_into_meta(client, monkeypatch):
    from life_graph.api import assistant

    session = MagicMock()
    session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(assistant, "async_session", fake_session)
    monkeypatch.setattr("life_graph.runtime.get_lm_client", lambda: _DownLM())

    response = await client.post("/api/v1/study/drafts", json={"source": "text", "text": "notes"})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["meta"] == {"degraded": True, "degraded_reason": study.MODEL_UNAVAILABLE}
    assert body["data"]["drafted"] == 0
    assert "degraded" not in body["data"]
