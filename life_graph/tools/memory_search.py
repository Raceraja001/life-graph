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

import hashlib
import json
import logging
import re
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


#: The owner asking for something to be kept, in their own message. Jarvis also
#: reads email and web pages; text in those cannot save itself as the owner's
#: own words by telling Jarvis to "remember" it (review 2026-10-23).
SAVE_INTENT = re.compile(
    r"\b(remember|save|note (this|that|it|down)|make a note|keep in mind|"
    r"don'?t forget|do not forget|never forget|jot|write (this|that|it) down)\b",
    re.IGNORECASE,
)
MAX_SAVE_CHARS = 1000


async def _owner_message(ctx: Any) -> str:
    """The owner's message for the run this tool call belongs to, or ""."""
    from life_graph.models.db import AgentTask
    from life_graph.storage.database import async_session

    if ctx is None:
        return ""
    try:
        async with async_session() as session:
            task = await session.get(AgentTask, ctx.root_task_id or ctx.task_id)
    except Exception:  # noqa: BLE001
        logger.warning("memory_save could not read its task", exc_info=True)
        return ""
    if task is None or task.tenant_id != ctx.tenant_id:
        return ""
    return str((task.input or {}).get("message") or "")


@tool(
    name="memory_save",
    description=(
        "Remember something when the user asks you to ('remember that…', 'save"
        " this', 'note that…', 'don't forget…'). Write it as one short sentence"
        " about the user, in their own terms, with any date in full. When it"
        " corrects something you remember, pass that memory's id from"
        " memory_search as replaces_id. Tell the user in a few words what you"
        " saved."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The fact, e.g. 'My car insurance renews on 5 March 2027.'",
            },
            "about": {
                "type": "array",
                "items": {"type": "string"},
                "description": "People, projects or things it is about, e.g. ['Murugan'].",
            },
            "replaces_id": {
                "type": "string",
                "description": "Id of a remembered fact this corrects (from memory_search).",
            },
        },
        "required": ["content"],
    },
)
async def memory_save(
    content: str, about: list[str] | None = None, replaces_id: str | None = None
) -> str:
    """Store one memory in the owner's words. Never raises.

    Active at once only when the owner's own message for this run asks to
    remember something; otherwise it waits in the review queue like any other
    memory the system picks up.
    """
    import uuid

    from life_graph.api.dependencies import get_memory_manager, get_store
    from life_graph.core.task_context import get_current_task_context
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context, tenant_scope
    from life_graph.models.schemas import MemoryCreate

    ctx = get_current_task_context()
    if has_tenant_context():
        tenant_id = get_current_tenant_id()
    elif ctx is not None:
        tenant_id = ctx.tenant_id
    else:
        return json.dumps({"error": "memory_save has no tenant context."})
    text_ = " ".join(str(content or "").split())
    if len(text_) < 3:
        return json.dumps({"error": "Nothing to save."})
    if len(text_) > MAX_SAVE_CHARS:
        return json.dumps({"error": f"Too long: keep it under {MAX_SAVE_CHARS} characters."})
    old_id = None
    if replaces_id:
        try:
            old_id = uuid.UUID(str(replaces_id))
        except ValueError:
            return json.dumps(
                {"error": "replaces_id is not a memory id; use one from memory_search."}
            )

    asked = bool(SAVE_INTENT.search(await _owner_message(ctx)))
    content_hash = hashlib.sha256(text_.lower().encode()).hexdigest()
    try:
        with tenant_scope(tenant_id):
            store = get_store()
            same = await store.find_exact_duplicate(content_hash)
            if same is not None and same.status == "active":
                return json.dumps({"saved": False, "already_remembered": same.content})
            embedding = await get_memory_manager().generate_embedding(text_)
            if same is None and embedding:
                for near, _score in await store.find_similar(embedding, threshold=0.95, limit=3):
                    if near.status == "active" and near.id != old_id:
                        return json.dumps({"saved": False, "already_remembered": near.content})
            if same is not None:
                # The same words were waiting for review: the owner asking settles it.
                row = same
                if asked:
                    await _activate(tenant_id, same.id)
            else:
                row = await store.store(
                    MemoryCreate(
                        content=text_,
                        tags=["explicit_save"],
                        source_type="explicit",
                        importance=0.7,
                        properties={"saved_by": "jarvis"},
                    ),
                    embedding=embedding or None,
                    trust_tier="self",
                    status="active" if asked else "pending",
                    extraction_tier="explicit",
                )
            replaced = None
            if old_id is not None and asked:
                replaced = await _supersede(tenant_id, old_id, row.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_save failed (%d chars): %s", len(text_), exc)
        return json.dumps({"error": f"Could not save it: {exc}"})

    try:
        from life_graph.services import entities

        names = [n for n in (about or []) if isinstance(n, str)]
        names += [name for _, name in await entities.known_in_text(tenant_id, text_)]
        await entities.link(tenant_id, row.id, names)
    except Exception:  # noqa: BLE001
        logger.warning("Entity linking failed for saved memory %s", row.id, exc_info=True)

    out: dict[str, Any] = {"saved": True, "id": str(row.id), "content": row.content}
    if not asked:
        out["status"] = "waiting for the user's review"
    if replaced:
        out["replaced"] = replaced
    return json.dumps(out)


async def _activate(tenant_id: str, memory_id: Any) -> None:
    from sqlalchemy import text

    from life_graph.storage.database import async_session

    async with async_session() as session:
        await session.execute(
            text(
                "UPDATE memories SET status = 'active', updated_at = NOW()"
                " WHERE id = :id AND tenant_id = :t AND status = 'pending'"
            ),
            {"id": memory_id, "t": tenant_id},
        )
        await session.commit()


async def _supersede(tenant_id: str, old_id: Any, new_id: Any) -> str | None:
    """Mark the owner's active memory *old_id* replaced by *new_id*; its content, or None."""
    from sqlalchemy import text

    from life_graph.storage.database import async_session

    async with async_session() as session:
        old = (
            await session.execute(
                text(
                    "UPDATE memories SET status = 'superseded', superseded_by = :new,"
                    " updated_at = NOW()"
                    " WHERE id = :old AND tenant_id = :t AND status = 'active' AND id <> :new"
                    " RETURNING content"
                ),
                {"old": old_id, "new": new_id, "t": tenant_id},
            )
        ).first()
        if old is not None:
            await session.execute(
                text("UPDATE memories SET supersedes = :old WHERE id = :new AND tenant_id = :t"),
                {"old": old_id, "new": new_id, "t": tenant_id},
            )
        await session.commit()
    return old[0] if old else None
