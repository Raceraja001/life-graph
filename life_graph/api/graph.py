"""Graph API routes — knowledge graph queries via Apache AGE.

Provides endpoints for browsing graph entities, executing Cypher
queries, finding paths between entities, and running hybrid
graph+vector searches.

All routes are prefixed with ``/graph`` and tagged for OpenAPI docs.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from life_graph.api.responses import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


# ── Request / Response Schemas ────────────────────────────────


class CypherQuery(BaseModel):
    """Body for executing a raw Cypher query."""

    cypher: str = Field(..., min_length=1, description="Cypher query string")
    params: dict[str, Any] | None = Field(
        None, description="Optional query parameters"
    )
    columns: list[str] | None = Field(
        None, description="Result column names (default: ['v'])"
    )


class GraphEntity(BaseModel):
    """Serialised graph entity (vertex)."""

    name: str
    label: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Serialised graph edge."""

    from_name: str
    to_name: str
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphSearchRequest(BaseModel):
    """Body for hybrid graph+vector search."""

    query: str = Field(..., min_length=1, description="Natural language query")
    label: str | None = Field(None, description="Filter by entity label")
    limit: int = Field(10, ge=1, le=100, description="Max results")
    min_importance: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum importance threshold"
    )


class GraphSearchResult(BaseModel):
    """Results from a hybrid graph+vector search."""

    entities: list[dict[str, Any]] = Field(default_factory=list)
    memories: list[dict[str, Any]] = Field(default_factory=list)
    graph_context: list[dict[str, Any]] = Field(default_factory=list)


# ── Lazy Dependency Helpers ───────────────────────────────────

_graph_store = None
_hybrid_engine = None


def _get_graph_store():
    """Lazy-initialise the GraphStore singleton."""
    global _graph_store
    if _graph_store is None:
        from life_graph.storage.graph import GraphStore
        _graph_store = GraphStore()
    return _graph_store


def _get_hybrid_engine():
    """Lazy-initialise the HybridQueryEngine singleton."""
    global _hybrid_engine
    if _hybrid_engine is None:
        from life_graph.storage.hybrid import HybridQueryEngine
        _hybrid_engine = HybridQueryEngine()
    return _hybrid_engine


# ── Routes ────────────────────────────────────────────────────


@router.get(
    "/entities",
    summary="List all graph entities",
)
async def list_entities(
    label: str | None = Query(None, description="Filter by vertex label"),
):
    """List all entities in the knowledge graph.

    Optionally filter by vertex label (e.g. ``Technology``, ``Person``).
    """
    store = _get_graph_store()
    try:
        raw = await store.get_all_entities(label=label)
    except Exception as exc:
        logger.exception("Failed to list graph entities")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Graph query failed: {exc}",
        ) from exc

    entities: list[GraphEntity] = []
    for v in raw:
        props = v.get("properties", {})
        entities.append(
            GraphEntity(
                name=props.get("name", "unknown"),
                label=v.get("label"),
                properties=props,
            )
        )
    return success_response(data=entities)


@router.get(
    "/entity/{name}",
    summary="Get entity detail with neighbors",
)
async def get_entity(name: str):
    """Get full details for an entity including graph neighbors and related memories."""
    engine = _get_hybrid_engine()
    try:
        return success_response(data=await engine.entity_context(name))
    except Exception as exc:
        logger.exception("Failed to get entity context for %s", name)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Graph query failed: {exc}",
        ) from exc


@router.post(
    "/query",
    summary="Execute a Cypher query",
)
async def execute_cypher(body: CypherQuery):
    """Execute a raw Cypher query against the knowledge graph.

    **Admin-level endpoint** — allows arbitrary read queries.
    Write operations (CREATE, SET, DELETE, MERGE, REMOVE, DROP) are blocked.
    """
    # Security: block write operations
    _WRITE_KEYWORDS = re.compile(
        r"\b(CREATE|SET|DELETE|DETACH|MERGE|REMOVE|DROP|CALL)\b",
        re.IGNORECASE,
    )
    if _WRITE_KEYWORDS.search(body.cypher):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write operations are not allowed via the API. Use read-only Cypher.",
        )

    store = _get_graph_store()
    try:
        result = await store.execute_cypher(
            cypher=body.cypher,
            params=body.params,
            columns=body.columns,
        )
        return success_response(data=result)
    except Exception as exc:
        logger.exception("Cypher query failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cypher query error: {exc}",
        ) from exc


@router.get(
    "/path",
    summary="Find path between two entities",
)
async def find_path(
    from_name: str = Query(..., description="Source entity name"),
    to_name: str = Query(..., description="Target entity name"),
    from_label: str = Query("Entity", description="Source vertex label"),
    to_label: str = Query("Entity", description="Target vertex label"),
    max_depth: int = Query(5, ge=1, le=10, description="Maximum path depth"),
):
    """Find a connecting path between two entities in the knowledge graph."""
    store = _get_graph_store()
    try:
        path = await store.find_path(
            from_label=from_label,
            from_name=from_name,
            to_label=to_label,
            to_name=to_name,
            max_depth=max_depth,
        )
    except Exception as exc:
        logger.exception("Path query failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Graph query failed: {exc}",
        ) from exc

    return success_response(data={
        "from": from_name,
        "to": to_name,
        "path": path,
        "found": len(path) > 0,
    })


@router.post(
    "/search",
    summary="Hybrid graph + vector search",
)
async def hybrid_search(body: GraphSearchRequest):
    """Run a hybrid search combining graph structure with vector similarity.

    The graph narrows entity scope, then vector search refines
    by semantic similarity.
    """
    engine = _get_hybrid_engine()

    graph_filter: dict[str, Any] = {}
    if body.label:
        graph_filter["label"] = body.label
    if body.min_importance is not None:
        graph_filter["min_importance"] = body.min_importance

    try:
        result = await engine.hybrid_search(
            query=body.query,
            graph_filter=graph_filter if graph_filter else None,
            limit=body.limit,
        )
    except Exception as exc:
        logger.exception("Hybrid search failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Hybrid search error: {exc}",
        ) from exc

    return success_response(data=GraphSearchResult(
        entities=result.get("entities", []),
        memories=result.get("memories", []),
        graph_context=result.get("graph_context", []),
    ))
