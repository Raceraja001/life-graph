"""One-time graph migration job — populate AGE graph from existing memories.

Reads all active memories from PostgreSQL, extracts entities from
``properties.entities`` and ``tags``, creates graph vertices with
inferred labels, and links co-occurring entities with ``related_to``
edges.

Usage::

    job = GraphMigrationJob(session_factory)
    report = await job.run()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.models.db import Memory

logger = logging.getLogger(__name__)


# ── Label Inference ───────────────────────────────────────────────────────────

# Keywords that hint at a specific vertex label
_TECHNOLOGY_KEYWORDS = {
    "python", "javascript", "typescript", "rust", "go", "java", "kotlin",
    "swift", "ruby", "php", "c++", "c#", "react", "vue", "angular",
    "django", "flask", "fastapi", "express", "nextjs", "nuxt",
    "postgresql", "postgres", "mysql", "mongodb", "redis", "sqlite",
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure",
    "git", "github", "gitlab", "linux", "windows", "macos",
    "vscode", "vim", "neovim", "emacs", "jetbrains", "pycharm",
    "node", "npm", "yarn", "pip", "poetry", "hatch",
    "tensorflow", "pytorch", "pandas", "numpy", "scipy",
    "html", "css", "sass", "tailwind", "bootstrap",
    "graphql", "rest", "grpc", "websocket",
    "nginx", "apache", "caddy", "traefik",
    "sqlalchemy", "alembic", "pgvector", "asyncpg",
    "spacy", "transformers", "litellm", "openai", "anthropic",
    "minio", "s3", "elasticsearch", "kibana",
}

_DECISION_KEYWORDS = {
    "decided", "chose", "picked", "selected", "went with",
    "switched to", "migrated to", "adopted", "prefer",
}

_CONCEPT_KEYWORDS = {
    "pattern", "principle", "practice", "approach", "strategy",
    "architecture", "design", "methodology", "framework",
    "convention", "standard", "guideline", "rule",
}


def infer_label(name: str, context: str = "") -> str:
    """Infer a vertex label from an entity name and surrounding context.

    Uses keyword matching heuristics to classify entities into
    Technology, Person, Project, Decision, Concept, or Domain.
    Falls back to ``Entity`` when uncertain.
    """
    name_lower = name.lower().strip()

    # Technology check (most common)
    if name_lower in _TECHNOLOGY_KEYWORDS:
        return "Technology"

    # Decision check (from context)
    ctx_lower = context.lower()
    for kw in _DECISION_KEYWORDS:
        if kw in ctx_lower:
            return "Decision"

    # Concept check
    for kw in _CONCEPT_KEYWORDS:
        if kw in name_lower:
            return "Concept"

    # Project check — names with dashes or underscores that aren't tech
    if ("-" in name or "_" in name) and name_lower not in _TECHNOLOGY_KEYWORDS:
        return "Project"

    # Person check — capitalized multi-word names
    words = name.split()
    if len(words) >= 2 and all(w[0].isupper() for w in words if w):
        return "Person"

    return "Entity"


# ── Report ────────────────────────────────────────────────────────────────────


@dataclass
class GraphMigrationReport:
    """Summary produced after a graph migration run."""

    memories_processed: int = 0
    entities_extracted: int = 0
    vertices_created: int = 0
    edges_created: int = 0
    errors: int = 0
    duration_seconds: float = 0.0


# ── Migration Job ─────────────────────────────────────────────────────────────


class GraphMigrationJob:
    """One-time job to populate the AGE graph from existing memories.

    Extracts entities from memory tags and ``properties.entities``,
    deduplicates by case-insensitive name, infers vertex labels,
    creates graph vertices, and links co-occurring entities.

    Args:
        session_factory: SQLAlchemy async session factory for reading memories.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._graph_store = None

    @property
    def graph_store(self):
        """Lazy-initialise the GraphStore."""
        if self._graph_store is None:
            from life_graph.storage.graph import GraphStore
            self._graph_store = GraphStore()
        return self._graph_store

    async def run(self) -> GraphMigrationReport:
        """Execute the full graph migration pipeline.

        Steps:
          1. Read all active memories
          2. Extract entities from tags + properties.entities
          3. Deduplicate entity names (case-insensitive)
          4. Infer labels and create vertices
          5. Create ``related_to`` edges for co-occurring entities
          6. Link vertices to memory UUIDs via properties

        Returns:
            A :class:`GraphMigrationReport` summarising the migration.
        """
        t0 = time.monotonic()
        report = GraphMigrationReport()

        # Step 1 — Read all active memories
        memories = await self._fetch_memories()
        report.memories_processed = len(memories)
        if not memories:
            logger.info("Graph migration: no memories to process")
            report.duration_seconds = time.monotonic() - t0
            return report

        # Step 2 & 3 — Extract and deduplicate entities
        entity_map, memory_entities = self._extract_entities(memories)
        report.entities_extracted = len(entity_map)

        # Step 4 — Create vertices
        for entity_name, info in entity_map.items():
            try:
                await self.graph_store.upsert_vertex(
                    label=info["label"],
                    name=entity_name,
                    properties={
                        "memory_ids": info["memory_ids"],
                        "occurrence_count": info["count"],
                    },
                )
                report.vertices_created += 1
            except Exception:
                logger.warning(
                    "Failed to create vertex for %s", entity_name,
                    exc_info=True,
                )
                report.errors += 1

        # Step 5 — Create edges for co-occurring entities
        edges_created: set[tuple[str, str]] = set()
        for memory_id, entity_names in memory_entities.items():
            for a, b in combinations(sorted(entity_names), 2):
                edge_key = (a, b)
                if edge_key in edges_created:
                    continue
                try:
                    a_label = entity_map[a]["label"]
                    b_label = entity_map[b]["label"]
                    await self.graph_store.create_edge(
                        from_label=a_label,
                        from_name=a,
                        to_label=b_label,
                        to_name=b,
                        edge_label="related_to",
                        properties={"source_memory": memory_id},
                    )
                    edges_created.add(edge_key)
                    report.edges_created += 1
                except Exception:
                    logger.warning(
                        "Failed to create edge %s -> %s", a, b,
                        exc_info=True,
                    )
                    report.errors += 1

        report.duration_seconds = time.monotonic() - t0
        logger.info(
            "Graph migration complete: %d memories → %d vertices, %d edges (%.2fs)",
            report.memories_processed,
            report.vertices_created,
            report.edges_created,
            report.duration_seconds,
        )
        return report

    # ── Private Helpers ───────────────────────────────────────

    async def _fetch_memories(self) -> list[Memory]:
        """Fetch all active memories from the database."""
        stmt = (
            select(Memory)
            .where(Memory.status == "active")
            .order_by(Memory.created_at.desc())
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    def _extract_entities(
        self, memories: list[Memory]
    ) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
        """Extract and deduplicate entities from memories.

        Returns:
            entity_map: ``{canonical_name: {label, count, memory_ids}}``
            memory_entities: ``{memory_id_str: {entity_names}}``
        """
        # entity_name (lowered) → {canonical_name, label, count, memory_ids}
        raw_entities: dict[str, dict[str, Any]] = {}
        # memory_id → set of canonical entity names
        memory_entities: dict[str, set[str]] = {}

        for memory in memories:
            mem_id = str(memory.id)
            mem_entities: set[str] = set()

            # Extract from tags
            if memory.tags:
                for tag in memory.tags:
                    tag_clean = tag.strip()
                    if tag_clean and len(tag_clean) >= 2:
                        mem_entities.add(tag_clean)

            # Extract from properties.entities
            if memory.properties and isinstance(memory.properties, dict):
                entities_list = memory.properties.get("entities", [])
                if isinstance(entities_list, list):
                    for entity in entities_list:
                        if isinstance(entity, str):
                            entity_clean = entity.strip()
                            if entity_clean and len(entity_clean) >= 2:
                                mem_entities.add(entity_clean)
                        elif isinstance(entity, dict):
                            name = entity.get("name", "").strip()
                            if name and len(name) >= 2:
                                mem_entities.add(name)

            # Deduplicate and build maps
            canonical_entities: set[str] = set()
            for entity_name in mem_entities:
                key = entity_name.lower()
                if key not in raw_entities:
                    label = infer_label(
                        entity_name, context=memory.content
                    )
                    raw_entities[key] = {
                        "canonical": entity_name,
                        "label": label,
                        "count": 0,
                        "memory_ids": [],
                    }
                raw_entities[key]["count"] += 1
                raw_entities[key]["memory_ids"].append(mem_id)
                canonical_entities.add(raw_entities[key]["canonical"])

            if canonical_entities:
                memory_entities[mem_id] = canonical_entities

        # Build final entity_map keyed by canonical name
        entity_map: dict[str, dict[str, Any]] = {}
        for info in raw_entities.values():
            entity_map[info["canonical"]] = {
                "label": info["label"],
                "count": info["count"],
                "memory_ids": info["memory_ids"][:50],  # cap stored IDs
            }

        return entity_map, memory_entities
