"""Every error the API sends uses the one documented envelope (audit M2).

api/responses.py documents ``{"error": {"code", "message", "request_id"}}`` and
the TypeScript SDK (sdks/typescript/src/client.ts) reads only ``error``. The
~280 ``HTTPException`` sites answered FastAPI's ``{"detail": ...}`` instead, so
the SDK saw no code and no message for any of them. They now answer the
envelope, and keep ``detail`` at the top level for the clients that read it
(dashboard/lib/api.ts, life-graph-ui, the Android app, the Python SDK).

These go through the real app and its middleware, so the shape is the one a
client receives.
"""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from life_graph.api import middleware
from life_graph.api.dependencies import get_store
from life_graph.api.responses import InvalidCursorError, http_error_body
from life_graph.main import app

TENANT = "envelope-contract"
RID = "rid-envelope-contract"


@pytest.fixture
async def client(monkeypatch):
    # The tenant middleware looks the tenant's status up in the database on
    # writes; seed its cache so no test here ever opens a DB connection.
    monkeypatch.setitem(middleware._tenant_status_cache, TENANT, (time.monotonic() + 3600, None))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Tenant-ID": TENANT, "X-Request-ID": RID},
    ) as http:
        yield http
    app.dependency_overrides.clear()


def _store(**methods) -> MagicMock:
    store = MagicMock()
    for name, value in methods.items():
        setattr(store, name, value)
    return store


def assert_envelope(response: httpx.Response, status: int, code: str | None = None) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert isinstance(body.get("error"), dict), body
    assert body["error"]["code"], body
    assert isinstance(body["error"]["message"], str), body
    assert body["error"]["request_id"] == RID, body
    assert "detail" in body, body
    if code is not None:
        assert body["error"]["code"] == code, body
    return body


async def test_401_from_the_auth_middleware(client, monkeypatch):
    def refuse(request):
        raise HTTPException(status_code=401, detail="Missing API key")

    monkeypatch.setattr(middleware, "verify_service_key", refuse)
    response = await client.get("/api/v1/memories/pending/count")

    body = assert_envelope(response, 401, "UNAUTHORIZED")
    assert body["detail"] == "Missing API key"
    assert body["error"]["message"] == "Missing API key"


async def test_403_from_a_route(client):
    # Raw Cypher is refused for any tenant but the administrative one.
    response = await client.post("/api/v1/graph/query", json={"cypher": "MATCH (n) RETURN n"})

    body = assert_envelope(response, 403, "FORBIDDEN")
    assert "administrative tenant" in body["detail"]
    assert body["error"]["message"] == body["detail"]


async def test_404_from_a_route(client):
    app.dependency_overrides[get_store] = lambda: _store(retrieve=AsyncMock(return_value=None))
    memory_id = uuid.uuid4()

    response = await client.get(f"/api/v1/memories/{memory_id}")

    body = assert_envelope(response, 404, "NOT_FOUND")
    assert body["detail"] == f"Memory {memory_id} not found"


async def test_404_for_an_unknown_path(client):
    response = await client.get("/api/v1/no-such-route")

    assert_envelope(response, 404, "NOT_FOUND")


async def test_409_from_a_route(client):
    archived = SimpleNamespace(status="archived", tenant_id=TENANT)
    app.dependency_overrides[get_store] = lambda: _store(retrieve=AsyncMock(return_value=archived))

    response = await client.post(f"/api/v1/memories/{uuid.uuid4()}/approve")

    body = assert_envelope(response, 409, "CONFLICT")
    assert body["detail"] == "Cannot approve a archived memory"


async def test_422_request_validation_keeps_its_field_details(client):
    response = await client.post("/api/v1/memories/", json={})

    body = assert_envelope(response, 422, "VALIDATION_ERROR")
    # The field-level list clients already read is unchanged...
    assert any("content" in d["field"] for d in body["error"]["details"])
    # ...and detail is a plain string, so a client that shows detail shows a sentence.
    assert body["detail"] == body["error"]["message"]


async def test_422_invalid_cursor(client):
    store = _store(list_memories=AsyncMock(side_effect=InvalidCursorError("Invalid cursor format")))
    app.dependency_overrides[get_store] = lambda: store

    response = await client.get("/api/v1/memories/", params={"cursor": "nope"})

    body = assert_envelope(response, 422, "INVALID_CURSOR")
    assert body["detail"] == "Invalid cursor format"


async def test_500_has_the_same_shape(client):
    store = _store(retrieve=AsyncMock(side_effect=RuntimeError("boom")))
    app.dependency_overrides[get_store] = lambda: store

    response = await client.get(f"/api/v1/memories/{uuid.uuid4()}")

    body = assert_envelope(response, 500, "INTERNAL_ERROR")
    assert body["detail"] == "An internal error occurred."
    assert "boom" not in response.text


def test_http_error_body_keeps_any_detail_unchanged():
    listed = http_error_body(400, [{"loc": ["x"]}], "r1")
    assert listed["detail"] == [{"loc": ["x"]}]
    assert listed["error"] == {
        "code": "BAD_REQUEST",
        "message": "[{'loc': ['x']}]",
        "request_id": "r1",
    }

    named = http_error_body(409, {"code": "ALREADY_RUNNING", "message": "busy"}, "r2")
    assert named["error"]["code"] == "ALREADY_RUNNING"
    assert named["error"]["message"] == "busy"
    assert named["detail"] == {"code": "ALREADY_RUNNING", "message": "busy"}

    assert http_error_body(418, "teapot")["error"]["code"] == "IM_A_TEAPOT"
    assert http_error_body(599, "odd")["error"]["code"] == "HTTP_599"


async def test_headers_on_an_http_exception_survive(client, monkeypatch):
    """A 401 that names its scheme, or a 429 with Retry-After, must keep the header."""
    from life_graph.api import graph as graph_api

    async def busy(*_a, **_k):
        raise HTTPException(status_code=503, detail="busy", headers={"Retry-After": "7"})

    monkeypatch.setattr(graph_api, "graph_available", busy)
    response = await client.get("/api/v1/graph/entities")

    assert_envelope(response, 503, "SERVICE_UNAVAILABLE")
    assert response.headers["Retry-After"] == "7"
