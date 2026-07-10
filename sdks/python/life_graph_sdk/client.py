"""Synchronous Life Graph SDK client.

Provides a fully-typed, envelope-aware client for the Life Graph v1 SaaS API.
All ``/api/v1/`` endpoints automatically unwrap the ``{"data": ..., "meta": ...}``
response envelope.  Rate-limit headers are tracked on every response.

Usage::

    brain = LifeGraph("https://api.example.com", api_key="sk-...", tenant_id="t-123")
    brain.remember("I prefer Python over Java")
    results = brain.search("programming language preference")

Can also be used as a context manager::

    with LifeGraph("https://api.example.com", api_key="sk-...", tenant_id="t-123") as brain:
        brain.remember("Context-managed memory")
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, BinaryIO

import httpx

from .errors import raise_for_status
from .types import (
    AskResult,
    GraphEntity,
    IngestResult,
    Intention,
    JobRun,
    KnowledgeGap,
    Memory,
    MemoryLink,
    RateLimitInfo,
    RecallContext,
    SearchResult,
    Session,
    StaleBelief,
    Stats,
    TimelineChapter,
)


class LifeGraph:
    """Synchronous client for the Life Graph v1 API.

    Every request attaches ``X-API-Key`` and ``X-Tenant-ID`` headers.
    Responses that use the standard ``{"data": ..., "meta": ...}`` envelope
    are unwrapped automatically so callers receive only the inner payload.

    Usage::

        brain = LifeGraph("https://api.example.com", api_key="sk-...", tenant_id="t-123")
        brain.remember("I prefer Python over Java")
        results = brain.search("programming language preference")

    Can also be used as a context manager::

        with LifeGraph(...) as brain:
            brain.remember("Context-managed memory")
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: str | None = None,
        tenant_id: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialise the client.

        Args:
            api_url: Base URL of the Life Graph API (e.g. ``"https://api.example.com"``).
            api_key: API key sent via the ``X-API-Key`` header.
            tenant_id: Tenant identifier sent via the ``X-Tenant-ID`` header.
            timeout: Request timeout in seconds.
        """
        self.base_url = api_url.rstrip("/")
        headers: dict[str, str] = {}
        if api_key:
            headers["X-API-Key"] = api_key
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id
        self._client = httpx.Client(
            base_url=self.base_url, timeout=timeout, headers=headers,
            follow_redirects=True,
        )
        self._rate_limit = RateLimitInfo()

    # -- Context manager --------------------------------------------------

    def __enter__(self) -> LifeGraph:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    # -- Internal helpers -------------------------------------------------

    @property
    def rate_limit_info(self) -> RateLimitInfo:
        """Return the rate-limit information parsed from the last API response.

        Returns:
            A :class:`RateLimitInfo` with ``limit``, ``remaining``, and
            ``reset_at`` fields populated from the most recent response
            headers.
        """
        return self._rate_limit

    def _track_rate_limit(self, response: httpx.Response) -> None:
        """Parse ``X-RateLimit-*`` headers and update internal state.

        Args:
            response: The ``httpx.Response`` to extract headers from.
        """
        self._rate_limit = RateLimitInfo(
            limit=int(response.headers.get("X-RateLimit-Limit", 0)),
            remaining=int(response.headers.get("X-RateLimit-Remaining", 0)),
            reset_at=int(response.headers.get("X-RateLimit-Reset", 0)),
        )

    @staticmethod
    def _api(path: str) -> str:
        """Prepend the ``/api/v1`` prefix to a resource path.

        Args:
            path: The resource path (e.g. ``"/memories"``).

        Returns:
            The full API path (e.g. ``"/api/v1/memories"``).
        """
        return f"/api/v1{path}"

    def _unwrap(self, response: httpx.Response) -> Any:
        """Unwrap the standard ``{"data": ..., "meta": ...}`` response envelope.

        If the body does not follow the envelope schema the raw JSON is
        returned as-is so that health / metrics endpoints work without
        special-casing.

        Args:
            response: A successful ``httpx.Response``.

        Returns:
            The ``data`` portion of the envelope, or the raw JSON body.
        """
        body = response.json()
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Execute an HTTP request, raise on errors, unwrap the envelope.

        Args:
            method: HTTP method (``"GET"``, ``"POST"``, etc.).
            path: The full URL path (already prefixed if needed).
            **kwargs: Additional keyword arguments forwarded to ``httpx.Client.request``.

        Returns:
            The unwrapped response data.

        Raises:
            LifeGraphError: On any non-success HTTP status.
        """
        response = self._client.request(method, path, **kwargs)
        self._track_rate_limit(response)
        raise_for_status(response)
        if response.status_code == 204:
            return None
        return self._unwrap(response)

    def _get(self, path: str, **kwargs: Any) -> Any:
        """Send a GET request.

        Args:
            path: URL path.
            **kwargs: Forwarded to :meth:`_request`.

        Returns:
            Unwrapped response data.
        """
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs: Any) -> Any:
        """Send a POST request.

        Args:
            path: URL path.
            **kwargs: Forwarded to :meth:`_request`.

        Returns:
            Unwrapped response data.
        """
        return self._request("POST", path, **kwargs)

    def _patch(self, path: str, **kwargs: Any) -> Any:
        """Send a PATCH request.

        Args:
            path: URL path.
            **kwargs: Forwarded to :meth:`_request`.

        Returns:
            Unwrapped response data.
        """
        return self._request("PATCH", path, **kwargs)

    def _delete(self, path: str, **kwargs: Any) -> Any:
        """Send a DELETE request.

        Args:
            path: URL path.
            **kwargs: Forwarded to :meth:`_request`.

        Returns:
            Unwrapped response data.
        """
        return self._request("DELETE", path, **kwargs)

    @staticmethod
    def _open_file(file_path: str | Path | BinaryIO) -> tuple[str, BinaryIO, str]:
        """Return ``(filename, file_obj, content_type)`` for upload.

        Args:
            file_path: A filesystem path or an already-open file-like object.

        Returns:
            A three-tuple suitable for the ``files`` parameter of httpx.
        """
        if isinstance(file_path, (str, Path)):
            p = Path(file_path)
            ct = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
            return p.name, open(p, "rb"), ct  # noqa: SIM115
        name = getattr(file_path, "name", "upload")
        return name, file_path, "application/octet-stream"

    # =====================================================================
    # Health (root paths — no /api/v1 prefix)
    # =====================================================================

    def health(self) -> dict:
        """Return the raw health-check payload from the API.

        Returns:
            A dict with health status information.
        """
        return self._get("/health")

    def ping(self) -> bool:
        """Check whether the API is reachable and healthy.

        Returns:
            ``True`` if the API responds with a success status.
        """
        try:
            self._get("/health")
            return True
        except Exception:
            return False

    def ready(self) -> dict:
        """Return the readiness-probe payload.

        Returns:
            A dict indicating whether the service is ready to accept traffic.
        """
        return self._get("/ready")

    def live(self) -> dict:
        """Return the liveness-probe payload.

        Returns:
            A dict indicating whether the service process is alive.
        """
        return self._get("/live")

    # =====================================================================
    # Memories
    # =====================================================================

    def memories(
        self,
        status: str | None = None,
        tags: list[str] | None = None,
        min_importance: float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Memory]:
        """List stored memories with optional filters.

        Args:
            status: Filter by memory status (e.g. ``"active"``).
            tags: Filter by one or more tags.
            min_importance: Minimum importance threshold.
            limit: Maximum number of memories to return.
            offset: Pagination offset.

        Returns:
            A list of :class:`Memory` objects.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        if tags is not None:
            params["tags"] = ",".join(tags)
        if min_importance is not None:
            params["min_importance"] = min_importance
        data = self._get(self._api("/memories"), params=params)
        return [Memory.from_dict(m) for m in data]

    def memory(self, id: str) -> Memory:
        """Retrieve a single memory by ID.

        Args:
            id: The memory identifier.

        Returns:
            The requested :class:`Memory`.

        Raises:
            NotFoundError: If no memory with the given ID exists.
        """
        data = self._get(self._api(f"/memories/{id}"))
        return Memory.from_dict(data)

    def create_memory(
        self,
        content: str,
        source: str | None = None,
        tags: list[str] | None = None,
        importance: float | None = None,
    ) -> list[Memory]:
        """Create one or more memories from raw content.

        Args:
            content: The textual content to store.
            source: Optional source label (e.g. ``"user"``, ``"agent"``).
            tags: Optional tags to attach.
            importance: Optional importance score override.

        Returns:
            A list of :class:`Memory` objects that were created.
        """
        body: dict[str, Any] = {"content": content}
        if source is not None:
            body["source"] = source
        if tags is not None:
            body["tags"] = tags
        if importance is not None:
            body["importance"] = importance
        data = self._post(self._api("/memories"), json=body)
        return [Memory.from_dict(m) for m in data]

    def update_memory(self, id: str, **fields: Any) -> Memory:
        """Update fields on an existing memory.

        Args:
            id: The memory identifier.
            **fields: Key-value pairs of fields to update (e.g.
                ``content="new text"``, ``tags=["a", "b"]``).

        Returns:
            The updated :class:`Memory`.

        Raises:
            NotFoundError: If no memory with the given ID exists.
        """
        data = self._patch(self._api(f"/memories/{id}"), json=fields)
        return Memory.from_dict(data)

    def delete_memory(self, id: str) -> None:
        """Delete a memory by ID.

        Args:
            id: The memory identifier.

        Raises:
            NotFoundError: If no memory with the given ID exists.
        """
        self._delete(self._api(f"/memories/{id}"))

    # =====================================================================
    # Memory Links
    # =====================================================================

    def create_memory_link(
        self,
        source_id: str,
        target_id: str,
        link_type: str,
        strength: float = 0.5,
    ) -> MemoryLink:
        """Create a typed link between two memories.

        Args:
            source_id: Source memory ID.
            target_id: Target memory ID.
            link_type: Relationship type (BECAUSE, EVIDENCED_BY,
                RELATED_TO, CONTRADICTS, SUPERSEDES, LEADS_TO).
            strength: Link strength (0.0–1.0).

        Returns:
            The created :class:`MemoryLink`.
        """
        body = {
            "source_memory_id": source_id,
            "target_memory_id": target_id,
            "link_type": link_type,
            "strength": strength,
        }
        data = self._post(self._api(f"/memories/{source_id}/links"), json=body)
        return MemoryLink.from_dict(data)

    def memory_links(self, memory_id: str) -> list[MemoryLink]:
        """List all links for a memory.

        Args:
            memory_id: The memory identifier.

        Returns:
            A list of :class:`MemoryLink` objects.
        """
        data = self._get(self._api(f"/memories/{memory_id}/links"))
        return [MemoryLink.from_dict(link) for link in data]

    def linked_memories(self, memory_id: str, depth: int = 2) -> list[dict]:
        """Get memories linked to this one via graph traversal.

        Args:
            memory_id: The memory identifier.
            depth: Traversal depth (1–5).

        Returns:
            A list of dicts with linked memory data, link types, and depth.
        """
        return self._get(
            self._api(f"/memories/{memory_id}/linked"),
            params={"depth": depth},
        )

    # =====================================================================
    # Search
    # =====================================================================

    def search(
        self,
        query: str,
        limit: int = 10,
        tags: list[str] | None = None,
        min_importance: float | None = None,
    ) -> list[Memory]:
        """Semantic search across all memories.

        Args:
            query: Natural-language search query.
            limit: Maximum number of results to return.
            tags: Optional tag filter.
            min_importance: Minimum importance threshold.

        Returns:
            A list of :class:`Memory` objects ranked by relevance.
        """
        body: dict[str, Any] = {"query": query, "limit": limit}
        if tags is not None:
            body["tags"] = tags
        if min_importance is not None:
            body["min_importance"] = min_importance
        data = self._post(self._api("/search"), json=body)
        # API returns {"memories": [...], ...} — extract the list
        if isinstance(data, dict) and "memories" in data:
            data = data["memories"]
        return [Memory.from_dict(m) for m in data]

    def ask(self, question: str, limit: int = 10) -> AskResult:
        """Ask a natural-language question and get an AI-generated answer.

        Args:
            question: The question to ask.
            limit: Maximum number of source memories to consider.

        Returns:
            An :class:`AskResult` containing the answer and source memories.
        """
        data = self._post(self._api("/search/ask"), json={"question": question, "limit": limit})
        return AskResult.from_dict(data)

    def recall(self, context: dict) -> RecallContext:
        """Recall memories, decisions, and intentions relevant to a context.

        Args:
            context: A dict describing the current situation or task.

        Returns:
            A :class:`RecallContext` bundle with relevant information.
        """
        data = self._post(self._api("/recall"), json={"context": context})
        return RecallContext.from_dict(data)

    def recall_event(self, context: dict, event: str) -> list[Memory]:
        """Recall memories relevant to a specific event within a context.

        Args:
            context: A dict describing the current situation.
            event: The event identifier or description.

        Returns:
            A list of :class:`Memory` objects related to the event.
        """
        data = self._post(
            self._api("/recall/event"),
            json={"context": context, "event": event},
        )
        return [Memory.from_dict(m) for m in data]

    # =====================================================================
    # Sessions
    # =====================================================================

    def start_session(self, context: dict | None = None) -> Session:
        """Start a new interaction session.

        Args:
            context: Optional initial context for the session.

        Returns:
            The newly created :class:`Session`.
        """
        body: dict[str, Any] = {}
        if context is not None:
            body["context"] = context
        data = self._post(self._api("/sessions/start"), json=body)
        return Session.from_dict(data)

    def end_session(self, session_id: str, outcome: str | None = None) -> Session:
        """End an active session.

        Args:
            session_id: The session identifier.
            outcome: Optional session outcome (``"success"``, ``"failure"``,
                or ``"neutral"``). Used for impact scoring.

        Returns:
            The finalized :class:`Session` with summary and impact scoring.
        """
        body: dict[str, Any] = {}
        if outcome is not None:
            body["outcome"] = outcome
        data = self._post(self._api(f"/sessions/{session_id}/end"), json=body or None)
        return Session.from_dict(data)

    def micro_consolidate(self, session_id: str) -> dict:
        """Manually trigger micro-consolidation for a session.

        Runs a lightweight 4-step pipeline (dedup, re-score, graph)
        on the session's memories. No LLM calls.

        Args:
            session_id: The session identifier.

        Returns:
            A dict with consolidation report (memories_processed,
            duplicates_removed, entities_discovered, etc.).
        """
        return self._post(self._api(f"/admin/micro-consolidate/{session_id}"))

    def session(self, session_id: str) -> Session:
        """Retrieve a session by ID.

        Args:
            session_id: The session identifier.

        Returns:
            The requested :class:`Session`.

        Raises:
            NotFoundError: If no session with the given ID exists.
        """
        data = self._get(self._api(f"/sessions/{session_id}"))
        return Session.from_dict(data)

    def sessions(self, limit: int = 10) -> list[Session]:
        """List recent sessions.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            A list of :class:`Session` objects.
        """
        data = self._get(self._api("/sessions"), params={"limit": limit})
        return [Session.from_dict(s) for s in data]

    def heartbeat(self, session_id: str, context: dict) -> Session:
        """Send a heartbeat to keep a session alive and update its context.

        Args:
            session_id: The session identifier.
            context: Updated context information.

        Returns:
            The updated :class:`Session`.
        """
        data = self._post(
            self._api(f"/sessions/{session_id}/heartbeat"),
            json={"context": context},
        )
        return Session.from_dict(data)

    # =====================================================================
    # Intentions
    # =====================================================================

    def create_intention(
        self,
        content: str,
        trigger_type: str = "event",
        trigger_condition: str | None = None,
        priority: str = "normal",
    ) -> Intention:
        """Create a new proactive intention.

        Args:
            content: Human-readable description of the intention.
            trigger_type: Type of trigger (``"event"``, ``"time"``, etc.).
            trigger_condition: Condition that will activate the intention.
            priority: Priority level (``"low"``, ``"normal"``, ``"high"``).

        Returns:
            The newly created :class:`Intention`.
        """
        body: dict[str, Any] = {
            "content": content,
            "trigger_type": trigger_type,
            "priority": priority,
        }
        if trigger_condition is not None:
            body["trigger_condition"] = trigger_condition
        data = self._post(self._api("/intentions"), json=body)
        return Intention.from_dict(data)

    def intentions(self) -> list[Intention]:
        """List all active intentions.

        Returns:
            A list of :class:`Intention` objects.
        """
        data = self._get(self._api("/intentions"))
        return [Intention.from_dict(i) for i in data]

    def triggered_intentions(self, context: dict) -> list[Intention]:
        """Evaluate which intentions are triggered by the given context.

        Args:
            context: A dict describing the current situation.

        Returns:
            A list of :class:`Intention` objects that have been triggered.
        """
        data = self._post(self._api("/intentions/triggered"), json={"context": context})
        return [Intention.from_dict(i) for i in data]

    def complete_intention(self, id: str) -> Intention:
        """Mark an intention as completed.

        Args:
            id: The intention identifier.

        Returns:
            The updated :class:`Intention`.

        Raises:
            NotFoundError: If no intention with the given ID exists.
        """
        data = self._post(self._api(f"/intentions/{id}/complete"))
        return Intention.from_dict(data)

    def dismiss_intention(self, id: str) -> Intention:
        """Dismiss an intention without completing it.

        Args:
            id: The intention identifier.

        Returns:
            The updated :class:`Intention`.

        Raises:
            NotFoundError: If no intention with the given ID exists.
        """
        data = self._post(self._api(f"/intentions/{id}/dismiss"))
        return Intention.from_dict(data)

    # =====================================================================
    # Identity
    # =====================================================================

    def timeline(self, domain: str | None = None) -> list[TimelineChapter]:
        """Retrieve the identity timeline, optionally filtered by domain.

        Args:
            domain: Optional domain filter (e.g. ``"career"``, ``"health"``).

        Returns:
            A list of :class:`TimelineChapter` objects.
        """
        params: dict[str, Any] = {}
        if domain is not None:
            params["domain"] = domain
        data = self._get(self._api("/identity/timeline"), params=params)
        return [TimelineChapter.from_dict(c) for c in data]

    def beliefs(self, domain: str | None = None) -> list[Memory]:
        """List current beliefs, optionally filtered by domain.

        Args:
            domain: Optional domain filter.

        Returns:
            A list of :class:`Memory` objects representing beliefs.
        """
        params: dict[str, Any] = {}
        if domain is not None:
            params["domain"] = domain
        data = self._get(self._api("/identity/beliefs"), params=params)
        return [Memory.from_dict(m) for m in data]

    def stale_beliefs(self, days: int = 90) -> list[StaleBelief]:
        """Identify beliefs that have not been confirmed recently.

        Args:
            days: Number of days after which a belief is considered stale.

        Returns:
            A list of :class:`StaleBelief` objects.
        """
        data = self._get(self._api("/identity/beliefs/stale"), params={"days": days})
        return [StaleBelief.from_dict(b) for b in data]

    def challenge_belief(self, memory_id: str) -> dict:
        """Challenge a specific belief and receive a reassessment.

        Args:
            memory_id: The memory ID of the belief to challenge.

        Returns:
            A dict with the challenge result and suggested actions.
        """
        return self._post(self._api(f"/identity/beliefs/{memory_id}/challenge"))

    # =====================================================================
    # Agent
    # =====================================================================

    def build_context(self, task: str, project: str | None = None) -> dict:
        """Build an agent context bundle for a given task.

        Args:
            task: Description of the task the agent is about to perform.
            project: Optional project name to scope context retrieval.

        Returns:
            A dict containing memories, intentions, and other context.
        """
        body: dict[str, Any] = {"task": task}
        if project is not None:
            body["project"] = project
        return self._post(self._api("/agent/context"), json=body)

    def learn(self, conversation: str, context: dict | None = None) -> list[Memory]:
        """Extract and store memories from a conversation transcript.

        Args:
            conversation: The conversation text to learn from.
            context: Optional context to guide memory extraction.

        Returns:
            A list of :class:`Memory` objects created from the conversation.
        """
        body: dict[str, Any] = {"conversation": conversation}
        if context is not None:
            body["context"] = context
        data = self._post(self._api("/agent/learn"), json=body)
        return [Memory.from_dict(m) for m in data]

    # =====================================================================
    # Admin
    # =====================================================================

    def stats(self) -> Stats:
        """Retrieve system statistics.

        Returns:
            A :class:`Stats` object with counts of memories, intentions, etc.
        """
        data = self._get(self._api("/admin/stats"))
        return Stats.from_dict(data)

    def gaps(self) -> list[KnowledgeGap]:
        """List detected knowledge gaps.

        Returns:
            A list of :class:`KnowledgeGap` objects.
        """
        data = self._get(self._api("/admin/gaps"))
        return [KnowledgeGap.from_dict(g) for g in data]

    def ingest(
        self,
        text: str,
        context: dict | None = None,
        source: str | None = None,
    ) -> list[Memory]:
        """Ingest free-form text and create memories from it.

        Args:
            text: The text to ingest.
            context: Optional context to guide memory extraction.
            source: Optional source label.

        Returns:
            A list of :class:`Memory` objects that were created.
        """
        body: dict[str, Any] = {"text": text}
        if context is not None:
            body["context"] = context
        if source is not None:
            body["source"] = source
        data = self._post(self._api("/admin/ingest"), json=body)
        return [Memory.from_dict(m) for m in data]

    def export_memories(self) -> dict:
        """Export all memories as a JSON-serialisable dict.

        Returns:
            A dict containing the full memory export.
        """
        return self._get(self._api("/admin/export"))

    def consolidate(self) -> dict:
        """Trigger an immediate memory consolidation pass.

        Returns:
            A dict with consolidation results and statistics.
        """
        return self._post(self._api("/admin/consolidate"))

    def jobs(self, limit: int = 20) -> list[JobRun]:
        """List recent background job runs.

        Args:
            limit: Maximum number of job runs to return.

        Returns:
            A list of :class:`JobRun` objects.
        """
        data = self._get(self._api("/admin/jobs"), params={"limit": limit})
        return [JobRun.from_dict(j) for j in data]

    def enqueue_consolidation(self, tenant_id: str | None = None) -> dict:
        """Enqueue a consolidation job for background processing.

        Args:
            tenant_id: Optional tenant ID override. Defaults to the
                client's configured tenant.

        Returns:
            A dict with the queued job information.
        """
        body: dict[str, Any] = {}
        if tenant_id is not None:
            body["tenant_id"] = tenant_id
        return self._post(self._api("/admin/consolidate/enqueue"), json=body)

    # =====================================================================
    # Graph
    # =====================================================================

    def entities(self, label: str | None = None) -> list[GraphEntity]:
        """List entities in the knowledge graph.

        Args:
            label: Optional label to filter entities by (e.g. ``"Person"``).

        Returns:
            A list of :class:`GraphEntity` objects.
        """
        params: dict[str, Any] = {}
        if label is not None:
            params["label"] = label
        data = self._get(self._api("/graph/entities"), params=params)
        return [GraphEntity.from_dict(e) for e in data]

    def entity(self, name: str) -> dict:
        """Get full details for a single graph entity.

        Args:
            name: The entity name.

        Returns:
            A dict containing the entity and its relationships.

        Raises:
            NotFoundError: If the entity does not exist.
        """
        return self._get(self._api(f"/graph/entity/{name}"))

    def graph_query(
        self,
        cypher: str,
        params: dict | None = None,
        columns: list[str] | None = None,
    ) -> list[dict]:
        """Execute a raw Cypher query against the knowledge graph.

        Args:
            cypher: A Cypher query string.
            params: Optional parameter dict to bind into the query.
            columns: Optional list of column names to extract.

        Returns:
            A list of result dicts.
        """
        body: dict[str, Any] = {"query": cypher}
        if params is not None:
            body["params"] = params
        if columns is not None:
            body["columns"] = columns
        return self._post(self._api("/graph/query"), json=body)

    def graph_path(
        self,
        from_name: str,
        to_name: str,
        max_depth: int = 5,
    ) -> dict:
        """Find the shortest path between two entities.

        Args:
            from_name: Starting entity name.
            to_name: Ending entity name.
            max_depth: Maximum traversal depth.

        Returns:
            A dict describing the path (nodes and relationships).
        """
        return self._get(
            self._api("/graph/path"),
            params={"from_name": from_name, "to_name": to_name, "max_depth": max_depth},
        )

    def graph_search(
        self,
        query: str,
        label: str | None = None,
        limit: int = 10,
        min_importance: float | None = None,
    ) -> dict:
        """Hybrid search combining vector similarity with graph context.

        Args:
            query: Natural-language search query.
            label: Optional entity label filter.
            limit: Maximum number of results to return.
            min_importance: Minimum importance threshold.

        Returns:
            A dict containing search results with graph context.
        """
        body: dict[str, Any] = {"query": query, "limit": limit}
        if label is not None:
            body["label"] = label
        if min_importance is not None:
            body["min_importance"] = min_importance
        return self._post(self._api("/graph/search"), json=body)

    # =====================================================================
    # Multimodal
    # =====================================================================

    def ingest_voice(self, file_path: str | Path | BinaryIO) -> IngestResult:
        """Ingest an audio file (voice memo, recording, etc.).

        Args:
            file_path: Path to the audio file, or an open file-like object.

        Returns:
            An :class:`IngestResult` with transcription details.
        """
        name, fobj, ct = self._open_file(file_path)
        try:
            data = self._post(
                self._api("/ingest/voice"), files={"file": (name, fobj, ct)},
            )
        finally:
            if isinstance(file_path, (str, Path)):
                fobj.close()
        return IngestResult.from_dict(data)

    def ingest_image(self, file_path: str | Path | BinaryIO) -> IngestResult:
        """Ingest an image file for OCR and analysis.

        Args:
            file_path: Path to the image file, or an open file-like object.

        Returns:
            An :class:`IngestResult` with OCR details.
        """
        name, fobj, ct = self._open_file(file_path)
        try:
            data = self._post(
                self._api("/ingest/image"), files={"file": (name, fobj, ct)},
            )
        finally:
            if isinstance(file_path, (str, Path)):
                fobj.close()
        return IngestResult.from_dict(data)

    def ingest_document(self, file_path: str | Path | BinaryIO) -> IngestResult:
        """Ingest a document file (PDF, DOCX, etc.).

        Args:
            file_path: Path to the document file, or an open file-like object.

        Returns:
            An :class:`IngestResult` with extraction details.
        """
        name, fobj, ct = self._open_file(file_path)
        try:
            data = self._post(
                self._api("/ingest/document"), files={"file": (name, fobj, ct)},
            )
        finally:
            if isinstance(file_path, (str, Path)):
                fobj.close()
        return IngestResult.from_dict(data)

    # =====================================================================
    # Procedures (Strategy Memory)
    # =====================================================================

    def create_procedure(
        self,
        trigger: str,
        steps: list[str],
        description: str | None = None,
        confidence: float = 0.5,
        tags: list[str] | None = None,
        learned_from: list[str] | None = None,
    ) -> dict:
        """Create a new procedural memory (learned strategy).

        Args:
            trigger: When this procedure should activate.
            steps: Ordered list of steps.
            description: Human-readable summary.
            confidence: Confidence score (0.0-1.0).
            tags: Optional tags.
            learned_from: Session IDs that led to this pattern.

        Returns:
            The created procedure as a dict.
        """
        body: dict[str, Any] = {
            "trigger": trigger,
            "steps": steps,
        }
        if description is not None:
            body["description"] = description
        if confidence != 0.5:
            body["confidence"] = confidence
        if tags:
            body["tags"] = tags
        if learned_from:
            body["learned_from"] = learned_from
        return self._post(self._api("/procedures/"), json=body)

    def procedures(self, limit: int = 20) -> list[dict]:
        """List all procedures.

        Args:
            limit: Maximum number of procedures to return.

        Returns:
            A list of procedure dicts.
        """
        return self._get(self._api("/procedures/"), params={"limit": limit})

    def procedure(self, procedure_id: str) -> dict:
        """Get a procedure by ID.

        Args:
            procedure_id: The procedure identifier.

        Returns:
            The procedure as a dict.
        """
        return self._get(self._api(f"/procedures/{procedure_id}"))

    def apply_procedure(self, procedure_id: str, success: bool = True) -> dict:
        """Record that a procedure was applied.

        Args:
            procedure_id: The procedure identifier.
            success: Whether the application succeeded.

        Returns:
            The updated procedure as a dict.
        """
        return self._post(
            self._api(f"/procedures/{procedure_id}/apply"),
            params={"success": str(success).lower()},
        )

    def match_procedures(self, query: str, limit: int = 5) -> list[dict]:
        """Find procedures matching a trigger query.

        Args:
            query: Search query to match against triggers.
            limit: Maximum results.

        Returns:
            A list of matching procedure dicts.
        """
        return self._get(self._api(f"/procedures/match/{query}"), params={"limit": limit})

    def delete_procedure(self, procedure_id: str) -> dict:
        """Archive a procedure.

        Args:
            procedure_id: The procedure identifier.

        Returns:
            Confirmation dict.
        """
        return self._delete(self._api(f"/procedures/{procedure_id}"))

    # =====================================================================
    # Convenience
    # =====================================================================

    def remember(self, text: str) -> list[Memory]:
        """Ingest free-form text and create memories from it.

        This is a convenience alias for :meth:`ingest` with no extra options.

        Args:
            text: The text to remember.

        Returns:
            A list of :class:`Memory` objects that were created.
        """
        return self.ingest(text)
