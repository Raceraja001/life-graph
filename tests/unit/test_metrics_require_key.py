"""``metrics_require_key`` closes GET /metrics behind a service key (audit M7 follow-up).

Off by default: /metrics stays public, as before.
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from life_graph.api import auth
from life_graph.api.middleware import AuthMiddleware

KEY = "svc-key"


def _ok(request):  # noqa: ANN001
    return PlainTextResponse("ok")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(auth.settings, "service_api_keys", KEY)
    monkeypatch.setattr(auth.settings, "api_key", None)
    monkeypatch.setattr(auth.settings, "environment", "production")
    app = Starlette(routes=[Route("/metrics", _ok), Route("/health", _ok)])
    app.add_middleware(AuthMiddleware)
    return TestClient(app)


def test_metrics_public_by_default(client, monkeypatch):
    monkeypatch.setattr(auth.settings, "metrics_require_key", False)
    assert client.get("/metrics").status_code == 200


def test_metrics_needs_a_key_when_required(client, monkeypatch):
    monkeypatch.setattr(auth.settings, "metrics_require_key", True)
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": f"Bearer {KEY}"}).status_code == 200
    # Only /metrics is closed by the setting; the other exempt paths stay open.
    assert client.get("/health").status_code == 200


def test_setting_defaults_off():
    from life_graph.config import Settings

    assert Settings.model_fields["metrics_require_key"].default is False
