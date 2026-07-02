"""Cold start bootstrap orchestrator.

Ties together GitAnalyzer, ConfigParser, and CodeAnalyzer to produce
50+ memories from existing project data. Handles deduplication,
embedding generation, and storage — all with zero LLM API calls.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from life_graph.cold_start.code_analyzer import CodeAnalyzer
from life_graph.cold_start.config_parser import ConfigParser
from life_graph.cold_start.git_analyzer import GitAnalyzer
from life_graph.models.schemas import MemoryCreate
from life_graph.services.embeddings import EmbeddingService
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)


class ColdStartBootstrap:
    """Orchestrate the cold start pipeline for Life Graph.

    Runs local analyzers on Git repos, config files, and Python code,
    then deduplicates, embeds, and stores all memories in PostgreSQL.
    """

    def __init__(
        self,
        store: PostgresMemoryStore,
        embedding_service: EmbeddingService,
    ) -> None:
        self._store = store
        self._embeddings = embedding_service
        self._git = GitAnalyzer()
        self._config = ConfigParser()
        self._code = CodeAnalyzer()

    async def run(self, config: dict[str, Any]) -> dict[str, Any]:
        """Execute the full cold start bootstrap pipeline.

        Args:
            config: Configuration dict with keys:
                - git_repos (list[str]): Paths to Git repositories.
                - author_name (str | None): Optional Git author filter.
                - obsidian_vault (str | None): Path to Obsidian vault (future).

        Returns:
            Summary dict with total_memories, time_seconds, and by_source counts.
        """
        start = time.monotonic()
        all_memories: list[dict[str, Any]] = []
        source_counts: dict[str, int] = {"git": 0, "config": 0, "code": 0}

        git_repos = config.get("git_repos", [])
        author_name = config.get("author_name")

        # ── Phase 1: Analyze each repository ──────────────────
        for repo_path in git_repos:
            logger.info("Processing repository: %s", repo_path)

            git_memories = self._run_safe(
                "GitAnalyzer", self._git.analyze, repo_path, author_name
            )
            all_memories.extend(git_memories)
            source_counts["git"] += len(git_memories)

            config_memories = self._run_safe(
                "ConfigParser", self._config.parse, repo_path
            )
            all_memories.extend(config_memories)
            source_counts["config"] += len(config_memories)

            code_memories = self._run_safe(
                "CodeAnalyzer", self._code.analyze, repo_path
            )
            all_memories.extend(code_memories)
            source_counts["code"] += len(code_memories)

        logger.info(
            "Phase 1 complete: %d raw memories collected", len(all_memories)
        )

        # ── Phase 2: Deduplicate ──────────────────────────────
        pre_dedup = len(all_memories)
        all_memories = self._deduplicate(all_memories)
        dupes_removed = pre_dedup - len(all_memories)
        logger.info(
            "Phase 2 complete: %d duplicates removed, %d remaining",
            dupes_removed, len(all_memories),
        )

        # ── Phase 3: Generate embeddings ──────────────────────
        contents = [m["content"] for m in all_memories]
        embeddings = self._embeddings.embed_batch(contents)
        logger.info(
            "Phase 3 complete: %d embeddings generated",
            sum(1 for e in embeddings if e),
        )

        # ── Phase 4: Store in PostgreSQL ──────────────────────
        stored_count = 0
        for memory_dict, embedding in zip(all_memories, embeddings):
            try:
                create_payload = MemoryCreate(
                    content=memory_dict["content"],
                    tags=memory_dict.get("tags"),
                    importance=memory_dict.get("importance", 0.5),
                    source_type="cold_start",
                    properties={
                        "source": memory_dict.get("source", "cold_start"),
                        "type_tag": memory_dict.get("type_tag", "unknown"),
                    },
                )
                row = await self._store.store(create_payload)

                # Set embedding directly if available
                if embedding and row:
                    await self._set_embedding(row.id, embedding)

                stored_count += 1
            except Exception:
                logger.exception(
                    "Failed to store memory: %s",
                    memory_dict.get("content", "")[:60],
                )

        elapsed = round(time.monotonic() - start, 2)
        summary = {
            "total_memories": stored_count,
            "duplicates_removed": dupes_removed,
            "time_seconds": elapsed,
            "by_source": source_counts,
            "api_calls_made": 0,
        }

        logger.info(
            "Cold start complete: %d memories stored in %.1fs "
            "(git=%d, config=%d, code=%d)",
            stored_count, elapsed,
            source_counts["git"], source_counts["config"],
            source_counts["code"],
        )
        return summary

    # ── Private Helpers ───────────────────────────────────────

    def _run_safe(
        self, name: str, func: Any, *args: Any
    ) -> list[dict[str, Any]]:
        """Run an analyzer function and catch any exceptions."""
        try:
            return func(*args)
        except Exception:
            logger.exception("%s failed", name)
            return []

    def _deduplicate(
        self, memories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove near-duplicate memories by content hash.

        When duplicates are found, keeps the one with highest importance.
        """
        seen: dict[str, dict[str, Any]] = {}

        for memory in memories:
            key = hashlib.md5(
                memory["content"].lower().strip().encode()
            ).hexdigest()

            if key not in seen:
                seen[key] = memory
            elif memory.get("importance", 0) > seen[key].get("importance", 0):
                seen[key] = memory

        return list(seen.values())

    async def _set_embedding(
        self, memory_id: Any, embedding: list[float]
    ) -> None:
        """Update the embedding column for a stored memory."""
        from sqlalchemy import update

        from life_graph.models.db import Memory
        from life_graph.storage.database import async_session

        async with async_session() as session:
            await session.execute(
                update(Memory)
                .where(Memory.id == memory_id)
                .values(embedding=embedding)
            )
            await session.commit()
