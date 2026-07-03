"""Hybrid graph + vector query engine.

Combines the :class:`GraphStore` (Apache AGE / Cypher) with the
:class:`PostgresMemoryStore` (pgvector cosine) to enable queries
that leverage both relationship structure and semantic similarity.

Typical workflows:
  - **hybrid_search**: Graph narrows entity scope → vector refines by semantics
  - **entity_context**: Full context for an entity (graph neighbors + related memories)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class HybridQueryEngine:
    """Query engine that blends graph traversal with vector search.

    Lazy-imports storage classes to avoid circular dependency issues
    at module load time.

    Usage::

        engine = HybridQueryEngine()
        results = await engine.hybrid_search("what database do I use?")
    """

    def __init__(self) -> None:
        self._graph_store = None
        self._memory_store = None

    @property
    def graph_store(self):
        """Lazy-initialise the GraphStore."""
        if self._graph_store is None:
            from life_graph.storage.graph import GraphStore
            self._graph_store = GraphStore()
        return self._graph_store

    @property
    def memory_store(self):
        """Lazy-initialise the PostgresMemoryStore."""
        if self._memory_store is None:
            from life_graph.storage.postgres import PostgresMemoryStore
            self._memory_store = PostgresMemoryStore()
        return self._memory_store

    # ── Hybrid Search ─────────────────────────────────────────

    async def hybrid_search(
        self,
        query: str,
        graph_filter: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Graph-narrowed vector search.

        Steps:
        1. Extract entity names from the query
        2. Look up those entities in the graph
        3. Get graph neighbors for additional context
        4. Search memories by vector similarity with graph-derived
           tag/property filters for improved relevance

        Args:
            query: Natural-language search string.
            graph_filter: Optional dict with ``label`` or ``entity`` keys.
            limit: Maximum memories to return.

        Returns:
            Dict with ``entities``, ``memories``, and ``graph_context``.
        """
        entities: list[dict[str, Any]] = []
        graph_context: list[dict[str, Any]] = []

        # Step 1 — Search graph for relevant entities
        try:
            entity_results = await self.graph_store.search_entities(query)
            entities = entity_results[:10]  # Cap to avoid overwhelming

            # If a specific label filter is provided, narrow further
            if graph_filter and "label" in graph_filter:
                label = graph_filter["label"]
                label_results = await self.graph_store.search_entities(
                    query, label=label
                )
                entities = label_results[:10]

            # Step 2 — Get neighbors of found entities
            for entity in entities[:5]:
                props = entity.get("properties", {})
                name = props.get("name", "")
                if name:
                    neighbors = await self.graph_store.get_neighbors(
                        vertex_name=name,
                        vertex_label="Entity",
                        depth=1,
                    )
                    graph_context.extend(neighbors[:5])

        except Exception:
            logger.warning(
                "Graph search failed — falling back to pure vector search",
                exc_info=True,
            )

        # Step 3 — Build filters from graph entities
        filters: dict[str, Any] = {}
        entity_names = []
        for e in entities:
            props = e.get("properties", {})
            name = props.get("name", "")
            if name:
                entity_names.append(name)

        # Use entity names as tag filters if we found any
        if entity_names:
            filters["tags"] = entity_names

        if graph_filter:
            if "min_importance" in graph_filter:
                filters["min_importance"] = graph_filter["min_importance"]

        # Step 4 — Vector search (with or without graph filters)
        memories: list[dict[str, Any]] = []
        try:
            from life_graph.services.embeddings import EmbeddingService

            embedding_service = EmbeddingService()
            embedding = embedding_service.embed(query)

            if embedding:
                rows = await self.memory_store.search_similar(
                    embedding=embedding,
                    limit=limit,
                    filters=filters if entity_names else None,
                )
                memories = [
                    {
                        "id": str(r.id),
                        "content": r.content,
                        "tags": r.tags,
                        "importance": r.importance,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ]

                # If graph-filtered search returned too few, broaden
                if len(memories) < limit // 2 and entity_names:
                    broad_rows = await self.memory_store.search_similar(
                        embedding=embedding,
                        limit=limit,
                    )
                    seen_ids = {m["id"] for m in memories}
                    for r in broad_rows:
                        if str(r.id) not in seen_ids:
                            memories.append({
                                "id": str(r.id),
                                "content": r.content,
                                "tags": r.tags,
                                "importance": r.importance,
                                "created_at": r.created_at.isoformat() if r.created_at else None,
                            })
                    memories = memories[:limit]

        except Exception:
            logger.warning(
                "Embedding service unavailable — returning graph-only results",
                exc_info=True,
            )

        return {
            "entities": [
                e.get("properties", {}) for e in entities
            ],
            "memories": memories,
            "graph_context": [
                e.get("properties", {}) for e in graph_context
            ],
        }

    # ── Entity Context ────────────────────────────────────────

    async def entity_context(
        self, entity_name: str
    ) -> dict[str, Any]:
        """Get full context for a named entity.

        Returns graph neighbors, related entities, and memories
        that reference this entity (by tag or property).

        Args:
            entity_name: The name of the entity to look up.

        Returns:
            Dict with ``entity``, ``neighbors``, and ``memories``.
        """
        # Graph lookup
        entity: dict[str, Any] | None = None
        neighbors: list[dict[str, Any]] = []

        try:
            # Try multiple labels
            for label in ["Entity", "Technology", "Person", "Project",
                          "Decision", "Concept", "Domain"]:
                entity = await self.graph_store.get_vertex(label, entity_name)
                if entity:
                    break

            if entity:
                # Get neighbors across all edge types
                raw_neighbors = await self.graph_store.get_neighbors(
                    vertex_name=entity_name,
                    vertex_label=entity.get("label", "Entity"),
                    depth=2,
                )
                neighbors = [
                    n.get("properties", {}) for n in raw_neighbors
                ]

        except Exception:
            logger.warning(
                "Graph lookup failed for entity %s", entity_name,
                exc_info=True,
            )

        # Memory lookup — find memories that reference this entity
        memories: list[dict[str, Any]] = []
        try:
            rows = await self.memory_store.list_memories(
                filters={"tags": [entity_name]},
                limit=20,
            )
            memories = [
                {
                    "id": str(r.id),
                    "content": r.content,
                    "tags": r.tags,
                    "importance": r.importance,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

            # Also search by properties.entities
            prop_rows = await self.memory_store.list_memories(
                filters={"properties": {"entities": [entity_name]}},
                limit=20,
            )
            seen_ids = {m["id"] for m in memories}
            for r in prop_rows:
                if str(r.id) not in seen_ids:
                    memories.append({
                        "id": str(r.id),
                        "content": r.content,
                        "tags": r.tags,
                        "importance": r.importance,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    })

        except Exception:
            logger.warning(
                "Memory lookup failed for entity %s", entity_name,
                exc_info=True,
            )

        return {
            "entity": entity.get("properties", {}) if entity else {"name": entity_name},
            "neighbors": neighbors,
            "memories": memories,
        }
