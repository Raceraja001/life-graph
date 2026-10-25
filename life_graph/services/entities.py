"""The people, projects and things the owner's memories mention, and what is known about each.

Why not the Apache AGE graph: on 2026-10-22 it served almost no retrieval
(entity search needed the whole question to be a substring of a name, the
neighbour step queried a label nothing wrote, vertices had no tenant). The
extractor already names the entities of every fact (``properties.entities``),
so this keeps a plain tenant-scoped index (migration 053):

* :func:`link` records which entities a memory mentions, under a normalised
  key, so "Life-Graph", "life graph" and "Life Graph" are one thing;
* :func:`known_in_text` finds already-known entities named in a question;
* :func:`memories_for` / :func:`about` give everything remembered about one,
  plus the entities most often mentioned with it.

Generic words the extractor tends to list ("user", "merge", "app") are not
entities and are dropped (:data:`NOT_ENTITIES`).
"""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text

from life_graph.storage.database import async_session

if TYPE_CHECKING:
    import uuid

#: Words that name nothing in particular. Seen on 2026-10-23 among the
#: extractor's entities: "user" (3), "merge" (3), and the like.
NOT_ENTITIES = frozenset(
    [
        "user",
        "users",
        "owner",
        "assistant",
        "ai",
        "agent",
        "agents",
        "app",
        "apps",
        "application",
        "system",
        "code",
        "task",
        "tasks",
        "project",
        "projects",
        "model",
        "models",
        "tool",
        "tools",
        "feature",
        "features",
        "merge",
        "pr",
        "prs",
        "commit",
        "branch",
        "test",
        "tests",
        "api",
        "apis",
        "data",
        "database",
        "server",
        "file",
        "files",
        "page",
        "pages",
        "plan",
        "work",
        "job",
        "memory",
        "memories",
        "note",
        "notes",
        "question",
        "answer",
        "today",
        "tomorrow",
        "yesterday",
        "week",
        "month",
    ]
)
MAX_KEY = 200
_CACHE_SECONDS = 60.0
_cache: dict[str, tuple[float, list[tuple[str, uuid.UUID, str]]]] = {}


def normalize(name: str) -> str:
    """The key an entity is stored under: lower case, separators as spaces, no "the"."""
    key = re.sub(r"[-_./\\]+", " ", (name or "").lower())
    key = re.sub(r"[^\w+# ]+", "", key)
    key = re.sub(r"\s+", " ", key).strip()
    key = re.sub(r"^the ", "", key)
    return key[:MAX_KEY]


def is_entity(key: str) -> bool:
    return len(key) >= 2 and not key.isdigit() and key not in NOT_ENTITIES


async def link(tenant_id: str, memory_id: uuid.UUID, names: list[str]) -> int:
    """Record that *memory_id* mentions *names*; return how many new links were made."""
    seen: dict[str, str] = {}
    for name in names or []:
        key = normalize(str(name))
        if is_entity(key) and key not in seen:
            seen[key] = str(name).strip()[:MAX_KEY]
    if not seen:
        return 0
    async with async_session() as session:
        linked = 0
        for key, name in seen.items():
            entity_id = await session.scalar(
                text(
                    "INSERT INTO entities (tenant_id, key, name, mentions) "
                    "VALUES (:t, :k, :n, 0) "
                    "ON CONFLICT (tenant_id, key) DO UPDATE SET updated_at = now() "
                    "RETURNING id"
                ),
                {"t": tenant_id, "k": key, "n": name},
            )
            added = await session.scalar(
                text(
                    "INSERT INTO memory_entities (memory_id, entity_id, tenant_id) "
                    "VALUES (:m, :e, :t) ON CONFLICT DO NOTHING RETURNING 1"
                ),
                {"m": memory_id, "e": entity_id, "t": tenant_id},
            )
            if added:
                # Counted per new link, so linking the same memory twice is harmless.
                await session.execute(
                    text("UPDATE entities SET mentions = mentions + 1 WHERE id = :e"),
                    {"e": entity_id},
                )
                linked += 1
        await session.commit()
    _cache.pop(tenant_id, None)
    return linked


async def _known(tenant_id: str) -> list[tuple[str, uuid.UUID, str]]:
    """(key, id, name) of the tenant's entities, longest key first; cached briefly."""
    hit = _cache.get(tenant_id)
    if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    from life_graph.models.assistant import Entity

    async with async_session() as session:
        rows = (
            await session.execute(
                select(Entity.key, Entity.id, Entity.name).where(Entity.tenant_id == tenant_id)
            )
        ).all()
    known = sorted(((k, i, n) for k, i, n in rows), key=lambda r: -len(r[0]))
    _cache[tenant_id] = (time.monotonic(), known)
    return known


async def known_in_text(tenant_id: str, text_: str) -> list[tuple[uuid.UUID, str]]:
    """Known entities named in *text_* (whole words), as (id, name)."""
    padded = f" {normalize(text_)} "
    found = []
    for key, entity_id, name in await _known(tenant_id):
        if f" {key} " in padded or f" {key}s " in padded:
            found.append((entity_id, name))
    return found


async def memories_for(tenant_id: str, entity_ids: list[uuid.UUID], limit: int = 20) -> list[Any]:
    """Active memories that mention any of *entity_ids*, newest first."""
    if not entity_ids:
        return []
    from life_graph.models.assistant import MemoryEntity
    from life_graph.models.db import Memory

    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(Memory)
                    .join(MemoryEntity, MemoryEntity.memory_id == Memory.id)
                    .where(
                        MemoryEntity.tenant_id == tenant_id,
                        MemoryEntity.entity_id.in_(entity_ids),
                        Memory.tenant_id == tenant_id,
                        Memory.status == "active",
                    )
                    .order_by(Memory.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .unique()
            .all()
        )
    return list(rows)


async def about(tenant_id: str, name: str, limit: int = 20) -> dict[str, Any] | None:
    """Everything remembered about one entity, and what it is most often mentioned with.

    *name* is matched on its key first, then as a whole-word part of a longer
    key ("school" finds "school app"). None when nothing is known by that name.
    """
    from life_graph.models.assistant import Entity, MemoryEntity

    key = normalize(name)
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Entity.id, Entity.key, Entity.name).where(
                    Entity.tenant_id == tenant_id,
                    (Entity.key == key)
                    | Entity.key.like(f"{key} %")
                    | Entity.key.like(f"% {key}")
                    | Entity.key.like(f"% {key} %"),
                )
            )
        ).all()
    if not rows:
        return None
    ids = [r[0] for r in rows]
    memories = await memories_for(tenant_id, ids, limit=limit)
    related: Counter[str] = Counter()
    if memories:
        async with async_session() as session:
            co = (
                await session.execute(
                    select(Entity.name)
                    .join(MemoryEntity, MemoryEntity.entity_id == Entity.id)
                    .where(
                        MemoryEntity.tenant_id == tenant_id,
                        MemoryEntity.memory_id.in_([m.id for m in memories]),
                        Entity.id.notin_(ids),
                    )
                )
            ).all()
        related.update(r[0] for r in co)
    # The entity the name is exactly, else the first it is part of: the phone
    # opens it from Jarvis's answer (GET /jarvis/entities/{id}).
    exact = next((r[0] for r in rows if r[1] == key), rows[0][0])
    return {
        "id": exact,
        "names": [r[2] for r in rows],
        "memories": memories,
        "related": [n for n, _ in related.most_common(8)],
    }
