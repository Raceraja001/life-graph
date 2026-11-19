"""Exception text never reaches a client (audit 2026-11-19, M3).

``/health`` is unauthenticated, and asyncpg/SQLAlchemy messages carry the DB
host, user and role. The graph routes put ``{exc}`` straight into the HTTP
detail. Each must answer with a fixed message (same status codes, so
monitoring keeps working) and keep the real error in the server log.
"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from life_graph.core.tenant import tenant_scope

SECRET = 'password authentication failed for user "lg_admin" at db.internal:5432'


@contextlib.asynccontextmanager
async def _broken_session():
    raise RuntimeError(SECRET)
    yield  # pragma: no cover


@pytest.mark.asyncio
async def test_health_hides_the_db_error(monkeypatch):
    from life_graph.main import app, health_check

    monkeypatch.setattr("life_graph.main.async_session", _broken_session)
    monkeypatch.setattr(
        "life_graph.main.check_redis", AsyncMock(return_value="error: connect to 10.0.0.9 refused")
    )
    monkeypatch.setattr("life_graph.storage.graph.graph_status", AsyncMock(return_value="disabled"))
    monkeypatch.setattr(app.state, "startup_report", None, raising=False)
    svc = MagicMock()
    svc.probe = AsyncMock(return_value="healthy")
    monkeypatch.setattr("life_graph.api.dependencies.get_embedding_service", lambda: svc)

    response = await health_check()
    raw = response.body.decode()
    body = json.loads(raw)

    assert response.status_code == 503
    assert body["checks"]["postgres"]["status"] == "unhealthy"
    assert body["checks"]["redis"]["status"] == "unhealthy"
    assert "lg_admin" not in raw
    assert "db.internal" not in raw
    assert "10.0.0.9" not in raw


@pytest.mark.asyncio
async def test_memory_health_hides_the_db_error(monkeypatch):
    from life_graph.api.health import memory_health

    monkeypatch.setattr("life_graph.api.health.async_session", _broken_session)
    with tenant_scope("t1"):
        response = await memory_health()
    raw = response.body.decode()

    assert response.status_code == 503
    assert json.loads(raw)["checks"]["postgres"]["status"] == "unhealthy"
    assert "lg_admin" not in raw


@pytest.mark.asyncio
async def test_graph_routes_hide_the_exception_text(monkeypatch):
    from life_graph.api import graph as graph_api

    store = MagicMock()
    store.get_all_entities = AsyncMock(side_effect=RuntimeError(SECRET))
    monkeypatch.setattr(graph_api, "_get_graph_store", lambda: store)
    monkeypatch.setattr(graph_api, "graph_available", AsyncMock(return_value=True))
    engine = MagicMock()
    engine.entity_context = AsyncMock(side_effect=RuntimeError(SECRET))
    engine.hybrid_search = AsyncMock(side_effect=RuntimeError(SECRET))
    monkeypatch.setattr(graph_api, "_get_hybrid_engine", lambda: engine)

    with tenant_scope("t1"):
        with pytest.raises(HTTPException) as e1:
            await graph_api.list_entities(label=None)
        with pytest.raises(HTTPException) as e2:
            await graph_api.get_entity("x")
        with pytest.raises(HTTPException) as e3:
            await graph_api.hybrid_search(graph_api.GraphSearchRequest(query="q"))

    for e in (e1, e2, e3):
        assert e.value.status_code == 503
        assert "lg_admin" not in str(e.value.detail)
