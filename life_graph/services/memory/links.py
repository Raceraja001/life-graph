"""Service for bidirectional memory links (Zettelkasten-style).

Manages typed relationships between memories, stored both in PostgreSQL
(for relational queries) and Apache AGE graph (for traversals).

Supported link types:
- BECAUSE — causal link
- EVIDENCED_BY — supporting evidence
- RELATED_TO — semantic similarity
- CONTRADICTS — conflicting information
- SUPERSEDES — updated version
- LEADS_TO — temporal sequence
- ASSOCIATED — learned "said/used together" links. Written only by
  services/memory/associations.py (one row per pair, lower id as source), so
  the public API does not accept it (models/schemas.py MemoryLinkCreate).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError

from life_graph.core.errors import (
    FOREIGN_KEY_VIOLATION,
    UNIQUE_VIOLATION,
    ConflictError,
    InvalidInputError,
    NotFoundError,
    sqlstate,
)
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Memory, MemoryLink
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

VALID_LINK_TYPES = frozenset(
    {
        "BECAUSE",
        "EVIDENCED_BY",
        "RELATED_TO",
        "CONTRADICTS",
        "SUPERSEDES",
        "LEADS_TO",
        # Said or used together; strengthens with use (services/memory/associations.py).
        "ASSOCIATED",
    }
)

#: The one message for a missing memory and another tenant's memory alike.
MEMORY_NOT_FOUND = "Memory not found"


async def _both_in_tenant(
    session: Any, source_id: uuid.UUID, target_id: uuid.UUID, tenant_id: str
) -> bool:
    """True when both memories exist and belong to *tenant_id*."""
    found = await session.scalars(
        select(Memory.id).where(
            Memory.id.in_([source_id, target_id]),
            Memory.tenant_id == tenant_id,
        )
    )
    return set(found.all()) == {source_id, target_id}


async def create_link(
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    link_type: str,
    strength: float = 0.5,
    properties: dict[str, Any] | None = None,
    tenant_id: str = "legacy",
) -> MemoryLink:
    """Create a link between two memories in DB and optionally in the AGE graph.

    Args:
        source_id: UUID of the source memory.
        target_id: UUID of the target memory.
        link_type: Relationship type (must be in VALID_LINK_TYPES).
        strength: Confidence/strength of the link (0.0–1.0).
        properties: Optional JSONB properties.
        tenant_id: Tenant identifier.

    Returns:
        The created MemoryLink ORM instance.

    Raises:
        InvalidInputError: If link_type is invalid or source_id == target_id.
        ConflictError: If this exact link (source, target, type) already exists.
        NotFoundError: If either memory does not exist or belongs to another
            tenant. The two cases are reported the same way, so this is not a
            way to learn whether another tenant's memory id exists.
        (All three are ValueErrors — core/errors.py.)
    """
    if link_type not in VALID_LINK_TYPES:
        raise InvalidInputError(
            f"Invalid link_type '{link_type}'. Must be one of {sorted(VALID_LINK_TYPES)}"
        )
    if source_id == target_id:
        raise InvalidInputError("Cannot link a memory to itself")

    async with async_session() as session:
        # The foreign keys only prove the memories exist, in any tenant. Both
        # ends must be this tenant's, or one tenant could link (and, through
        # the link graph, reach) another tenant's memories.
        if not await _both_in_tenant(session, source_id, target_id, tenant_id):
            raise NotFoundError(MEMORY_NOT_FOUND)
        link = MemoryLink(
            source_memory_id=source_id,
            target_memory_id=target_id,
            link_type=link_type,
            strength=max(0.0, min(1.0, strength)),
            properties=properties or {},
            tenant_id=tenant_id,
        )
        session.add(link)
        try:
            await session.commit()
        except IntegrityError as exc:
            # The SQLSTATE decides, not the message text (audit L3):
            # UNIQUE(source_memory_id, target_memory_id, link_type) from
            # migration 009, and the two foreign keys to memories.
            state = sqlstate(exc)
            if state == UNIQUE_VIOLATION:
                raise ConflictError(
                    "Link already exists between these memories with this type"
                ) from exc
            if state == FOREIGN_KEY_VIOLATION:
                raise NotFoundError(MEMORY_NOT_FOUND) from exc
            raise
        await session.refresh(link)

    # Sync to AGE graph (best-effort)
    await _sync_link_to_graph(source_id, target_id, link_type, strength, tenant_id)

    return link


async def get_links(
    memory_id: uuid.UUID,
    direction: str = "both",
    link_type: str | None = None,
    tenant_id: str | None = None,
) -> list[MemoryLink]:
    """Query links for a memory.

    Args:
        memory_id: The memory to query links for.
        direction: 'outgoing', 'incoming', or 'both'.
        link_type: Optional filter by link type.
        tenant_id: Optional tenant filter.

    Returns:
        List of MemoryLink instances.
    """
    async with async_session() as session:
        conditions = []

        if direction == "outgoing":
            conditions.append(MemoryLink.source_memory_id == memory_id)
        elif direction == "incoming":
            conditions.append(MemoryLink.target_memory_id == memory_id)
        else:
            conditions.append(
                or_(
                    MemoryLink.source_memory_id == memory_id,
                    MemoryLink.target_memory_id == memory_id,
                )
            )

        if link_type is not None:
            conditions.append(MemoryLink.link_type == link_type)
        if tenant_id is not None:
            conditions.append(MemoryLink.tenant_id == tenant_id)

        stmt = select(MemoryLink).where(and_(*conditions))
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def delete_link(link_id: uuid.UUID) -> bool:
    """Delete a link by its ID.

    Returns:
        True if a link was deleted, False otherwise.
    """
    async with async_session() as session:
        stmt = delete(MemoryLink).where(
            MemoryLink.id == link_id,
            MemoryLink.tenant_id == get_current_tenant_id(),
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def get_link_graph(
    memory_id: uuid.UUID,
    depth: int = 2,
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get linked memories for context expansion via BFS traversal.

    Args:
        memory_id: Starting memory.
        depth: Maximum traversal depth (1–5).
        tenant_id: Optional tenant filter.

    Returns:
        List of dicts with memory data, link_type, strength, and depth.
    """
    depth = min(max(depth, 1), 5)
    visited: set[uuid.UUID] = {memory_id}
    results: list[dict[str, Any]] = []
    current_frontier: set[uuid.UUID] = {memory_id}

    async with async_session() as session:
        for current_depth in range(1, depth + 1):
            if not current_frontier:
                break

            # Find all links touching the current frontier
            stmt = select(MemoryLink).where(
                or_(
                    MemoryLink.source_memory_id.in_(current_frontier),
                    MemoryLink.target_memory_id.in_(current_frontier),
                )
            )
            if tenant_id is not None:
                stmt = stmt.where(MemoryLink.tenant_id == tenant_id)

            result = await session.execute(stmt)
            links = result.scalars().all()

            next_frontier: set[uuid.UUID] = set()
            neighbor_ids: set[uuid.UUID] = set()

            for link in links:
                # Determine the neighbor (the other side of the link)
                if link.source_memory_id in current_frontier:
                    neighbor_id = link.target_memory_id
                else:
                    neighbor_id = link.source_memory_id

                if neighbor_id in visited:
                    continue

                visited.add(neighbor_id)
                next_frontier.add(neighbor_id)
                neighbor_ids.add(neighbor_id)

                results.append(
                    {
                        "memory_id": str(neighbor_id),
                        "link_type": link.link_type,
                        "strength": link.strength,
                        "depth": current_depth,
                        "link_id": str(link.id),
                    }
                )

            # Fetch actual memory data for neighbors found at this depth
            if neighbor_ids:
                mem_stmt = select(Memory).where(Memory.id.in_(neighbor_ids))
                mem_result = await session.execute(mem_stmt)
                mem_map = {m.id: m for m in mem_result.scalars().all()}

                for item in results:
                    if item["depth"] == current_depth:
                        mem = mem_map.get(uuid.UUID(item["memory_id"]))
                        if mem:
                            item["content"] = mem.content
                            item["importance"] = mem.importance
                            item["tags"] = mem.tags or []
                            item["status"] = mem.status

            current_frontier = next_frontier

    return results


async def auto_link_memories(
    memories: list[Memory],
    threshold: float = 0.80,
    tenant_id: str = "legacy",
) -> int:
    """Auto-detect RELATED_TO links via embedding cosine similarity.

    Compares all pairs of memories with embeddings and creates
    RELATED_TO links for pairs with cosine similarity above threshold.

    Args:
        memories: List of Memory ORM instances with embeddings.
        threshold: Minimum cosine similarity to create a link.
        tenant_id: Tenant identifier.

    Returns:
        Number of links created.
    """
    import numpy as np

    # Filter to memories that have embeddings
    embedded = [m for m in memories if m.embedding is not None]
    if len(embedded) < 2:
        return 0

    links_created = 0

    for i in range(len(embedded)):
        for j in range(i + 1, len(embedded)):
            a = np.array(embedded[i].embedding, dtype=np.float32)
            b = np.array(embedded[j].embedding, dtype=np.float32)

            # Cosine similarity
            dot = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                continue
            similarity = float(dot / (norm_a * norm_b))

            if similarity >= threshold:
                try:
                    await create_link(
                        source_id=embedded[i].id,
                        target_id=embedded[j].id,
                        link_type="RELATED_TO",
                        strength=round(similarity, 4),
                        properties={
                            "auto_detected": True,
                            "cosine_similarity": round(similarity, 4),
                        },
                        tenant_id=tenant_id,
                    )
                    links_created += 1
                except Exception:
                    # Skip duplicates or other errors
                    logger.debug(
                        "Could not auto-link %s ↔ %s",
                        embedded[i].id,
                        embedded[j].id,
                        exc_info=True,
                    )

    return links_created


async def _sync_link_to_graph(
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    link_type: str,
    strength: float,
    tenant_id: str,
) -> None:
    """Best-effort sync of a memory link to the Apache AGE graph."""
    try:
        from life_graph.storage.graph import GraphStore

        graph = GraphStore()
        await graph.upsert_vertex(
            label="Memory",
            name=str(source_id),
            properties={"memory_id": str(source_id)},
            tenant_id=tenant_id,
        )
        await graph.upsert_vertex(
            label="Memory",
            name=str(target_id),
            properties={"memory_id": str(target_id)},
            tenant_id=tenant_id,
        )
        await graph.create_edge(
            from_label="Memory",
            from_name=str(source_id),
            to_label="Memory",
            to_name=str(target_id),
            edge_label=link_type,
            properties={"strength": strength},
            tenant_id=tenant_id,
        )
    except Exception:
        logger.debug("Graph store not available for link sync", exc_info=True)
