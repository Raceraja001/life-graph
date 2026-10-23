"""Memory search tool — lets a persona read the user's own memories.

Every built-in persona already lists ``memory_search`` in its
``allowed_tools`` (see kernel/personas.py and the read-only ambient
toolset in kernel/ambient.py); until this module existed the registry
intersection in ``ProcessManager._run_agent`` silently dropped the name,
so none of them could read memory at all.

**Read-only by construction.** It runs the same two calls the search
route uses — ``MemoryManager.generate_embedding`` plus
``PostgresMemoryStore.hybrid_search`` — and nothing else. It deliberately
does *not* go through ``services/recall.py``: that engine is driven by a
context fingerprint rather than a query, and its full-disclosure path
writes (7-day cooldown keys, ``touch_many``). Surfacing a memory to an
agent here records no access count, no cooldown and no reinforcement.

**Tenant resolution.** A tool handler only receives LLM-supplied
arguments, so there is no tenant parameter to spoof: the tenant comes
from the ``core/tenant.py`` contextvar when one is set (the request
path), else from the kernel ``TaskContext`` the agent is executing under,
wrapped in ``tenant_scope`` so the storage layer sees it. Both search
calls filter by ``tenant_id`` in SQL. With neither context there is no
tenant to search, and the tool says so instead of guessing.
"""

from __future__ import annotations

import json
import logging
from contextlib import nullcontext
from typing import Any

from life_graph.scoring.ranking import INDEX_CONTENT_CHARS
from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 5
MAX_LIMIT = 20


def _to_row(memory: Any) -> dict[str, Any]:
    """Project one matched memory onto a compact line.

    Five fields, with the same truncation a recall index line uses — the
    full object carries twenty, of which a model reads the content. The
    core is schema-less, so there is no memory-type enum: ``type`` is the
    row's ``source_type`` (capture, manual, inferred, …).
    """
    content = str(memory.content or "")
    if len(content) > INDEX_CONTENT_CHARS:
        content = content[:INDEX_CONTENT_CHARS].rstrip() + "…"
    created_at = getattr(memory, "created_at", None)
    return {
        "id": str(memory.id),
        "content": content,
        "type": memory.source_type,
        "importance": memory.importance,
        "created_at": created_at.isoformat() if created_at else None,
    }


@tool(
    name="memory_search",
    description=(
        "Search the user's own remembered facts, preferences, decisions"
        " and lessons by meaning as well as by keyword. Read-only: it"
        " never stores or modifies anything. Use it before asking the"
        " user something they may have already told you."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to look for, in natural language.",
            },
            "limit": {
                "type": "integer",
                "description": (
                    f"Maximum memories to return. Defaults to {DEFAULT_LIMIT},"
                    f" capped at {MAX_LIMIT}."
                ),
                "default": DEFAULT_LIMIT,
            },
        },
        "required": ["query"],
    },
)
async def memory_search(query: str, limit: int = DEFAULT_LIMIT) -> str:
    """Search the current tenant's active memories for *query*.

    Returns a JSON string. Never raises — every failure comes back as
    {"error": "..."} so the calling persona's tool-loop can react to it
    like any other tool result.
    """
    # Imported here, not at module scope: api.dependencies pulls in the
    # whole service graph, and tools are imported during startup before
    # that is wired up (the delegate.py pattern).
    from life_graph.api.dependencies import get_memory_manager, get_store
    from life_graph.core.task_context import get_current_task_context
    from life_graph.core.tenant import has_tenant_context, tenant_scope

    if has_tenant_context():
        scope: Any = nullcontext()
    else:
        ctx = get_current_task_context()
        if ctx is None:
            return json.dumps(
                {
                    "error": (
                        "memory_search has no tenant context — it can only be"
                        " called from a request or from a persona running"
                        " inside a kernel AgentTask."
                    ),
                }
            )
        scope = tenant_scope(ctx.tenant_id)

    with scope:
        try:
            capped = max(1, min(int(limit), MAX_LIMIT))
            embedding = await get_memory_manager().generate_embedding(query)
            if not embedding:
                return json.dumps(
                    {"error": "Embedding service is unavailable — cannot search memories."}
                )
            hits = await get_store().hybrid_search(
                embedding=embedding,
                query_text=query,
                limit=capped,
                # Pending memories are behind the approval gate; an agent
                # never sees them (same rule as the MCP search tool).
                statuses=("active",),
            )
            results = [_to_row(memory) for memory, _score in hits]
        except Exception as exc:
            # Never the query text: a search can carry personal details.
            logger.warning("memory_search failed (query of %d chars): %s", len(query), exc)
            return json.dumps({"error": f"Memory search failed: {exc}"})

    logger.info("memory_search returned %d memories", len(results))
    return json.dumps({"query": query, "count": len(results), "results": results})


@tool(
    name="memory_forget",
    description=(
        "Forget one of the user's remembered facts when they say it is wrong,"
        " out of date, or ask you to forget it. Pass the id from memory_search."
        " The memory is archived (the user can restore it from the dashboard),"
        " never deleted. Tell the user what you forgot."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "memory_id": {"type": "string", "description": "The id from memory_search."},
            "reason": {
                "type": "string",
                "description": "In a few words, why: 'user said it is wrong', 'out of date'.",
            },
        },
        "required": ["memory_id"],
    },
)
async def memory_forget(memory_id: str, reason: str = "") -> str:
    """Archive one active memory of the current tenant. Never raises."""
    import uuid
    from datetime import UTC, datetime

    from sqlalchemy import text

    from life_graph.core.task_context import get_current_task_context
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
    from life_graph.storage.database import async_session

    if has_tenant_context():
        tenant_id = get_current_tenant_id()
    else:
        ctx = get_current_task_context()
        if ctx is None:
            return json.dumps({"error": "memory_forget has no tenant context."})
        tenant_id = ctx.tenant_id
    try:
        mid = uuid.UUID(str(memory_id))
    except ValueError:
        return json.dumps({"error": "That is not a memory id; use one from memory_search."})
    note = json.dumps(
        {"forgotten": {"at": datetime.now(UTC).isoformat(), "reason": (reason or "")[:200]}}
    )
    try:
        async with async_session() as session:
            row = (
                await session.execute(
                    text(
                        "UPDATE memories SET status = 'archived', updated_at = NOW(),"
                        " properties = COALESCE(properties, '{}'::jsonb) || CAST(:note AS jsonb)"
                        " WHERE id = :id AND tenant_id = :tenant AND status = 'active'"
                        " RETURNING content"
                    ),
                    {"id": mid, "tenant": tenant_id, "note": note},
                )
            ).first()
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_forget failed: %s", exc)
        return json.dumps({"error": f"Could not forget it: {exc}"})
    if row is None:
        return json.dumps({"error": "No active memory with that id."})
    return json.dumps({"forgotten": True, "content": row[0]})


@tool(
    name="memory_about",
    description=(
        "Everything remembered about one person, project or thing the user has"
        " mentioned (e.g. 'Murugan', 'the school app', 'Life Graph'), newest"
        " first, with what it is most often mentioned with. Read-only."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The person, project or thing."},
            "limit": {
                "type": "integer",
                "description": "Maximum memories (default 15).",
                "default": 15,
            },
        },
        "required": ["name"],
    },
)
async def memory_about(name: str, limit: int = 15) -> str:
    """The entity's active memories and related entities, as JSON. Never raises."""
    from life_graph.core.task_context import get_current_task_context
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
    from life_graph.services import entities

    if has_tenant_context():
        tenant_id = get_current_tenant_id()
    else:
        ctx = get_current_task_context()
        if ctx is None:
            return json.dumps({"error": "memory_about has no tenant context."})
        tenant_id = ctx.tenant_id
    try:
        found = await entities.about(tenant_id, name, limit=max(1, min(int(limit), 40)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_about failed: %s", exc)
        return json.dumps({"error": f"Could not look that up: {exc}"})
    if found is None:
        return json.dumps({"name": name, "known": False, "memories": []})
    return json.dumps(
        {
            "name": name,
            "known": True,
            "also_called": found["names"],
            "memories": [_to_row(m) for m in found["memories"]],
            "often_mentioned_with": found["related"],
        }
    )
