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


def _over_http(monkeypatch, headers: dict[str, str], seen: dict | None = None) -> None:
    """Pretend a tool is running inside an MCP request that came over HTTP."""

    def caller_headers(include_all=False, include=None):
        if seen is not None:
            seen["include"] = include
        return headers

    monkeypatch.setattr(deps, "get_http_request", lambda: object())
    monkeypatch.setattr(deps, "get_http_headers", caller_headers)
    monkeypatch.setattr(mcp_server, "API_KEY", "server-key")


def test_over_http_a_tool_calls_the_api_with_the_callers_key_and_tenant(monkeypatch):
    seen = {}
    _over_http(monkeypatch, {"authorization": "Bearer caller-key", "x-tenant-id": "acme"}, seen)

    h = mcp_server._headers()

    assert h["Authorization"] == "Bearer caller-key"
    assert h["X-Tenant-ID"] == "acme"
    assert "authorization" in seen["include"]


def test_over_http_the_tools_tenant_argument_is_ignored(monkeypatch):
    # tenant_id is a tool argument, so the model writes it (audit L9).
    _over_http(monkeypatch, {"authorization": "Bearer caller-key", "x-tenant-id": "acme"})
    assert mcp_server._headers("other")["X-Tenant-ID"] == "acme"


def test_over_http_an_x_api_key_credential_is_forwarded_as_is(monkeypatch):
    _over_http(monkeypatch, {"x-api-key": "caller-key", "x-tenant-id": "acme"})

    h = mcp_server._headers()

    assert h["X-API-Key"] == "caller-key"
    assert "Authorization" not in h


def test_over_http_the_servers_own_key_is_never_added(monkeypatch):
    # A caller that presented no credential to a standalone --transport http
    # server must not borrow LIFE_GRAPH_API_KEY.
    _over_http(monkeypatch, {"x-tenant-id": "acme"})

    h = mcp_server._headers()

    assert "Authorization" not in h and "X-API-Key" not in h
    assert "server-key" not in str(h)


def test_over_stdio_the_environment_key_and_tenant_apply(monkeypatch):
    def no_request():
        raise RuntimeError("No active HTTP request found.")

    monkeypatch.setattr(deps, "get_http_request", no_request)
    monkeypatch.setattr(deps, "get_http_headers", lambda include_all=False, include=None: {})
    monkeypatch.setattr(mcp_server, "API_KEY", "server-key")
    monkeypatch.setattr(mcp_server, "DEFAULT_TENANT", "raja")

    h = mcp_server._headers()

    assert h["Authorization"] == "Bearer server-key"
    assert h["X-Tenant-ID"] == "raja"
    # Over stdio the tool's tenant still picks the tenant.
    assert mcp_server._headers("other")["X-Tenant-ID"] == "other"


def test_with_no_request_at_all_the_real_helper_reports_stdio():
    assert mcp_server._serving_http() is False


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
