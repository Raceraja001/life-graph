"""Preference ↔ Knowledge Graph integration service.

Bridges the preference/evidence stores with the Apache AGE knowledge
graph.  When preferences or evidence are created the service
automatically syncs corresponding graph nodes and edges so that the
knowledge graph stays in lock-step with relational data.

All graph operations are **best-effort** — failures are logged but
never propagate to callers.  This keeps the critical CRUD path safe
even when AGE is unavailable.

Usage::

    from life_graph.services.preference_graph import PreferenceGraphService

    svc = PreferenceGraphService()
    svc.subscribe()                   # wire EventBus listeners
    await svc.sync_preference(...)    # explicit one-shot sync
    subgraph = await svc.get_preference_subgraph(tenant_id, pref_id)
"""

from __future__ import annotations

import logging
from typing import Any

from life_graph.core.events import Event, EventType, event_bus

logger = logging.getLogger(__name__)


# ── Lazy GraphStore accessor ─────────────────────────────────

_graph_store = None


def _get_graph_store():
    """Lazy-initialise the GraphStore singleton.

    Mirrors the pattern used in ``life_graph.api.graph``.
    """
    global _graph_store
    if _graph_store is None:
        from life_graph.storage.graph import GraphStore

        _graph_store = GraphStore()
    return _graph_store


# ── Allowed inter-preference relationship types ──────────────

_ALLOWED_REL_TYPES = frozenset({"RELATED_TO", "DEPENDS_ON", "CONTRADICTS"})


class PreferenceGraphService:
    """Keeps the AGE knowledge graph synchronised with preference data.

    Provides three capabilities:

    1. **Auto-sync via EventBus** — call :meth:`subscribe` once at
       startup and the service will listen for
       ``PREFERENCE_CREATED``, ``PREFERENCE_UPDATED``, and
       ``EVIDENCE_ADDED`` events, creating or updating graph nodes
       and edges automatically.

    2. **Explicit sync methods** — :meth:`sync_preference`,
       :meth:`sync_evidence`, and :meth:`link_preferences` can be
       called directly for imperative use-cases.

    3. **Subgraph query** — :meth:`get_preference_subgraph` returns
       a preference node together with all connected evidence and
       related preference nodes, ready for visualisation.

    All operations are tenant-scoped via ``tenant_id``.
    """

    def __init__(self) -> None:
        self._subscribed = False

    # ── EventBus Integration ──────────────────────────────────

    def subscribe(self) -> None:
        """Register EventBus handlers for automatic graph sync.

        Safe to call multiple times — subscriptions are idempotent.
        """
        if self._subscribed:
            return

        event_bus.subscribe(EventType.PREFERENCE_CREATED, self._on_preference_created)
        event_bus.subscribe(EventType.PREFERENCE_UPDATED, self._on_preference_updated)
        event_bus.subscribe(EventType.EVIDENCE_ADDED, self._on_evidence_added)

        self._subscribed = True
        logger.info("PreferenceGraphService subscribed to EventBus")

    def unsubscribe(self) -> None:
        """Remove EventBus handlers."""
        if not self._subscribed:
            return

        event_bus.unsubscribe(EventType.PREFERENCE_CREATED, self._on_preference_created)
        event_bus.unsubscribe(EventType.PREFERENCE_UPDATED, self._on_preference_updated)
        event_bus.unsubscribe(EventType.EVIDENCE_ADDED, self._on_evidence_added)

        self._subscribed = False
        logger.info("PreferenceGraphService unsubscribed from EventBus")

    # ── Event Handlers ────────────────────────────────────────

    async def _on_preference_created(self, event: Event) -> None:
        """Handle ``PREFERENCE_CREATED`` — create a Preference node."""
        payload = event.payload
        await self.sync_preference(
            tenant_id=payload["tenant_id"],
            preference_id=payload["id"],
            topic=payload.get("topic", "unknown"),
            choice=payload.get("choice", ""),
            confidence=payload.get("confidence", 0.5),
        )

    async def _on_preference_updated(self, event: Event) -> None:
        """Handle ``PREFERENCE_UPDATED`` — update the Preference node.

        Only topic/choice/confidence changes are reflected in the
        graph; the full relational record is the source of truth.
        """
        payload = event.payload
        # Updated events may not carry full data — sync with
        # whatever is available.  GraphStore.create_preference_node
        # does an upsert internally.
        await self.sync_preference(
            tenant_id=payload["tenant_id"],
            preference_id=payload["id"],
            topic=payload.get("topic"),
            choice=payload.get("choice"),
            confidence=payload.get("confidence"),
        )

    async def _on_evidence_added(self, event: Event) -> None:
        """Handle ``EVIDENCE_ADDED`` — create Evidence node + edge."""
        payload = event.payload
        await self.sync_evidence(
            tenant_id=payload["tenant_id"],
            evidence_id=payload["id"],
            preference_id=payload["preference_id"],
            stance=payload.get("stance", "supports"),
            strength=payload.get("weight", payload.get("credibility", 1.0)),
        )

    # ── Explicit Sync Methods ─────────────────────────────────

    async def sync_preference(
        self,
        tenant_id: str,
        preference_id: str,
        topic: str | None = None,
        choice: str | None = None,
        confidence: float | None = None,
    ) -> None:
        """Create or update a Preference node in the knowledge graph.

        Args:
            tenant_id: Tenant scope.
            preference_id: UUID string of the preference.
            topic: Preference topic (used as the node ``name``).
            choice: The selected choice.
            confidence: Current confidence score.
        """
        store = _get_graph_store()
        await store.create_preference_node(
            tenant_id=tenant_id,
            preference_id=preference_id,
            topic=topic or "unknown",
            choice=choice or "",
            confidence=confidence if confidence is not None else 0.5,
        )
        logger.debug(
            "Synced preference %s to graph for tenant %s",
            preference_id,
            tenant_id,
        )

    async def sync_evidence(
        self,
        tenant_id: str,
        evidence_id: str,
        preference_id: str,
        stance: str = "supports",
        strength: float = 1.0,
    ) -> None:
        """Create an Evidence node and link it to its parent Preference.

        The edge label matches the stance (``SUPPORTS`` or
        ``CONTRADICTS``).

        Args:
            tenant_id: Tenant scope.
            evidence_id: UUID string of the evidence item.
            preference_id: UUID string of the parent preference.
            stance: ``"supports"`` | ``"contradicts"`` | ``"neutral"``.
            strength: Credibility-weighted strength of the evidence.
        """
        store = _get_graph_store()
        await store.create_evidence_node(
            tenant_id=tenant_id,
            evidence_id=evidence_id,
            preference_id=preference_id,
            stance=stance,
            strength=strength,
        )
        logger.debug(
            "Synced evidence %s → preference %s to graph for tenant %s",
            evidence_id,
            preference_id,
            tenant_id,
        )

    async def link_preferences(
        self,
        tenant_id: str,
        from_preference_id: str,
        to_preference_id: str,
        rel_type: str = "RELATED_TO",
    ) -> None:
        """Create a relationship edge between two Preference nodes.

        Args:
            tenant_id: Tenant scope.
            from_preference_id: Source preference UUID string.
            to_preference_id: Target preference UUID string.
            rel_type: One of ``RELATED_TO``, ``DEPENDS_ON``, or
                ``CONTRADICTS``.

        Raises:
            ValueError: If *rel_type* is not in the allowed set.
        """
        if rel_type not in _ALLOWED_REL_TYPES:
            raise ValueError(
                f"Invalid rel_type {rel_type!r}; "
                f"must be one of {sorted(_ALLOWED_REL_TYPES)}"
            )

        store = _get_graph_store()
        await store.create_preference_relationship(
            tenant_id=tenant_id,
            from_id=from_preference_id,
            to_id=to_preference_id,
            rel_type=rel_type,
        )
        logger.info(
            "Linked preferences %s -[%s]-> %s for tenant %s",
            from_preference_id,
            rel_type,
            to_preference_id,
            tenant_id,
        )

    # ── Subgraph Query ────────────────────────────────────────

    async def get_preference_subgraph(
        self,
        tenant_id: str,
        preference_id: str,
    ) -> dict[str, Any]:
        """Return the preference subgraph for visualisation.

        The result includes:

        * ``preference`` — the Preference node data (or ``None``).
        * ``evidence`` — list of connected Evidence nodes.
        * ``related_preferences`` — list of related Preference nodes.
        * ``edges`` — list of edge dicts ``{from, to, label}``.

        Best-effort: returns an empty structure on failure.

        Args:
            tenant_id: Tenant scope.
            preference_id: UUID string of the root preference.

        Returns:
            Dict with keys ``preference``, ``evidence``,
            ``related_preferences``, and ``edges``.
        """
        empty: dict[str, Any] = {
            "preference": None,
            "evidence": [],
            "related_preferences": [],
            "edges": [],
        }

        store = _get_graph_store()

        try:
            # ── Fetch root preference node ────────────────────
            pref_rows = await store.execute_cypher(
                "MATCH (p:Preference) "
                "WHERE p.id = $pid AND p.tenant_id = $tid "
                "RETURN p",
                params={"pid": preference_id, "tid": tenant_id},
            )
            if not pref_rows:
                return empty

            preference_node = pref_rows[0].get("v")

            # ── Fetch connected evidence + edges ──────────────
            evidence_rows = await store.execute_cypher(
                "MATCH (e:Evidence)-[r]->(p:Preference) "
                "WHERE p.id = $pid AND p.tenant_id = $tid "
                "AND e.tenant_id = $tid "
                "RETURN e, r",
                params={"pid": preference_id, "tid": tenant_id},
                columns=["e", "r"],
            )

            evidence_nodes: list[dict[str, Any]] = []
            edges: list[dict[str, Any]] = []

            for row in evidence_rows:
                ev = row.get("e")
                rel = row.get("r")
                if ev and isinstance(ev, dict):
                    evidence_nodes.append(ev)
                if rel and isinstance(rel, dict):
                    edges.append({
                        "from": rel.get("start_id") or _prop(ev, "id"),
                        "to": preference_id,
                        "label": rel.get("label", "SUPPORTS"),
                    })

            # ── Fetch related preference nodes + edges ────────
            rel_pref_rows = await store.execute_cypher(
                "MATCH (p:Preference)-[r]-(q:Preference) "
                "WHERE p.id = $pid AND p.tenant_id = $tid "
                "AND q.tenant_id = $tid "
                "RETURN q, r",
                params={"pid": preference_id, "tid": tenant_id},
                columns=["q", "r"],
            )

            related_nodes: list[dict[str, Any]] = []
            for row in rel_pref_rows:
                qn = row.get("q")
                rel = row.get("r")
                if qn and isinstance(qn, dict):
                    related_nodes.append(qn)
                if rel and isinstance(rel, dict):
                    edges.append({
                        "from": preference_id,
                        "to": _prop(qn, "id"),
                        "label": rel.get("label", "RELATED_TO"),
                    })

            return {
                "preference": preference_node,
                "evidence": evidence_nodes,
                "related_preferences": related_nodes,
                "edges": edges,
            }

        except Exception:
            logger.warning(
                "Failed to build preference subgraph for %s (best-effort)",
                preference_id,
                exc_info=True,
            )
            return empty


# ── Helpers ──────────────────────────────────────────────────


def _prop(node: dict[str, Any] | None, key: str) -> Any:
    """Safely extract a property from an AGE vertex dict."""
    if not node:
        return None
    props = node.get("properties", node)
    return props.get(key)


# ── Module-level singleton ───────────────────────────────────

preference_graph_service = PreferenceGraphService()
"""Singleton instance — import and call ``subscribe()`` at startup."""
