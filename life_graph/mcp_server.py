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

import json
import os
import uuid
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.tools import ToolResult

# ── Configuration ────────────────────────────────────────────────────────────

API_BASE = os.environ.get("LIFE_GRAPH_API_URL", "http://localhost:8000")
DEFAULT_TENANT = os.environ.get("LIFE_GRAPH_DEFAULT_TENANT", "personal")
API_KEY = os.environ.get("LIFE_GRAPH_API_KEY", "")

# Progressive-disclosure default for `search` and `recall`. On, because the
# whole point of the index is that a model rarely needs twenty full memory
# objects to decide which two matter: an index line costs roughly a tenth of
# the tokens, and `get_memories` expands the ids that survive that decision.
# The HTTP API keeps defaulting to full objects — this flips the MCP surface
# only, where the caller is always a language model paying per token.
# Set LIFE_GRAPH_MCP_INDEX_ONLY_DEFAULT=false to restore full objects.
INDEX_ONLY_DEFAULT = os.environ.get(
    "LIFE_GRAPH_MCP_INDEX_ONLY_DEFAULT", "true"
).strip().lower() not in {
    "false",
    "0",
    "no",
    "off",
}

mcp = FastMCP(
    "Life Graph Memory",
    instructions=(
        "Brain-inspired memory layer for AI agents. "
        "Store, search, recall, and manage persistent memories across sessions. "
        "Also drives Life Graph's dev-agent: list projects, start a dev task "
        "(or a plan-only task), check its stage, and list approvals waiting on "
        "the human. Approving or rejecting is deliberately NOT available here — "
        "that decision belongs to the person, in the dashboard or mobile app."
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


def _result(payload: Any) -> ToolResult:
    """Return a payload as exactly one compact text block.

    Every tool here used to be annotated ``-> dict[str, Any]``. FastMCP reads
    that annotation, derives an output schema from it, and then sends the
    payload **twice**: once JSON-encoded as a text block in ``content``, and
    again as ``structured_content``. Measured on fastmcp 3.4.5, that is
    almost exactly double the bytes for every call, and a model reads the
    text block.

    Returning ``ToolResult`` opts out of that derivation — the deprecation
    note on ``Tool.serializer`` in ``fastmcp/tools/base.py`` points here:
    "Return ToolResult from your tools for full control over serialization."
    One text block, no structured duplicate, no output schema.

    ``separators`` drops the spaces json.dumps adds by default; ``default=str``
    keeps UUIDs and timestamps from raising.
    """
    if isinstance(payload, str):
        return ToolResult(content=payload)
    return ToolResult(content=json.dumps(payload, separators=(",", ":"), default=str))


# ── Memory Tools ─────────────────────────────────────────────────────────────


@mcp.tool()
async def remember(
    content: str,
    source_type: str = "mcp",
    tags: list[str] | None = None,
    importance: float | None = None,
    tenant_id: str | None = None,
) -> ToolResult:
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
        resp = await client.post("/api/v1/memories/", json=body, headers=_headers(tenant_id))
        resp.raise_for_status()
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def search(
    query: str,
    limit: int = 5,
    search_mode: str = "hybrid",
    min_importance: float | None = None,
    tags: list[str] | None = None,
    index_only: bool = INDEX_ONLY_DEFAULT,
    tenant_id: str | None = None,
) -> ToolResult:
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
        index_only: Return a compact index (id, truncated content, tags, score,
            status) instead of full memory objects — about a tenth of the
            tokens. On by default: pair with `get_memories` to expand only the
            ids you need. Pass false when you genuinely want every full object.
        tenant_id: Tenant scope
    """
    body: dict[str, Any] = {
        "query": query,
        "limit": limit,
        "search_mode": search_mode,
        "index_only": index_only,
    }
    if min_importance is not None:
        body["min_importance"] = min_importance
    if tags:
        body["tags"] = tags

    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post("/api/v1/search/", json=body, headers=_headers(tenant_id))
        resp.raise_for_status()
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def recall(
    context: dict[str, Any],
    index_only: bool = INDEX_ONLY_DEFAULT,
    tenant_id: str | None = None,
) -> ToolResult:
    """Proactive recall — retrieves the most relevant memories for the current context.

    Returns memories grouped by category:
    - identity: Core preferences, values, working style
    - decisions: Relevant past decisions and rationale
    - intentions: Pending to-dos or reminders matching this context
    - warnings: Lessons learned, contradictions, caveats

    Uses 7-signal ranking (semantic similarity, context match, importance, impact,
    recency, access frequency, trust) with anti-annoyance controls (cooldowns,
    session caps, dismissal tracking).

    Args:
        context: Current context dict (e.g. {"project": "my-app", "task": "deploy"})
        index_only: Return a compact index instead of the four populated buckets —
            about a tenth of the tokens. On by default; nothing is marked as
            surfaced until you expand an id with `get_memories`. Pass false to
            get the four populated buckets directly.
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/search/recall",
            json={"context": context, "index_only": index_only},
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def ask(
    question: str,
    tenant_id: str | None = None,
) -> ToolResult:
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
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def get_memories(
    ids: list[str],
    tenant_id: str | None = None,
) -> ToolResult:
    """Expand memory ids to their full content — step 2 of progressive disclosure.

    `search(index_only=True)` and `recall(index_only=True)` return compact lines
    with truncated content. Pass the ids you actually care about here to get the
    full memories in one round trip.

    This is also what marks those memories as surfaced: it sets the recall
    cooldown and records an access (which feeds decay and the frequency ranking
    signal). Listing a memory in an index does none of that — only reading it does.

    Args:
        ids: Memory UUIDs to expand (1-50)
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.post(
            "/api/v1/memories/batch",
            json={"ids": ids},
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def forget(
    memory_id: str,
    tenant_id: str | None = None,
) -> ToolResult:
    """Delete a specific memory by ID (soft delete — can be unarchived later).

    Args:
        memory_id: UUID of the memory to delete
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.delete(f"/api/v1/memories/{memory_id}", headers=_headers(tenant_id))
        resp.raise_for_status()
        return _result({"status": "deleted", "memory_id": memory_id})


@mcp.tool()
async def reinforce(
    memory_id: str,
    tenant_id: str | None = None,
) -> ToolResult:
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
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def deny(
    memory_id: str,
    replacement: str | None = None,
    tenant_id: str | None = None,
) -> ToolResult:
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
        return _result(_extract_data(resp.json()))


# ── Identity Tools ───────────────────────────────────────────────────────────


@mcp.tool()
async def beliefs(
    tenant_id: str | None = None,
) -> ToolResult:
    """Get the user's current active beliefs and preferences.

    Returns identity memories — things the system believes are true about the user
    right now (preferences, values, decisions, working style).

    Args:
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.get("/api/v1/identity/beliefs", headers=_headers(tenant_id))
        resp.raise_for_status()
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def stale_beliefs(
    days: int = 90,
    tenant_id: str | None = None,
) -> ToolResult:
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
        return _result(_extract_data(resp.json()))


# ── Session Tools ────────────────────────────────────────────────────────────


@mcp.tool()
async def start_session(
    context: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> ToolResult:
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
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def end_session(
    session_id: str,
    summary: str | None = None,
    tenant_id: str | None = None,
) -> ToolResult:
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
        return _result(_extract_data(resp.json()))


# ── Intention Tools ──────────────────────────────────────────────────────────


@mcp.tool()
async def set_intention(
    content: str,
    trigger_type: str = "context",
    trigger_condition: str | None = None,
    tenant_id: str | None = None,
) -> ToolResult:
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
        resp = await client.post("/api/v1/intentions/", json=body, headers=_headers(tenant_id))
        resp.raise_for_status()
        return _result(_extract_data(resp.json()))


# ── Graph Tools ──────────────────────────────────────────────────────────────


@mcp.tool()
async def graph_search(
    query: str,
    tenant_id: str | None = None,
) -> ToolResult:
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
        return _result(_extract_data(resp.json()))


# ── Dev-agent Tools ──────────────────────────────────────────────────────────
#
# Lets an editor agent (Claude Code, Cline, ...) drive Life Graph's dev-agent
# pipeline. Starting a task is safe to expose: it goes through the full
# pipeline -- isolated worktree, verifier chain, review, and the driver_pr /
# driver_merge approvals -- exactly like a dashboard-started task. There is
# intentionally no approve/reject tool: whoever calls an MCP tool is a model,
# and every approval gate exists so that a human makes that decision.

_DEV_TASK_LIST_FIELDS = (
    "id",
    "title",
    "project_name",
    "persona",
    "stage",
    "status",
    "error",
    "pr_url",
    "created_at",
)
_APPROVAL_DETAIL_CHARS = 500


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, TypeError):
        return False
    return True


async def _resolve_project_id(
    client: httpx.AsyncClient, project: str, tenant_id: str | None
) -> str:
    """Accept a project id or its registered name (what a model naturally knows)."""
    if _is_uuid(project):
        return project
    resp = await client.get("/api/v1/kernel/projects", headers=_headers(tenant_id))
    resp.raise_for_status()
    projects = (_extract_data(resp.json()) or {}).get("projects") or []
    matches = [p for p in projects if str(p.get("name", "")).lower() == project.lower()]
    if not matches:
        names = ", ".join(sorted(str(p.get("name")) for p in projects)) or "none"
        raise ValueError(f"No registered project named {project!r}. Registered: {names}")
    return str(matches[0]["id"])


@mcp.tool()
async def list_projects(tenant_id: str | None = None) -> ToolResult:
    """List the projects registered with Life Graph's dev-agent.

    Use a project's `name` or `id` with `start_dev_task`.

    Args:
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.get("/api/v1/kernel/projects", headers=_headers(tenant_id))
        resp.raise_for_status()
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def start_dev_task(
    instruction: str,
    project: str,
    persona_name: str = "code-fixer-local",
    plan_only: bool = False,
    spec_first: bool = False,
    tenant_id: str | None = None,
) -> ToolResult:
    """Start a dev-agent task in a registered project (runs in the background).

    The task runs through the full pipeline: an isolated git worktree, the
    verifier chain, review, then `driver_pr` / `driver_merge` approvals that a
    human decides. Nothing reaches the project's default branch without them.
    Poll progress with `get_dev_task`.

    Works best scoped to one file per task. For larger work, use
    `plan_only=True`: the agent writes only a spec (requirements/design/tasks,
    no file changes allowed), a human approves it, and the plan's tasks then
    run one at a time.

    Args:
        instruction: What to do, as specifically as possible
        project: Registered project name (e.g. "life-graph") or its id
        persona_name: Persona whose driver runs the task (default runs locally)
        plan_only: Produce a reviewable plan instead of code
        spec_first: Write a short spec before the code, in the same run
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        project_id = await _resolve_project_id(client, project, tenant_id)
        resp = await client.post(
            "/api/v1/kernel/drivers/tasks",
            json={
                "instruction": instruction,
                "project_id": project_id,
                "persona_name": persona_name,
                "plan_only": plan_only,
                "spec_first": spec_first,
            },
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        task = _extract_data(resp.json()) or {}
        return _result({k: task.get(k) for k in _DEV_TASK_LIST_FIELDS})


@mcp.tool()
async def get_dev_task(task_id: str, tenant_id: str | None = None) -> ToolResult:
    """Get one dev task in full: stage, error, output, spec, PR, and every
    verifier result (which check failed and its evidence).

    Stages: queued, running, landed, needs_review, awaiting_pr, pr_open,
    awaiting_merge, merged, closed, failed, completed.

    Args:
        task_id: The dev task's id (from `start_dev_task` or `list_dev_tasks`)
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.get(
            f"/api/v1/kernel/drivers/tasks/{task_id}", headers=_headers(tenant_id)
        )
        resp.raise_for_status()
        return _result(_extract_data(resp.json()))


@mcp.tool()
async def list_dev_tasks(limit: int = 20, tenant_id: str | None = None) -> ToolResult:
    """List recent dev tasks, newest first, as compact rows (no output text).

    Expand one with `get_dev_task`.

    Args:
        limit: Max tasks (1-200, default 20)
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.get(
            "/api/v1/kernel/drivers/tasks",
            params={"limit": limit},
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        rows = _extract_data(resp.json()) or []
        return _result([{k: r.get(k) for k in _DEV_TASK_LIST_FIELDS} for r in rows])


@mcp.tool()
async def list_approvals(
    status: str = "pending",
    limit: int = 20,
    tenant_id: str | None = None,
) -> ToolResult:
    """List items waiting on the human: PRs to open, merges, plans, deploys, ...

    Read-only on purpose. Approving or rejecting is the person's decision and
    happens in the Life Graph dashboard or mobile app, never from here.

    Args:
        status: pending (default), approved, rejected, or all
        limit: Max items (1-500, default 20)
        tenant_id: Tenant scope
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.get(
            "/api/v1/approvals",
            params={"status": status, "limit": limit},
            headers=_headers(tenant_id),
        )
        resp.raise_for_status()
        rows = _extract_data(resp.json()) or []
        return _result(
            [
                {
                    "id": r.get("id"),
                    "kind": r.get("kind"),
                    "title": r.get("title"),
                    "status": r.get("status"),
                    "detail": (r.get("detail") or "")[:_APPROVAL_DETAIL_CHARS],
                    "created_at": r.get("created_at"),
                }
                for r in rows
            ]
        )


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
