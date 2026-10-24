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


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    """No keys unless a test sets them; development unless a test says otherwise."""
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(settings, "service_api_keys", "")
    monkeypatch.setattr(settings, "environment", "development")


def _tenants() -> set[str]:
    from life_graph.api.websocket import ws_manager

    return {t for t, conns in ws_manager._connections.items() if conns}


def _refused(client, url, **kw) -> int:
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(url, **kw) as ws:
        ws.receive_text()
    return exc.value.code


def test_websocket_accepts_caddy_injected_header(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "real-secret")
    client = TestClient(_app())
    with client.websocket_connect("/ws?api_key=dev", headers={"X-API-Key": "real-secret"}) as ws:
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}


def test_websocket_rejects_placeholder_query_param_alone(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "real-secret")
    client = TestClient(_app())
    assert _refused(client, "/ws?api_key=dev") == 4401


def test_websocket_open_when_no_key_configured_in_development():
    client = TestClient(_app())
    with client.websocket_connect("/ws") as ws:
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}


def test_websocket_closed_when_no_key_configured_outside_development(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    assert _refused(TestClient(_app()), "/ws?tenant_id=victim") == 4401


# ── Security review 2026-10-24 (H1): service_api_keys, not just api_key ──


def test_service_keys_are_checked_not_only_the_legacy_key(monkeypatch):
    """The deployment sets service_api_keys and leaves api_key empty; the
    socket used to be open to anyone then, for whatever tenant they named."""
    monkeypatch.setattr(settings, "service_api_keys", "svc-1,svc-2")
    client = TestClient(_app())
    assert _refused(client, "/ws?tenant_id=victim") == 4401
    assert _refused(client, "/ws?api_key=guess&tenant_id=victim") == 4401


def test_dashboard_style_query_key_names_its_tenant(monkeypatch):
    # dashboard/lib/use-websocket.ts: /ws?api_key=<key>&tenant_id=<tenant>
    monkeypatch.setattr(settings, "service_api_keys", "svc-1,svc-2")
    client = TestClient(_app())
    with client.websocket_connect("/ws?api_key=svc-2&tenant_id=t_dash") as ws:
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}
        assert "t_dash" in _tenants()


def test_bearer_key_with_tenant_header(monkeypatch):
    monkeypatch.setattr(settings, "service_api_keys", "svc-1")
    client = TestClient(_app())
    headers = {"Authorization": "Bearer svc-1", "X-Tenant-ID": "t_hdr"}
    with client.websocket_connect("/ws", headers=headers) as ws:
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}
        assert "t_hdr" in _tenants()


def test_a_device_token_listens_as_its_own_tenant_only(monkeypatch):
    from life_graph.services import devices

    async def fake_auth(token):
        return ("t_phone", "dev-1") if token == "phone-token" else None

    monkeypatch.setattr(settings, "service_api_keys", "svc-1")
    monkeypatch.setattr(devices, "authenticate", fake_auth)
    client = TestClient(_app())
    url = "/ws?tenant_id=someone-else"
    with client.websocket_connect(url, headers={"Authorization": "Bearer phone-token"}) as ws:
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}
        assert "t_phone" in _tenants() and "someone-else" not in _tenants()
    assert _refused(client, url, headers={"Authorization": "Bearer other"}) == 4401
