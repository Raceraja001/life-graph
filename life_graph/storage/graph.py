"""Apache AGE graph storage layer.

Provides a ``GraphStore`` class that executes Cypher queries against
the ``life_graph`` graph in PostgreSQL via the Apache AGE extension.

AGE requires per-connection setup (``LOAD 'age'`` and ``SET search_path``),
so this module maintains its own asyncpg connection pool rather than
sharing the SQLAlchemy engine.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import asyncpg

from life_graph.config import settings

logger = logging.getLogger(__name__)

# Graph name used throughout the application
GRAPH_NAME = "life_graph"


def _parse_dsn(database_url: str) -> str:
    """Convert SQLAlchemy-style URL to asyncpg DSN.

    Strips the ``+asyncpg`` driver suffix so asyncpg can parse it.
    """
    return re.sub(r"postgresql\+asyncpg://", "postgresql://", database_url)


def _parse_agtype(raw: str) -> Any:
    """Parse an agtype string returned by AGE into a Python object.

    AGE returns results as ``agtype`` which are JSON-like strings
    with optional ``::vertex`` or ``::edge`` type suffixes.
    """
    if raw is None:
        return None

    # Strip type annotations like ::vertex, ::edge, ::path
    cleaned = re.sub(r"::(?:vertex|edge|path|numeric|integer|float|string)\b", "", str(raw))

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return str(raw)


def _to_cypher_props(props: dict[str, Any]) -> str:
    """Convert a Python dict to AGE Cypher property map syntax.

    AGE Cypher expects ``{key: 'value'}`` (unquoted keys, single-quoted
    string values), not JSON-style ``{"key": "value"}``.
    """
    parts: list[str] = []
    for key, value in props.items():
        if isinstance(value, str):
            safe = value.replace("\\", "\\\\").replace("'", "\\'")
            parts.append(f"{key}: '{safe}'")
        elif isinstance(value, bool):
            parts.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            parts.append(f"{key}: {value}")
        elif isinstance(value, list):
            # Serialize lists as JSON string (AGE doesn't support array properties natively)
            safe = json.dumps(value).replace("\\", "\\\\").replace("'", "\\'")
            parts.append(f"{key}: '{safe}'")
        elif value is None:
            continue
        else:
            safe = str(value).replace("\\", "\\\\").replace("'", "\\'")
            parts.append(f"{key}: '{safe}'")
    return "{" + ", ".join(parts) + "}"


class GraphStore:
    """Async graph store backed by Apache AGE (Cypher over PostgreSQL).

    All Cypher queries are wrapped in AGE's SQL syntax::

        SELECT * FROM cypher('life_graph', $$
            MATCH (n:Technology) RETURN n
        $$) AS (v agtype);

    The store lazily creates a connection pool on first use and
    configures each connection with AGE's required ``LOAD`` and
    ``SET search_path`` commands.

    Usage::

        store = GraphStore()
        results = await store.execute_cypher(
            "MATCH (n:Technology) RETURN n"
        )
    """

    _pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create the asyncpg connection pool."""
        if self._pool is None:
            dsn = _parse_dsn(settings.database_url)
            self._pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=2,
                max_size=settings.database_pool_size,
                init=self._init_connection,
            )
        return self._pool

    @staticmethod
    async def _init_connection(conn: asyncpg.Connection) -> None:
        """Per-connection setup for Apache AGE."""
        await conn.execute("LOAD 'age'")
        await conn.execute(
            'SET search_path = ag_catalog, "$user", public'
        )

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    # ── Core Cypher Execution ─────────────────────────────────

    async def execute_cypher(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query via AGE's SQL wrapper.

        Args:
            cypher: Cypher query string.
            params: Optional parameters (currently injected via
                    string formatting — AGE has limited param support).
            columns: Column aliases for the result set. Defaults
                     to ``["v"]`` for single-column results.

        Returns:
            List of dicts, one per result row.
        """
        if columns is None:
            columns = ["v"]

        col_spec = ", ".join(f"{c} agtype" for c in columns)

        # AGE doesn't support $-params in Cypher — inject safely
        resolved_cypher = cypher
        if params:
            for key, value in params.items():
                placeholder = f"${key}"
                if isinstance(value, str):
                    # Escape single quotes for Cypher string literals
                    safe_val = value.replace("\\", "\\\\").replace("'", "\\'")
                    resolved_cypher = resolved_cypher.replace(
                        placeholder, f"'{safe_val}'"
                    )
                elif isinstance(value, (int, float)):
                    resolved_cypher = resolved_cypher.replace(
                        placeholder, str(value)
                    )
                elif isinstance(value, bool):
                    resolved_cypher = resolved_cypher.replace(
                        placeholder, "true" if value else "false"
                    )
                else:
                    safe_val = json.dumps(value).replace("'", "\\'")
                    resolved_cypher = resolved_cypher.replace(
                        placeholder, f"'{safe_val}'"
                    )

        sql = (
            f"SELECT * FROM cypher('{GRAPH_NAME}', $$ "
            f"{resolved_cypher} "
            f"$$) AS ({col_spec})"
        )

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # AGE requires search_path to include ag_catalog.
            # asyncpg resets search_path (via RESET ALL) when returning
            # connections to the pool, so we must re-set it on every use.
            await conn.execute("LOAD 'age'")
            await conn.execute(
                'SET search_path = ag_catalog, "$user", public'
            )
            try:
                rows = await conn.fetch(sql)
            except Exception:
                logger.exception("Cypher query failed: %s", resolved_cypher[:200])
                raise

        results: list[dict[str, Any]] = []
        for row in rows:
            parsed = {}
            for col in columns:
                raw_value = row.get(col)
                parsed[col] = _parse_agtype(raw_value) if raw_value else None
            results.append(parsed)

        return results

    # ── Vertex Operations ─────────────────────────────────────

    async def create_vertex(
        self, label: str, properties: dict[str, Any]
    ) -> str:
        """Create a vertex with the given label and properties.

        Args:
            label: Vertex label (e.g. ``Technology``, ``Person``).
            properties: Key-value properties for the vertex.

        Returns:
            String representation of the vertex's graph ID.
        """
        props_cypher = _to_cypher_props(properties)
        cypher = f"CREATE (n:{label} {props_cypher}) RETURN id(n)"
        results = await self.execute_cypher(cypher)
        if results:
            return str(results[0]["v"])
        return ""

    async def get_vertex(
        self, label: str, name: str
    ) -> dict[str, Any] | None:
        """Find a vertex by label and name property.

        Returns:
            Vertex data dict or None if not found.
        """
        cypher = "MATCH (n:{label}) WHERE n.name = $name RETURN n".replace(
            "{label}", label
        )
        results = await self.execute_cypher(
            cypher, params={"name": name}
        )
        if results:
            return results[0]["v"]
        return None

    async def upsert_vertex(
        self, label: str, name: str, properties: dict[str, Any] | None = None
    ) -> str:
        """Create a vertex if it doesn't exist, or return existing.

        AGE doesn't support MERGE natively in all versions, so we
        check existence first.

        Returns:
            String representation of the vertex's graph ID.
        """
        existing = await self.get_vertex(label, name)
        if existing:
            vertex_id = existing.get("id", "")
            return str(vertex_id)

        props = {"name": name}
        if properties:
            props.update(properties)
        return await self.create_vertex(label, props)

    # ── Edge Operations ───────────────────────────────────────

    async def create_edge(
        self,
        from_label: str,
        from_name: str,
        to_label: str,
        to_name: str,
        edge_label: str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Create an edge between two vertices identified by label+name.

        Args:
            from_label: Source vertex label.
            from_name: Source vertex name.
            to_label: Target vertex label.
            to_name: Target vertex name.
            edge_label: Relationship type.
            properties: Optional edge properties.

        Returns:
            String representation of the edge's graph ID.
        """
        props_str = _to_cypher_props(properties) if properties else ""
        edge_props = f" {props_str}" if props_str else ""

        cypher = (
            f"MATCH (a:{from_label}), (b:{to_label}) "
            f"WHERE a.name = $from_name AND b.name = $to_name "
            f"CREATE (a)-[e:{edge_label}{edge_props}]->(b) "
            f"RETURN id(e)"
        )
        results = await self.execute_cypher(
            cypher,
            params={"from_name": from_name, "to_name": to_name},
        )
        if results:
            return str(results[0]["v"])
        return ""

    # ── Traversal ─────────────────────────────────────────────

    async def get_neighbors(
        self,
        vertex_name: str,
        vertex_label: str = "Entity",
        edge_label: str | None = None,
        depth: int = 1,
    ) -> list[dict[str, Any]]:
        """Get neighbors of a vertex up to a given depth.

        Args:
            vertex_name: Name property of the source vertex.
            vertex_label: Label of the source vertex.
            edge_label: Optional filter on edge label.
            depth: Maximum traversal depth (1–5).

        Returns:
            List of dicts with neighbor info and relationship type.
        """
        depth = min(max(depth, 1), 5)

        if edge_label:
            rel = f"[r:{edge_label}*1..{depth}]"
        else:
            rel = f"[r*1..{depth}]"

        cypher = (
            f"MATCH (a:{vertex_label})-{rel}-(b) "
            f"WHERE a.name = $name "
            f"RETURN b"
        )
        results = await self.execute_cypher(
            cypher, params={"name": vertex_name}
        )

        neighbors: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in results:
            v = row.get("v")
            if v and isinstance(v, dict):
                name = v.get("properties", {}).get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    neighbors.append(v)

        return neighbors

    async def find_path(
        self,
        from_label: str,
        from_name: str,
        to_label: str,
        to_name: str,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Find a path between two vertices.

        Uses variable-length relationship matching to find any
        connecting path up to ``max_depth`` hops.

        Returns:
            List of vertices along the path, or empty if no path exists.
        """
        max_depth = min(max(max_depth, 1), 10)
        cypher = (
            f"MATCH p = (a:{from_label})-[*1..{max_depth}]-(b:{to_label}) "
            f"WHERE a.name = $from_name AND b.name = $to_name "
            f"RETURN p"
        )
        results = await self.execute_cypher(
            cypher,
            params={"from_name": from_name, "to_name": to_name},
            columns=["p"],
        )

        if not results:
            return []

        # Parse the path — AGE returns it as a nested structure
        path_data = results[0].get("p")
        if isinstance(path_data, list):
            return path_data
        if isinstance(path_data, dict):
            return [path_data]
        return [{"raw": str(path_data)}]

    # ── Search ────────────────────────────────────────────────

    async def search_entities(
        self,
        query: str,
        label: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for entities by name using case-insensitive substring match.

        Args:
            query: Search term to match against entity names.
            label: Optional vertex label filter.

        Returns:
            List of matching vertex dicts.
        """
        target_label = label if label else "Entity"

        # Search across the specific label or all labels if Entity
        if label and label != "Entity":
            cypher = (
                f"MATCH (n:{target_label}) "
                f"WHERE n.name =~ $pattern "
                f"RETURN n"
            )
        else:
            # Search all vertices — use the base Entity label
            # but also check all specific labels
            cypher = (
                f"MATCH (n) "
                f"WHERE n.name =~ $pattern "
                f"RETURN n"
            )

        # AGE uses =~ for regex matching (case-insensitive)
        pattern = f"(?i).*{re.escape(query)}.*"
        results = await self.execute_cypher(
            cypher, params={"pattern": pattern}
        )

        entities: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in results:
            v = row.get("v")
            if v and isinstance(v, dict):
                name = v.get("properties", {}).get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    entities.append(v)

        return entities

    async def get_all_entities(
        self, label: str | None = None
    ) -> list[dict[str, Any]]:
        """List all entities, optionally filtered by label.

        Returns:
            List of vertex dicts.
        """
        if label:
            cypher = f"MATCH (n:{label}) RETURN n"
        else:
            cypher = "MATCH (n) RETURN n"

        results = await self.execute_cypher(cypher)

        entities: list[dict[str, Any]] = []
        for row in results:
            v = row.get("v")
            if v and isinstance(v, dict):
                entities.append(v)

        return entities
