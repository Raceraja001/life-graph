"""
Life Graph — MCP Server (Model Context Protocol)

Exposes Life Graph memory capabilities to any MCP-compatible client
(Claude, Cursor, VS Code, Antigravity, etc.).

Usage:
    # Development (with inspector UI):
    fastmcp dev life_graph/mcp_server.py

    # Production (stdio transport for Claude/Cursor):
    fastmcp run life_graph/mcp_server.py

    # Or as a Docker service:
    docker compose exec app fastmcp run life_graph/mcp_server.py
"""

from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
import httpx

# ── Configuration ────────────────────────────────────────────────────────────

API_BASE = os.environ.get("LIFE_GRAPH_API_URL", "http://localhost:8000")
DEFAULT_TENANT = os.environ.get("LIFE_GRAPH_DEFAULT_TENANT", "personal")
API_KEY = os.environ.get("LIFE_GRAPH_API_KEY", "")

mcp = FastMCP(
    "Life Graph Memory",
    instructions=(
        "Brain-inspired memory layer for AI agents. "
        "Store, search, recall, and manage persistent memories across sessions."
    ),
)


def _headers(tenant_id: str | None = None) -> dict[str, str]:
    """Build request headers with tenant and optional auth."""
    h = {
        "Content-Type": "application/json",
        "X-Tenant-ID": tenant_id or DEFAULT_TENANT,
    }
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h


def _extract_data(response: dict[str, Any]) -> Any:
    """Unwrap the Life Graph response envelope ({data: ...})."""
    if isinstance(response, dict) and "data" in response:
        return response["data"]
    return response


# ── Memory Tools ─────────────────────────────────────────────────────────────


@mcp.tool()
async def remember(
    content: str,
    source_type: str = "mcp",
    tags: list[str] | None = None,
    importance: float | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Store a new memory. The system automatically:
    - Extracts facts using a 3-tier pipeline (regex → spaCy → LLM)
    - Scores importance
    - Checks for duplicates (cosine ≥ 0.92)
    - Detects contradictions with existing memories

    Args:
        content: The text to remember (a fact, preference, decision, lesson, etc.)
        source_type: Origin of this memory (mcp, manual, conversation, agent)
        tags: Optional categorization tags
        importance: Override importance score (0.0-1.0). Auto-scored if omitted.
        tenant_id: Tenant scope (defaults to LIFE_GRAPH_DEFAULT_TENANT)
    """
    body: dict[str, Any] = {"content": content, "source_type": source_type}
    if tags:
        body["tags"] = tags
    if importance is not None:
        body["importance"] = importance

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/memories/", json=body, headers=_headers(tenant_id)
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


@mcp.tool()
async def search(
    query: str,
    limit: int = 5,
    search_mode: str = "hybrid",
    min_importance: float | None = None,
    tags: list[str] | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Search across all memories with configurable strategy.

    Modes:
    - "vector": Pure cosine similarity (fastest, semantic only)
    - "hybrid": Vector + BM25 keyword matching (default, best balance)
    - "tri_hybrid": Vector + BM25 + graph entity proximity (most comprehensive)

    Args:
        query: Natural language search query
        limit: Max results (1-100, default 5)
        search_mode: Search strategy (vector, hybrid, or tri_hybrid)
        min_importance: Only return memories above this importance threshold
        tags: Filter by these tags
        tenant_id: Tenant scope
    """
    body: dict[str, Any] = {
        "query": query,
        "limit": limit,
        "search_mode": search_mode,
    }
    if min_importance is not None:
        body["min_importance"] = min_importance
    if tags:
        body["tags"] = tags

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/search/", json=body, headers=_headers(tenant_id)
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


@mcp.tool()
async def recall(
    context: dict[str, Any],
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Proactive recall — retrieves the most relevant memories for the current context.

    Returns memories grouped by category:
    - identity: Core preferences, values, working style
    - decisions: Relevant past decisions and rationale
    - intentions: Pending to-dos or reminders matching this context
    - warnings: Lessons learned, contradictions, caveats

    Uses 6-signal ranking (similarity, context, importance, recency, access frequency,
    trust) with anti-annoyance controls (cooldowns, session caps, dismissal tracking).

    Args:
        context: Current context dict (e.g. {"project": "my-app", "task": "deploy"})
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/search/recall",
            json={"context": context},
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


@mcp.tool()
async def ask(
    question: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Ask a natural language question and get a synthesized answer from memories.

    The system searches for relevant memories, then uses an LLM to compose
    a direct answer citing the source memories.

    Args:
        question: A natural language question (e.g. "What framework does the user prefer?")
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/search/ask",
            json={"question": question},
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


@mcp.tool()
async def forget(
    memory_id: str,
    tenant_id: str | None = None,
) -> dict[str, str]:
    """Delete a specific memory by ID (soft delete — can be unarchived later).

    Args:
        memory_id: UUID of the memory to delete
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.delete(
            f"/api/v1/memories/{memory_id}", headers=_headers(tenant_id)
        )
        resp.raise_for_status()
        return {"status": "deleted", "memory_id": memory_id}


@mcp.tool()
async def reinforce(
    memory_id: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Confirm that a memory is still accurate (reinforce it).

    Resets confidence to 0.9, updates the last_reinforced timestamp,
    and increments the reinforcement counter. Use when the system
    asks "is this still true?" and the user confirms YES.

    Args:
        memory_id: UUID of the memory to reinforce
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            f"/api/v1/memories/{memory_id}/reinforce",
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


@mcp.tool()
async def deny(
    memory_id: str,
    replacement: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Mark a memory as no longer accurate (deny it).

    The memory is marked as 'superseded'. If a replacement string is provided,
    a new memory is created that supersedes the old one (with full history chain).

    Args:
        memory_id: UUID of the memory to deny
        replacement: Optional new content that replaces the denied memory
        tenant_id: Tenant scope
    """
    body: dict[str, Any] = {}
    if replacement:
        body["replacement"] = replacement

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            f"/api/v1/memories/{memory_id}/deny",
            json=body,
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


# ── Identity Tools ───────────────────────────────────────────────────────────


@mcp.tool()
async def beliefs(
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Get the user's current active beliefs and preferences.

    Returns identity memories — things the system believes are true about the user
    right now (preferences, values, decisions, working style).

    Args:
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.get(
            "/api/v1/identity/beliefs", headers=_headers(tenant_id)
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


@mcp.tool()
async def stale_beliefs(
    days: int = 90,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Find beliefs that haven't been accessed in a while and may be outdated.

    Returns stale memories with suggested challenge prompts like:
    "I remember you prefer Django — is that still true?"

    Args:
        days: How many days of inactivity makes a belief 'stale' (default 90)
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.get(
            "/api/v1/identity/stale",
            params={"days": days},
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


# ── Session Tools ────────────────────────────────────────────────────────────


@mcp.tool()
async def start_session(
    context: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Start a new conversation session. Returns session ID for tracking.

    Starting a session enables memory linking — memories created during this
    session are automatically associated with it.

    Args:
        context: Initial context (e.g. {"project": "my-app", "task": "fix login bug"})
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/sessions/start",
            json={"context": context or {}},
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


@mcp.tool()
async def end_session(
    session_id: str,
    summary: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """End a conversation session. Generates an LLM summary and links memories.

    Args:
        session_id: UUID of the session to end
        summary: Optional manual summary (auto-generated if omitted)
        tenant_id: Tenant scope
    """
    body: dict[str, Any] = {}
    if summary:
        body["summary"] = summary

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            f"/api/v1/sessions/{session_id}/end",
            json=body,
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


# ── Intention Tools ──────────────────────────────────────────────────────────


@mcp.tool()
async def set_intention(
    content: str,
    trigger_type: str = "context",
    trigger_condition: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Create a prospective memory (future intention / reminder).

    The system will surface this when the trigger condition is met.

    Args:
        content: What to remember to do (e.g. "Run migrations before deploying")
        trigger_type: When to trigger — "time", "event", or "context" (default)
        trigger_condition: The trigger (e.g. "2026-07-10" or "when deploying")
        tenant_id: Tenant scope
    """
    body: dict[str, Any] = {
        "content": content,
        "trigger_type": trigger_type,
    }
    if trigger_condition:
        body["trigger_condition"] = trigger_condition

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/intentions/", json=body, headers=_headers(tenant_id)
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


# ── Graph Tools ──────────────────────────────────────────────────────────────


@mcp.tool()
async def graph_search(
    query: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Hybrid search combining knowledge graph traversal with vector similarity.

    Finds entities related to the query via the graph, then refines by
    semantic similarity. Best for entity-relationship questions like
    "What tools does the user use for deployment?"

    Args:
        query: Natural language query about entities/relationships
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/graph/search",
            json={"query": query},
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _extract_data(resp.json())


# ── Resources ────────────────────────────────────────────────────────────────


@mcp.resource("memory://stats")
async def memory_stats() -> str:
    """Get system statistics — memory count, session count, gap count."""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10.0) as client:
        resp = await client.get("/admin/stats", headers=_headers())
        if resp.status_code == 200:
            return str(_extract_data(resp.json()))
        return f"Error fetching stats: {resp.status_code}"


@mcp.resource("memory://health")
async def memory_health() -> str:
    """Get service health — database and Redis connectivity status."""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=10.0) as client:
        resp = await client.get("/health")
        if resp.status_code == 200:
            return str(resp.json())
        return f"Unhealthy: {resp.status_code}"


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
