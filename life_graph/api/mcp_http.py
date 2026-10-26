"""Life Graph's own MCP tools over HTTP, at ``/mcp/`` in the API.

The same tools as the stdio server (``life_graph/mcp_server.py``), for an MCP
client on another machine that has a key but not this repo, e.g. Claude Code
on a laptop on the tailnet::

    claude mcp add --transport http life-graph https://<host>:10443/mcp/ \\
        --header "Authorization: Bearer <key>" --header "X-Tenant-ID: <tenant>"

Off unless ``LIFE_GRAPH_MCP_HTTP_ENABLED`` is set. ``/mcp`` is not an exempt
path, so ``AuthMiddleware`` asks for a service key before a request gets here,
and it is not on the device allowlist, so a phone's token is refused. Each tool
then calls the API (``mcp_http_self_url``) with the caller's own
``Authorization`` and ``X-Tenant-ID`` (``mcp_server._headers``): it can do what
that key can do through the API, and nothing more.

Stateless: every request stands alone, so there is no MCP session to lose on
an API restart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from life_graph.config import settings

if TYPE_CHECKING:
    from starlette.applications import Starlette


def allowed_hosts() -> list[str]:
    """Host headers to answer: the configured names, each also with any port."""
    hosts = [h.strip() for h in settings.mcp_http_allowed_hosts.split(",") if h.strip()]
    return hosts + [f"{h}:*" for h in hosts if ":" not in h]


def build_app() -> Starlette:
    """The MCP endpoint as an ASGI app, to mount at ``/mcp``."""
    from life_graph import mcp_server

    # The tools call the API over HTTP; inside the API that is this process.
    mcp_server.API_BASE = settings.mcp_http_self_url
    return mcp_server.mcp.http_app(
        path="/",
        stateless_http=True,
        allowed_hosts=allowed_hosts(),
    )
