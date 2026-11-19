"""Exempt paths match on segment boundaries; metrics label by route (audit
2026-11-19, M7).

``startswith("/brain")`` exempted ``/brainX`` and ``/docsX`` from auth, and
request metrics were labelled with the raw path, so any caller could add a
Prometheus series per request to the public ``/metrics``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse
from starlette.routing import Mount

from life_graph.api.auth import is_exempt_path
from life_graph.api.middleware import RequestLoggingMiddleware
from life_graph.core import metrics


@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/live",
        "/ready",
        "/metrics",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/openapi.json",
        "/brain",
        "/brain/",
        "/brain/assets/app.js",
        "/ws",
        "/",
        "/api/v1/devices/pair",
    ],
)
def test_real_exempt_paths_stay_exempt(path):
    assert is_exempt_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "/brainX",
        "/brain-admin",
        "/docsX",
        "/healthz/../api/v1/memories",
        "/healthy",
        "/metrics2",
        "/wsx",
        "/redocs",
        "/openapi.jsonx",
        "/api/v1/memories",
    ],
)
def test_lookalike_paths_are_not_exempt(path):
    assert not is_exempt_path(path)


def _series_count() -> int:
    return sum(
        1
        for family in metrics.REQUEST_COUNT.collect()
        for s in family.samples
        if s.name.endswith("_total")
    )


@pytest.mark.skipif(not metrics.PROMETHEUS_AVAILABLE, reason="prometheus_client missing")
def test_random_paths_do_not_add_metric_series():
    async def static_like(scope, receive, send):
        await PlainTextResponse("ok")(scope, receive, send)

    app = FastAPI(routes=[Mount("/brain", app=static_like)])

    @app.get("/items/{item_id}")
    async def item(item_id: str):
        return {"id": item_id}

    app.add_middleware(RequestLoggingMiddleware)
    client = TestClient(app)

    # One request of each shape first, so every series this test can create
    # already exists.
    client.get("/brain/x0")
    client.get("/items/x0")
    client.get("/nowhere-0")
    before = _series_count()

    for i in range(1, 300):
        assert client.get(f"/brain/x{i}").status_code == 200
        assert client.get(f"/items/x{i}").status_code == 200
        assert client.get(f"/nowhere-{i}").status_code == 404

    assert _series_count() == before
    labels = {
        s.labels["path"] for family in metrics.REQUEST_COUNT.collect() for s in family.samples
    }
    assert {"/brain", "/items/{item_id}", metrics.UNMATCHED_ROUTE} <= labels
    assert not any(p.startswith("/brain/x") or p.startswith("/nowhere") for p in labels)


def test_route_label_without_a_route_is_unmatched():
    assert metrics.route_label({}) == metrics.UNMATCHED_ROUTE
    assert metrics.route_label({"route": object()}) == metrics.UNMATCHED_ROUTE
