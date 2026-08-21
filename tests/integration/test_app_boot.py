"""Integration tests for app lifespan (startup/shutdown) with MCP bridge.

Covers:
- Lifespan startup and shutdown complete successfully when no external
  MCP servers are configured
- Health check works during lifespan

This is a regression guard: it tests that the app boots cleanly and the
lifespan context works, especially after wiring the MCP bridge.
"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from life_graph.main import app
from tests.integration.conftest import skip_on_db_error


class TestAppBoot:
    @skip_on_db_error
    async def test_app_boots_with_no_mcp_servers_configured(self, monkeypatch):
        """Verify lifespan startup and shutdown work with MCP bridge wired.

        Expected: app boots cleanly, lifespan context enters and exits
        without error. Health check responds 200 or 503 (latter acceptable
        if DB/Redis unreachable in CI).
        """
        # Ensure no servers are configured
        monkeypatch.setattr("life_graph.config.settings.mcp_servers", "[]", raising=False)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with app.router.lifespan_context(app):
                resp = await client.get("/health")

        # Accept 200 (healthy) or 503 (infrastructure unavailable in CI)
        assert resp.status_code in (200, 503), (
            f"Unexpected status: {resp.status_code}, body: {resp.text}"
        )
