"""The Tier-1 routers declare their responses, and the contract is pinned (audit M11).

memories, search and graph return ``Envelope[...]`` response models, so FastAPI
validates every body against the declared type and the OpenAPI schema shows
the real shape. ``snapshots/openapi_tier1.json`` pins that part of the schema:
a change to a response (or request) shape of these routes fails here until the
snapshot is regenerated on purpose:

    LIFE_GRAPH_UPDATE_OPENAPI_SNAPSHOT=1 pytest tests/unit/test_openapi_tier1_snapshot.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from life_graph.api import graph, memories, search
from life_graph.api.responses import Envelope

SNAPSHOT = Path(__file__).parent / "snapshots" / "openapi_tier1.json"
ROUTERS = {"memories": memories.router, "search": search.router, "graph": graph.router}
PREFIX = "/api/v1"


def _routes():
    for name, router in ROUTERS.items():
        for route in router.routes:
            if isinstance(route, APIRoute):
                yield name, route


def _refs(node, out: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            out.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            _refs(value, out)
    elif isinstance(node, list):
        for value in node:
            _refs(value, out)


def _tier1_spec() -> dict:
    from life_graph.main import app

    spec = app.openapi()
    paths: dict[str, dict] = {}
    for _name, route in _routes():
        path = PREFIX + route.path
        for method in sorted(m.lower() for m in route.methods):
            paths.setdefault(path, {})[method] = spec["paths"][path][method]

    schemas = spec["components"]["schemas"]
    wanted: set[str] = set()
    _refs(paths, wanted)
    seen: set[str] = set()
    while wanted - seen:
        name = sorted(wanted - seen)[0]
        seen.add(name)
        _refs(schemas[name], wanted)
    return {
        "paths": dict(sorted(paths.items())),
        "schemas": {n: schemas[n] for n in sorted(seen)},
    }


def test_every_tier1_route_declares_an_envelope():
    untyped = []
    for name, route in _routes():
        if route.status_code == 204:
            continue  # DELETE /memories/{id}: no body
        model = route.response_model
        origin = getattr(model, "__pydantic_generic_metadata__", {}).get("origin")
        if origin is not Envelope:
            untyped.append(f"{name}: {sorted(route.methods)} {route.path} -> {model!r}")
    assert not untyped, "routes without response_model=Envelope[...]:\n" + "\n".join(untyped)


def test_envelope_omits_meta_when_absent_and_keeps_it_when_sent():
    """Typing a route must not add a "meta": null that success_response never sent."""

    class Item(BaseModel):
        a: int

    assert Envelope[Item](data={"a": 1}).model_dump(mode="json") == {"data": {"a": 1}}
    assert Envelope[list[Item]](data=[{"a": 1}], meta={"has_more": False}).model_dump(
        mode="json"
    ) == {"data": [{"a": 1}], "meta": {"has_more": False}}


@pytest.mark.skipif(
    bool(os.environ.get("LIFE_GRAPH_UPDATE_OPENAPI_SNAPSHOT")), reason="regenerating"
)
def test_tier1_openapi_matches_the_snapshot():
    current = _tier1_spec()
    pinned = json.loads(SNAPSHOT.read_text())
    assert current["paths"].keys() == pinned["paths"].keys()
    for path, ops in current["paths"].items():
        assert ops == pinned["paths"][path], (
            f"OpenAPI for {path} changed. If on purpose, regenerate: "
            "LIFE_GRAPH_UPDATE_OPENAPI_SNAPSHOT=1 pytest " + __file__
        )
    assert current["schemas"] == pinned["schemas"], (
        "A Tier-1 schema changed. If on purpose, regenerate: "
        "LIFE_GRAPH_UPDATE_OPENAPI_SNAPSHOT=1 pytest " + __file__
    )


@pytest.mark.skipif(
    not os.environ.get("LIFE_GRAPH_UPDATE_OPENAPI_SNAPSHOT"), reason="set to regenerate"
)
def test_regenerate_snapshot():
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps(_tier1_spec(), indent=1, sort_keys=True) + "\n")


async def test_ask_early_exit_is_enveloped_like_every_other_answer(monkeypatch):
    """POST /search/ask answered a bare AskResponse on its four early exits.

    life-graph-ui unwraps ``data``, so it got undefined exactly when the answer
    was "I can't search" or "I don't know"."""
    import time
    from unittest.mock import AsyncMock, MagicMock

    import httpx

    from life_graph.api import middleware
    from life_graph.api.dependencies import get_memory_manager, get_metamemory
    from life_graph.main import app

    manager = MagicMock()
    manager._generate_embedding = AsyncMock(return_value=None)  # embedder down
    app.dependency_overrides[get_memory_manager] = lambda: manager
    app.dependency_overrides[get_metamemory] = lambda: MagicMock()
    monkeypatch.setitem(middleware._tenant_status_cache, "t1", (time.monotonic() + 60, None))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http:
            response = await http.post(
                "/api/v1/search/ask", json={"question": "q?"}, headers={"X-Tenant-ID": "t1"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"data"}
    assert body["data"]["answer"].startswith("Embedding service is unavailable")
    assert body["data"]["source_count"] == 0


def test_success_responses_are_documented_as_envelopes():
    """The 2xx schema of each typed route is an Envelope component, not a bare object."""
    spec = _tier1_spec()
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            ok = next((c for c in ("200", "201") if c in op["responses"]), None)
            if ok is None:
                continue
            content = op["responses"][ok].get("content", {}).get("application/json", {})
            ref = content.get("schema", {}).get("$ref", "")
            assert ref.rsplit("/", 1)[-1].startswith("Envelope_"), (method, path, content)
