"""WebSocket handshake auth must accept Caddy's injected X-API-Key
header, not just the ``api_key`` query parameter.

The bug this guards: a browser's native WebSocket API can't set custom
headers on its own outgoing handshake, so the dashboard sends a
placeholder ``api_key=dev`` query param it has no way to make real.
Caddy already injects the real ``X-API-Key`` header on proxied ``/ws``
requests (same as it does for ``/api``/``/docs``) — but the endpoint
only ever checked the query param, so every browser connection failed
auth, got closed, and reconnected forever ("Reconnecting…" in the UI).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from life_graph.api.auth import extract_api_key
from life_graph.api.websocket import websocket_endpoint
from life_graph.config import settings


class _Headers(dict):
    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


def test_extract_api_key_prefers_bearer_over_header_over_query():
    headers = _Headers({"Authorization": "Bearer bearer-key", "X-API-Key": "header-key"})
    assert extract_api_key(headers, {"api_key": "query-key"}) == "bearer-key"


def test_extract_api_key_falls_back_to_header_then_query():
    assert extract_api_key(_Headers({"X-API-Key": "header-key"}), {"api_key": "query-key"}) == (
        "header-key"
    )
    assert extract_api_key(_Headers(), {"api_key": "query-key"}) == "query-key"


def test_extract_api_key_returns_none_when_nothing_present():
    assert extract_api_key(_Headers(), {}) is None


def _app() -> FastAPI:
    app = FastAPI()
    app.add_api_websocket_route("/ws", websocket_endpoint)
    return app


def test_websocket_accepts_caddy_injected_header(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "real-secret")
    client = TestClient(_app())
    with client.websocket_connect("/ws?api_key=dev", headers={"X-API-Key": "real-secret"}) as ws:
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}


def test_websocket_rejects_placeholder_query_param_alone(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "real-secret")
    client = TestClient(_app())
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws?api_key=dev") as ws:
            ws.receive_text()


def test_websocket_open_when_no_api_key_configured(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "")
    client = TestClient(_app())
    with client.websocket_connect("/ws") as ws:
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}
