"""MCP over HTTP (api/mcp_http.py): gated like the API, and each tool call
goes on to the API as the caller (their key and tenant), not as the server."""

import fastmcp.server.dependencies as deps

from life_graph import mcp_server
from life_graph.api import mcp_http
from life_graph.api.auth import is_exempt_path
from life_graph.api.device_access import device_may_call


def test_the_endpoint_needs_a_service_key_and_refuses_phone_tokens():
    for path in ("/mcp", "/mcp/"):
        assert not is_exempt_path(path)
        for method in ("GET", "POST", "DELETE"):
            assert not device_may_call(method, path)


def test_over_http_a_tool_calls_the_api_with_the_callers_key_and_tenant(monkeypatch):
    seen = {}

    def caller_headers(include_all=False, include=None):
        seen["include"] = include
        return {"authorization": "Bearer caller-key", "x-tenant-id": "acme"}

    monkeypatch.setattr(deps, "get_http_headers", caller_headers)
    monkeypatch.setattr(mcp_server, "API_KEY", "server-key")

    h = mcp_server._headers()

    assert h["Authorization"] == "Bearer caller-key"
    assert h["X-Tenant-ID"] == "acme"
    assert "authorization" in seen["include"]
    # A tenant named in the call still wins, as over stdio.
    assert mcp_server._headers("other")["X-Tenant-ID"] == "other"


def test_over_stdio_the_environment_key_and_tenant_apply(monkeypatch):
    monkeypatch.setattr(deps, "get_http_headers", lambda include_all=False, include=None: {})
    monkeypatch.setattr(mcp_server, "API_KEY", "server-key")
    monkeypatch.setattr(mcp_server, "DEFAULT_TENANT", "raja")

    h = mcp_server._headers()

    assert h["Authorization"] == "Bearer server-key"
    assert h["X-Tenant-ID"] == "raja"


def test_allowed_hosts_take_any_port(monkeypatch):
    monkeypatch.setattr(
        mcp_http.settings, "mcp_http_allowed_hosts", "localhost, race-home-pc.tailcdbd87.ts.net"
    )
    assert mcp_http.allowed_hosts() == [
        "localhost",
        "race-home-pc.tailcdbd87.ts.net",
        "localhost:*",
        "race-home-pc.tailcdbd87.ts.net:*",
    ]


def test_build_points_the_tools_at_this_api(monkeypatch):
    monkeypatch.setattr(mcp_http.settings, "mcp_http_self_url", "http://127.0.0.1:9999")
    monkeypatch.setattr(mcp_server, "API_BASE", "http://elsewhere")
    app = mcp_http.build_app()
    assert mcp_server.API_BASE == "http://127.0.0.1:9999"
    assert hasattr(app, "lifespan")
