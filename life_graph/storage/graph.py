"""Apache AGE graph storage layer.

Provides a ``GraphStore`` class that executes Cypher queries against
the ``life_graph`` graph in PostgreSQL via the Apache AGE extension.

AGE requires per-connection setup (``LOAD 'age'`` and ``SET search_path``),
so this module maintains its own asyncpg connection pool rather than
sharing the SQLAlchemy engine.

AGE is **optional**. It is a compiled extension that managed Postgres
(Supabase, Neon, RDS) and the stock ``pgvector/pgvector:pg16`` image do not
carry, so every entry point here degrades to an empty result rather than
raising when the extension, the graph, or ``settings.graph_enabled`` is
missing. See :func:`_get_pool`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import asyncpg

from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id, has_tenant_context

logger = logging.getLogger(__name__)

# Graph name used throughout the application
GRAPH_NAME = "life_graph"

# Tenant used when a caller passes none and no tenant context is set.
DEFAULT_GRAPH_TENANT = "default"

# Labels are spliced into the Cypher text, because AGE cannot parameterise them.
# Anything looser lets ``Entity) RETURN n //`` comment out the tenant filter.
LABEL_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"

# A $param outside a string literal. Literals are matched first so that text
# already in the query (edge properties, say) is never read as a placeholder.
_PLACEHOLDER = re.compile(r"'(?:\\.|[^'\\])*'|\$(\w+)")


# ── Process-wide pool + availability probe ────────────────────
#
# Both are module-level on purpose.
#
# The pool was previously declared as a class attribute but assigned as an
# instance attribute, so every ``GraphStore()`` built its own pool — and
# callers like ``services/memory/links.py`` construct one per link and never
# close it. One pool per process is the intent.
#
# The availability answer is cached for the same reason, but more sharply: on
# a database without AGE, ``asyncpg.create_pool`` fails in ``init`` (``LOAD
# 'age'``) and leaves the pool unset, so an uncached probe would retry the
# connection on *every* call for the life of the process. One failed probe
# disables the graph until restart.
_pool: asyncpg.Pool | None = None
_pool_lock = asyncio.Lock()

# None = not probed yet, True/False = the cached answer.
_available: bool | None = None


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


def _resolve_tenant(tenant_id: str | None) -> str:
    """The given tenant, else the current context's, else the default."""
    if tenant_id is not None:
        return tenant_id
    return get_current_tenant_id() if has_tenant_context() else DEFAULT_GRAPH_TENANT


def _safe_label(label: str) -> str:
    """Return ``label`` if it is a bare identifier.

    Raises:
        ValueError: The label could alter the query it is spliced into.
    """
    if not re.fullmatch(LABEL_PATTERN, label):
        raise ValueError(f"Invalid graph label: {label!r}")
    return label


def _cypher_literal(value: Any) -> str:
    """Render a parameter value as a Cypher literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        # Escape single quotes for Cypher string literals
        safe_val = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{safe_val}'"
    if isinstance(value, (int, float)):
        return str(value)
    safe_val = json.dumps(value).replace("'", "\\'")
    return f"'{safe_val}'"


def _dollar_tag(text: str) -> str:
    """A dollar-quote tag that does not occur in ``text``.

    A plain ``$$`` wrapper would be closed by a value containing ``$$``, and
    everything after it would run as SQL.
    """
    tag = "$cypher$"
    while tag in text:
        tag = f"{tag[:-1]}q$"
    return tag


def _hop_chain(
    hops: int,
    from_label: str,
    to_label: str | None = None,
    edge_label: str | None = None,
) -> tuple[str, str]:
    """Build a fixed-length pattern and a tenant filter covering every vertex.

    Traversals are spelled out hop by hop because AGE 1.5 has no way to filter
    the inside of a ``[*1..n]`` match: ``ALL(x IN nodes(p) ...)`` and list
    comprehensions are syntax errors there. Filtering only the endpoints would
    let a walk pass through another tenant's vertex.

    Returns:
        ``(pattern, where)``, binding the endpoints as ``a`` and ``b`` and
        comparing each vertex to ``$tid``.
    """
    names = ["a", *(f"n{i}" for i in range(1, hops)), "b"]
    vertices = [f"({name})" for name in names]
    vertices[0] = f"(a:{_safe_label(from_label)})"
    if to_label:
        vertices[-1] = f"(b:{_safe_label(to_label)})"
    rel = f"-[:{_safe_label(edge_label)}]-" if edge_label else "-[]-"
    return rel.join(vertices), " AND ".join(f"{name}.tenant_id = $tid" for name in names)


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


async def _get_pool() -> asyncpg.Pool | None:
    """Return the process-wide AGE pool, or ``None`` if the graph is unusable.

    ``None`` is returned when the graph is switched off
    (``LIFE_GRAPH_GRAPH_ENABLED=false``), when the AGE extension is missing, or
    when the ``life_graph`` graph was never created — the three ways a plain
    ``pgvector/pgvector:pg16`` or managed-Postgres deployment looks. The answer
    is cached for the process; a caller that gets ``None`` should return an
    empty result, not raise.
    """
    global _pool, _available

    if not settings.graph_enabled:
        return None
    if _available is False:
        return None
    if _pool is not None:
        return _pool

    async with _pool_lock:
        # Re-check under the lock — concurrent callers race to the first probe.
        if _available is False:
            return None
        if _pool is not None:
            return _pool

        dsn = _parse_dsn(settings.database_url)
        try:
            pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=2,
                max_size=settings.database_pool_size,
                init=GraphStore._init_connection,
            )
        except Exception:
            _available = False
            logger.warning(
                "Apache AGE is unavailable (LOAD 'age' failed) — graph search is "
                "disabled for this process; vector+BM25 search is unaffected.",
                exc_info=True,
            )
            return None

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT 1 FROM ag_catalog.ag_graph WHERE name = $1", GRAPH_NAME
                )
        except Exception:
            await pool.close()
            _available = False
            logger.warning(
                "Apache AGE graph catalog unreadable — graph search is disabled for this process.",
                exc_info=True,
            )
            return None

        if row is None:
            await pool.close()
            _available = False
            logger.warning(
                "Graph %r does not exist (migration 002 was skipped) — graph "
                "search is disabled for this process.",
                GRAPH_NAME,
            )
            return None

        _pool = pool
        _available = True
        return _pool


async def close_pool() -> None:
    """Close the process-wide pool and forget the cached probe result."""
    global _pool, _available
    if _pool is not None:
        await _pool.close()
        _pool = None
    _available = None


async def graph_available() -> bool:
    """Whether Cypher queries can run right now (probing once, then cached)."""
    return await _get_pool() is not None


async def graph_status(probe: bool = False) -> str:
    """``"disabled"`` | ``"unavailable"`` | ``"enabled"`` — for /health.

    Args:
        probe: Connect once to settle the answer if it has not been settled
            yet. Off by default so a status read never opens a connection.
    """
    if not settings.graph_enabled:
        return "disabled"
    if _available is None and probe:
        await _get_pool()
    if _available is False:
        return "unavailable"
    return "enabled"


class GraphStore:
    """Async graph store backed by Apache AGE (Cypher over PostgreSQL).

    All Cypher queries are wrapped in AGE's SQL syntax::

        SELECT * FROM cypher('life_graph', $$
            MATCH (n:Technology) RETURN n
        $$) AS (v agtype);

    Connections come from one process-wide pool, created on first use and
    configured with AGE's required ``LOAD`` and ``SET search_path`` commands.
    Instances are therefore cheap and interchangeable.

    Every method returns an empty result (``[]`` / ``""`` / ``None`` / an empty
    dict) rather than raising when the graph is unavailable.

    Usage::

        store = GraphStore()
        results = await store.execute_cypher(
            "MATCH (n:Technology) RETURN n"
        )
    """

    async def _get_pool(self) -> asyncpg.Pool | None:
        """The process-wide asyncpg pool, or ``None`` when AGE is unusable."""
        return await _get_pool()

    @staticmethod
    async def _init_connection(conn: asyncpg.Connection) -> None:
        """Per-connection setup for Apache AGE."""
        await conn.execute("LOAD 'age'")
        await conn.execute('SET search_path = ag_catalog, "$user", public')

    async def close(self) -> None:
        """Release this instance. A no-op: the pool is shared by the process.

        Instances are cheap handles on the one process-wide pool. This used to
        call :func:`close_pool`, so one job finishing (micro-consolidation,
        after every session end) closed the pool under every concurrent graph
        query. Process shutdown is the only place to call :func:`close_pool`.
        """

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
            List of dicts, one per result row. Empty when the graph is
            disabled or Apache AGE is unavailable.
        """
        if columns is None:
            columns = ["v"]

        col_spec = ", ".join(f"{c} agtype" for c in columns)

        # AGE doesn't support $-params in Cypher — inject safely, in one pass so
        # that a value containing "$tid" is not expanded by the next parameter.
        resolved_cypher = cypher
        if params:
            resolved_cypher = _PLACEHOLDER.sub(
                lambda m: (
                    _cypher_literal(params[m.group(1)]) if m.group(1) in params else m.group(0)
                ),
                cypher,
            )

        tag = _dollar_tag(resolved_cypher)
        sql = f"SELECT * FROM cypher('{GRAPH_NAME}', {tag} {resolved_cypher} {tag}) AS ({col_spec})"

        # Short-circuit *before* touching the pool: ``_get_pool`` is not inside
        # the try/except below, so a connection failure here would escape as an
        # exception rather than an empty result.
        pool = await _get_pool()
        if pool is None:
            logger.debug("Graph disabled — skipping Cypher: %s", resolved_cypher[:120])
            return []

        async with pool.acquire() as conn:
            # AGE requires search_path to include ag_catalog.
            # asyncpg resets search_path (via RESET ALL) when returning
            # connections to the pool, so we must re-set it on every use.
            await conn.execute("LOAD 'age'")
            await conn.execute('SET search_path = ag_catalog, "$user", public')
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
        self, label: str, properties: dict[str, Any], tenant_id: str | None = None
    ) -> str:
        """Create a vertex with the given label and properties.

        Args:
            label: Vertex label (e.g. ``Technology``, ``Person``).
            properties: Key-value properties for the vertex.
            tenant_id: Owning tenant. Defaults to the current tenant, and
                overrides any ``tenant_id`` in ``properties``.

        Returns:
            String representation of the vertex's graph ID.
        """
        props_cypher = _to_cypher_props({**properties, "tenant_id": _resolve_tenant(tenant_id)})
        cypher = f"CREATE (n:{_safe_label(label)} {props_cypher}) RETURN id(n)"
        results = await self.execute_cypher(cypher)
        if results:
            return str(results[0]["v"])
        return ""

    async def get_vertex(
        self, label: str, name: str, tenant_id: str | None = None
    ) -> dict[str, Any] | None:
        """Find a tenant's vertex by label and name property.

        Returns:
            Vertex data dict or None if not found.
        """
        cypher = (
            f"MATCH (n:{_safe_label(label)}) WHERE n.name = $name AND n.tenant_id = $tid RETURN n"
        )
        results = await self.execute_cypher(
            cypher, params={"name": name, "tid": _resolve_tenant(tenant_id)}
        )
        if results:
            return results[0]["v"]
        return None

    async def upsert_vertex(
        self,
        label: str,
        name: str,
        properties: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> str:
        """Create a vertex if the tenant doesn't have it, or return existing.

        AGE doesn't support MERGE natively in all versions, so we
        check existence first.

        Returns:
            String representation of the vertex's graph ID.
        """
        tenant_id = _resolve_tenant(tenant_id)
        existing = await self.get_vertex(label, name, tenant_id=tenant_id)
        if existing:
            vertex_id = existing.get("id", "")
            return str(vertex_id)

        props = {"name": name}
        if properties:
            props.update(properties)
        return await self.create_vertex(label, props, tenant_id=tenant_id)

    # ── Edge Operations ───────────────────────────────────────

    async def create_edge(
        self,
        from_label: str,
        from_name: str,
        to_label: str,
        to_name: str,
        edge_label: str,
        properties: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> str:
        """Create an edge between two of a tenant's vertices, by label+name.

        Args:
            from_label: Source vertex label.
            from_name: Source vertex name.
            to_label: Target vertex label.
            to_name: Target vertex name.
            edge_label: Relationship type.
            properties: Optional edge properties.
            tenant_id: Tenant both vertices must belong to. Defaults to the
                current tenant.

        Returns:
            String representation of the edge's graph ID, or ``""`` when either
            vertex is missing from this tenant.
        """
        props_str = _to_cypher_props(properties) if properties else ""
        edge_props = f" {props_str}" if props_str else ""

        cypher = (
            f"MATCH (a:{_safe_label(from_label)}), (b:{_safe_label(to_label)}) "
            f"WHERE a.name = $from_name AND a.tenant_id = $tid "
            f"AND b.name = $to_name AND b.tenant_id = $tid "
            f"CREATE (a)-[e:{_safe_label(edge_label)}{edge_props}]->(b) "
            f"RETURN id(e)"
        )
        results = await self.execute_cypher(
            cypher,
            params={
                "from_name": from_name,
                "to_name": to_name,
                "tid": _resolve_tenant(tenant_id),
            },
        )
        if results:
            return str(results[0]["v"])
        return ""

    async def create_edge_if_absent(
        self,
        from_label: str,
        from_name: str,
        to_label: str,
        to_name: str,
        edge_label: str,
        properties: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> str:
        """Create an edge unless the two vertices are already joined by one.

        The existing-edge check ignores direction, so a symmetric relation
        such as ``related_to`` written ``a->b`` once and ``b->a`` later is
        still one edge. AGE has no reliable ``MERGE`` across versions (see
        :meth:`upsert_vertex`), so this matches first, then creates.

        Returns:
            The new edge's graph ID, or ``""`` when the edge already existed or
            either vertex is missing from this tenant.
        """
        tid = _resolve_tenant(tenant_id)
        existing = await self.execute_cypher(
            f"MATCH (a:{_safe_label(from_label)})-[e:{_safe_label(edge_label)}]-"
            f"(b:{_safe_label(to_label)}) "
            f"WHERE a.name = $from_name AND a.tenant_id = $tid "
            f"AND b.name = $to_name AND b.tenant_id = $tid "
            f"RETURN id(e) LIMIT 1",
            params={"from_name": from_name, "to_name": to_name, "tid": tid},
        )
        if existing:
            return ""
        return await self.create_edge(
            from_label,
            from_name,
            to_label,
            to_name,
            edge_label,
            properties=properties,
            tenant_id=tid,
        )

    # ── Traversal ─────────────────────────────────────────────

    async def get_neighbors(
        self,
        vertex_name: str,
        vertex_label: str = "Entity",
        edge_label: str | None = None,
        depth: int = 1,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get a tenant's neighbors of a vertex up to a given depth.

        Args:
            vertex_name: Name property of the source vertex.
            vertex_label: Label of the source vertex.
            edge_label: Optional filter on edge label.
            depth: Maximum traversal depth (1–5).
            tenant_id: Tenant every vertex on the walk must belong to.
                Defaults to the current tenant.

        Returns:
            List of dicts with neighbor info and relationship type.
        """
        depth = min(max(depth, 1), 5)
        tenant_id = _resolve_tenant(tenant_id)

        neighbors: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hops in range(1, depth + 1):
            pattern, scope = _hop_chain(hops, vertex_label, edge_label=edge_label)
            results = await self.execute_cypher(
                f"MATCH {pattern} WHERE a.name = $name AND {scope} RETURN b",
                params={"name": vertex_name, "tid": tenant_id},
            )
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
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find a path between two vertices, staying inside one tenant.

        Tries each length up to ``max_depth`` hops in turn, so the path
        returned is a shortest one.

        Returns:
            List of vertices along the path, or empty if no path exists.
        """
        max_depth = min(max(max_depth, 1), 10)
        tenant_id = _resolve_tenant(tenant_id)

        for hops in range(1, max_depth + 1):
            pattern, scope = _hop_chain(hops, from_label, to_label)
            results = await self.execute_cypher(
                f"MATCH p = {pattern} "
                f"WHERE a.name = $from_name AND b.name = $to_name AND {scope} "
                f"RETURN p",
                params={"from_name": from_name, "to_name": to_name, "tid": tenant_id},
                columns=["p"],
            )
            if not results:
                continue

            # Parse the path — AGE returns it as a nested structure
            path_data = results[0].get("p")
            if isinstance(path_data, list):
                return path_data
            if isinstance(path_data, dict):
                return [path_data]
            return [{"raw": str(path_data)}]

        return []

    # ── Search ────────────────────────────────────────────────

    async def search_entities(
        self,
        query: str,
        label: str | None = None,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search a tenant's entities by case-insensitive substring match on name.

        Args:
            query: Search term to match against entity names.
            label: Optional vertex label filter.
            tenant_id: Tenant to search. Defaults to the current tenant.

        Returns:
            List of matching vertex dicts.
        """
        # Search the specific label, or every vertex when the label is Entity
        match = f"MATCH (n:{_safe_label(label)})" if label and label != "Entity" else "MATCH (n)"
        cypher = f"{match} WHERE n.name =~ $pattern AND n.tenant_id = $tid RETURN n"

        # AGE uses =~ for regex matching (case-insensitive)
        pattern = f"(?i).*{re.escape(query)}.*"
        results = await self.execute_cypher(
            cypher, params={"pattern": pattern, "tid": _resolve_tenant(tenant_id)}
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
        self, label: str | None = None, tenant_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List a tenant's entities, optionally filtered by label.

        Returns:
            List of vertex dicts.
        """
        match = f"MATCH (n:{_safe_label(label)})" if label else "MATCH (n)"
        cypher = f"{match} WHERE n.tenant_id = $tid RETURN n"

        results = await self.execute_cypher(cypher, params={"tid": _resolve_tenant(tenant_id)})

        entities: list[dict[str, Any]] = []
        for row in results:
            v = row.get("v")
            if v and isinstance(v, dict):
                entities.append(v)

        return entities

    # ── Knowledge Graph: Preference/Evidence Nodes ─────────────

    async def create_preference_node(
        self,
        tenant_id: str,
        preference_id: str,
        topic: str,
        choice: str,
        confidence: float,
    ) -> None:
        """Create or update a Preference node in the knowledge graph.

        Best-effort: failures are logged but never crash the main flow.
        """
        try:
            # Check if node already exists
            existing = await self.execute_cypher(
                "MATCH (p:Preference) WHERE p.id = $pid AND p.tenant_id = $tid RETURN p",
                params={"pid": preference_id, "tid": tenant_id},
            )
            if existing:
                # Update existing node
                await self.execute_cypher(
                    "MATCH (p:Preference) WHERE p.id = $pid AND p.tenant_id = $tid "
                    "SET p.topic = $topic, p.choice = $choice, p.confidence = $conf "
                    "RETURN p",
                    params={
                        "pid": preference_id,
                        "tid": tenant_id,
                        "topic": topic,
                        "choice": choice,
                        "conf": confidence,
                    },
                )
            else:
                await self.create_vertex(
                    "Preference",
                    {
                        "id": preference_id,
                        "tenant_id": tenant_id,
                        "name": topic,
                        "topic": topic,
                        "choice": choice,
                        "confidence": confidence,
                    },
                    tenant_id=tenant_id,
                )
            logger.debug("Graph: preference node %s upserted", preference_id)
        except Exception:
            logger.warning(
                "Graph: failed to create preference node %s (best-effort)",
                preference_id,
                exc_info=True,
            )

    async def create_evidence_node(
        self,
        tenant_id: str,
        evidence_id: str,
        preference_id: str,
        stance: str,
        strength: float,
    ) -> None:
        """Create an Evidence node and link to its parent Preference.

        Best-effort: failures are logged but never crash the main flow.
        """
        try:
            # Create evidence vertex
            await self.create_vertex(
                "Evidence",
                {
                    "id": evidence_id,
                    "tenant_id": tenant_id,
                    "name": f"evidence-{evidence_id[:8]}",
                    "stance": stance,
                    "strength": strength,
                },
                tenant_id=tenant_id,
            )
            # Link to parent preference
            edge_label = stance.upper()
            await self.execute_cypher(
                f"MATCH (e:Evidence), (p:Preference) "
                f"WHERE e.id = $eid AND e.tenant_id = $tid "
                f"AND p.id = $pid AND p.tenant_id = $tid "
                f"CREATE (e)-[r:{edge_label}]->(p) RETURN r",
                params={
                    "eid": evidence_id,
                    "tid": tenant_id,
                    "pid": preference_id,
                },
            )
            logger.debug(
                "Graph: evidence node %s linked to preference %s",
                evidence_id,
                preference_id,
            )
        except Exception:
            logger.warning(
                "Graph: failed to create evidence node %s (best-effort)",
                evidence_id,
                exc_info=True,
            )

    async def create_preference_relationship(
        self,
        tenant_id: str,
        from_id: str,
        to_id: str,
        rel_type: str,
    ) -> None:
        """Create a relationship between two Preference nodes.

        Supported rel_types: DEPENDS_ON, RELATED_TO, CONTRADICTS.
        Best-effort: failures are logged but never crash the main flow.
        """
        try:
            await self.execute_cypher(
                f"MATCH (a:Preference), (b:Preference) "
                f"WHERE a.id = $fid AND a.tenant_id = $tid "
                f"AND b.id = $toid AND b.tenant_id = $tid "
                f"CREATE (a)-[r:{rel_type}]->(b) RETURN r",
                params={
                    "fid": from_id,
                    "tid": tenant_id,
                    "toid": to_id,
                },
            )
            logger.debug(
                "Graph: preference relationship %s -> %s (%s)",
                from_id,
                to_id,
                rel_type,
            )
        except Exception:
            logger.warning(
                "Graph: failed to create preference relationship %s -> %s (best-effort)",
                from_id,
                to_id,
                exc_info=True,
            )

    async def get_preference_graph(
        self,
        tenant_id: str,
        preference_id: str,
    ) -> dict[str, Any]:
        """Get a preference and all connected nodes (evidence, related preferences).

        Returns a dict with the preference data and a list of connections.
        Best-effort: returns empty result on failure.
        """
        try:
            # Get the preference node
            pref_results = await self.execute_cypher(
                "MATCH (p:Preference) WHERE p.id = $pid AND p.tenant_id = $tid RETURN p",
                params={"pid": preference_id, "tid": tenant_id},
            )
            if not pref_results:
                return {"preference": None, "connections": []}

            # Get all connected nodes
            conn_results = await self.execute_cypher(
                "MATCH (p:Preference)-[r]-(n) WHERE p.id = $pid AND p.tenant_id = $tid RETURN n",
                params={"pid": preference_id, "tid": tenant_id},
            )

            connections = []
            for row in conn_results:
                v = row.get("v")
                if v and isinstance(v, dict):
                    connections.append(v)

            return {
                "preference": pref_results[0].get("v"),
                "connections": connections,
            }
        except Exception:
            logger.warning(
                "Graph: failed to get preference graph for %s (best-effort)",
                preference_id,
                exc_info=True,
            )
            return {"preference": None, "connections": []}
