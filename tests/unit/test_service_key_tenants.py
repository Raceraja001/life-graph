"""Optional service-key -> tenant binding (LIFE_GRAPH_SERVICE_KEY_TENANTS).

``verify_service_key`` only checks that a key is on the list, so any key could
name any tenant in ``X-Tenant-ID``. With ``service_key_tenants`` set, a key
may use only the tenants listed under its SHA-256 digest; a key with no entry
is refused; owner keys are not restricted. Unset, nothing changes.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from life_graph.api import auth
from life_graph.api import graph as graph_api
from life_graph.api.websocket import _authenticate
from life_graph.config import settings
from life_graph.main import app

OWNER_KEY = "owner-key-tenants-0123456789"
ACME_KEY = "acme-key-tenants-1111111111"
OTHER_KEY = "other-key-tenants-2222222222"  # valid, but with no binding


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


BINDING = json.dumps({_digest(ACME_KEY): ["acme", "acme-staging"]})


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "service_api_keys", f"{ACME_KEY},{OTHER_KEY},{OWNER_KEY}")
    monkeypatch.setattr(settings, "owner_api_keys", OWNER_KEY)
    monkeypatch.setattr(settings, "service_key_tenants", "")


@pytest.fixture
def bound(keys, monkeypatch):
    monkeypatch.setattr(settings, "service_key_tenants", BINDING)


class TestKeyMayUseTenant:
    def test_unset_allows_every_key_every_tenant(self, keys):
        assert settings.service_key_tenants_map is None
        for key in (ACME_KEY, OTHER_KEY, "not-even-a-key"):
            assert auth.key_may_use_tenant(key, "anything")

    def test_a_bound_key_uses_only_its_tenants(self, bound):
        assert auth.key_may_use_tenant(ACME_KEY, "acme")
        assert auth.key_may_use_tenant(ACME_KEY, "acme-staging")
        assert not auth.key_may_use_tenant(ACME_KEY, "globex")
        assert not auth.key_may_use_tenant(ACME_KEY, "default")

    def test_an_unbound_key_is_refused_when_the_map_is_set(self, bound):
        assert not auth.key_may_use_tenant(OTHER_KEY, "acme")

    def test_the_owner_key_is_never_restricted(self, bound):
        assert auth.key_may_use_tenant(OWNER_KEY, "acme")
        assert auth.key_may_use_tenant(OWNER_KEY, "globex")

    def test_no_key_checked_means_nothing_to_bind(self, bound):
        assert auth.key_may_use_tenant(None, "globex")

    def test_digests_match_in_either_case(self, keys, monkeypatch):
        monkeypatch.setattr(
            settings, "service_key_tenants", json.dumps({_digest(ACME_KEY).upper(): ["acme"]})
        )
        assert auth.key_may_use_tenant(ACME_KEY, "acme")

    @pytest.mark.parametrize(
        "raw",
        ["{not json", '["acme"]', json.dumps({"abc": "acme"}), json.dumps({"abc": [1]})],
        ids=["not-json", "not-an-object", "not-a-list", "not-strings"],
    )
    def test_a_malformed_map_fails_closed(self, keys, monkeypatch, caplog, raw):
        monkeypatch.setattr(settings, "service_key_tenants", raw)
        with caplog.at_level("ERROR", logger="life_graph.config"):
            assert not auth.key_may_use_tenant(ACME_KEY, "acme")
        # The owner can still get in to fix it.
        assert auth.key_may_use_tenant(OWNER_KEY, "acme")


@pytest.fixture
async def client(monkeypatch):
    # GET /graph/entities with the graph off: a route that needs no database.
    monkeypatch.setattr(graph_api, "graph_available", AsyncMock(return_value=False))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def _get(client, key: str, tenant: str):
    return await client.get(
        "/api/v1/graph/entities",
        headers={"Authorization": f"Bearer {key}", "X-Tenant-ID": tenant},
    )


class TestHttp:
    async def test_unset_any_key_reaches_any_tenant(self, keys, client):
        for key in (ACME_KEY, OTHER_KEY):
            response = await _get(client, key, "globex")
            assert response.status_code == 200, response.text

    async def test_a_bound_key_reaches_its_own_tenant(self, bound, client):
        response = await _get(client, ACME_KEY, "acme")
        assert response.status_code == 200, response.text

    async def test_a_bound_key_is_refused_another_tenant(self, bound, client):
        response = await _get(client, ACME_KEY, "globex")
        assert response.status_code == 403, response.text
        body = response.json()
        assert body["error"]["code"] == "TENANT_FORBIDDEN"
        assert body["detail"] == auth.SERVICE_KEY_TENANT_FORBIDDEN

    async def test_an_unbound_key_is_refused(self, bound, client):
        response = await _get(client, OTHER_KEY, "acme")
        assert response.status_code == 403, response.text

    async def test_the_owner_key_reaches_any_tenant(self, bound, client):
        response = await _get(client, OWNER_KEY, "globex")
        assert response.status_code == 200, response.text

    async def test_an_invalid_key_is_still_401(self, bound, client):
        response = await _get(client, "wrong-key", "acme")
        assert response.status_code == 401, response.text

    async def test_exempt_paths_are_not_bound(self, bound, client):
        response = await client.get("/live", headers={"Authorization": f"Bearer {OTHER_KEY}"})
        assert response.status_code != 403, response.text


class TestWebSocket:
    @staticmethod
    def _ws():
        return SimpleNamespace(headers={})

    async def test_unset_any_key_names_any_tenant(self, keys):
        assert await _authenticate(self._ws(), OTHER_KEY, "globex") == "globex"

    async def test_a_bound_key_names_only_its_tenants(self, bound):
        assert await _authenticate(self._ws(), ACME_KEY, "acme") == "acme"
        assert await _authenticate(self._ws(), ACME_KEY, "globex") is None

    async def test_an_unbound_key_is_refused(self, bound):
        assert await _authenticate(self._ws(), OTHER_KEY, "acme") is None

    async def test_the_owner_key_names_any_tenant(self, bound):
        assert await _authenticate(self._ws(), OWNER_KEY, "globex") == "globex"
