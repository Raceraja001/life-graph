"""Agent integration bridge for Life Graph (T-051).

Provides a high-level interface between the Life Graph memory system
and external AI agent frameworks (CrewAI, OpenHands, etc.).

Key responsibilities:
  - Build rich context for agents starting a task
  - Extract and store memories from completed agent conversations
  - Format recall context as system prompt additions

Usage::

    bridge = LifeGraphBridge(store, recall_engine, memory_manager, intention_service)
    ctx = await bridge.build_agent_context("Fix the auth bug", project="life_graph")
    # ctx['system_prompt_addon'] can be injected into the agent's system prompt
"""

from __future__ import annotations

import logging
from typing import Any

from life_graph.core.memory_manager import MemoryManager
from life_graph.models.schemas import IntentionResponse, MemoryResponse, RecallContext
from life_graph.services.intentions import IntentionService
from life_graph.services.recall import RecallEngine
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)

# Common task-description words that don't carry topical meaning
_STOP_WORDS: frozenset[str] = frozenset({
    "about", "after", "before", "being", "between", "could",
    "doing", "during", "every", "going", "having", "other",
    "should", "their", "there", "these", "thing", "those",
    "under", "using", "where", "which", "while", "would",
    "build", "create", "write", "please", "could", "would",
})


class LifeGraphBridge:
    """Bridge between Life Graph memory system and AI agent frameworks.

    Wraps the recall engine, memory manager, and intention service
    into a single façade that agents can call without knowing the
    internals of Life Graph.

    Typical flow:
        1. Agent starts a task → ``build_agent_context()``
        2. Agent completes a task → ``learn_from_task()``
    """

    def __init__(
        self,
        store: PostgresMemoryStore,
        recall_engine: RecallEngine,
        memory_manager: MemoryManager,
        intention_service: IntentionService,
    ) -> None:
        self.store = store
        self.recall = recall_engine
        self.manager = memory_manager
        self.intentions = intention_service

    # ── Public API ────────────────────────────────────────────

    async def build_agent_context(
        self,
        task: str,
        project: str | None = None,
    ) -> dict[str, Any]:
        """Build context for an agent starting a task.

        Runs the proactive recall pipeline and formats the results
        into a dict that agent frameworks can consume directly.

        Args:
            task: Natural-language task description.
            project: Optional project scope for filtering memories.

        Returns:
            Dict with keys: identity, decisions, intentions, warnings,
            system_prompt_addon, and topic metadata.
        """
        context: dict[str, Any] = {
            "project": project,
            "topics": self._extract_topics(task),
        }

        recall = await self.recall.session_start_recall(context)

        logger.info(
            "Built agent context for task (project=%s): "
            "%d identity, %d decisions, %d intentions, %d warnings",
            project,
            len(recall.identity),
            len(recall.decisions),
            len(recall.intentions),
            len(recall.warnings),
        )

        return {
            "identity": [m.content for m in recall.identity],
            "decisions": [m.content for m in recall.decisions],
            "intentions": [i.content for i in recall.intentions],
            "warnings": [m.content for m in recall.warnings],
            "system_prompt_addon": self._format_context(recall),
        }

    async def learn_from_task(
        self,
        conversation: str,
        source: str = "agent_task",
    ) -> list[MemoryResponse]:
        """Extract and store memories from an agent's task conversation.

        Runs the full ingestion pipeline (extract → score →
        contradiction check → store) on the conversation text.

        Args:
            conversation: Full text of the agent conversation.
            source: Source identifier for provenance tracking.

        Returns:
            List of MemoryResponse objects created from the conversation.
        """
        memories = await self.manager.ingest(
            text=conversation,
            source=source,
        )

        logger.info(
            "Learned %d memories from agent task (source=%s)",
            len(memories),
            source,
        )

        return [MemoryResponse.model_validate(m) for m in memories]

    # ── Internal Helpers ──────────────────────────────────────

    def _extract_topics(self, task: str) -> list[str]:
        """Extract significant keywords from a task description.

        Simple heuristic: words longer than 4 characters that aren't
        in the stop-word set. Returns at most 10 topics.

        Args:
            task: Natural-language task description.

        Returns:
            List of extracted topic keywords.
        """
        words = task.lower().split()
        return [w for w in words if len(w) > 4 and w not in _STOP_WORDS][:10]

    @staticmethod
    def _format_context(recall: RecallContext) -> str:
        """Format recall context as a system prompt addition.

        Produces a markdown-formatted string that can be appended
        to an agent's system prompt, organized by memory category.

        Args:
            recall: RecallContext from the proactive recall engine.

        Returns:
            Markdown string, or empty string if no memories are present.
        """
        sections: list[str] = []

        if recall.identity:
            lines = "\n".join(f"- {m.content}" for m in recall.identity)
            sections.append(f"## Developer Identity\n{lines}")

        if recall.decisions:
            lines = "\n".join(f"- {m.content}" for m in recall.decisions)
            sections.append(f"## Active Decisions\n{lines}")

        if recall.warnings:
            lines = "\n".join(f"- {m.content}" for m in recall.warnings)
            sections.append(f"## Warnings & Anti-patterns\n{lines}")

        if recall.intentions:
            lines = "\n".join(f"- {i.content}" for i in recall.intentions)
            sections.append(f"## Pending Intentions\n{lines}")

        return "\n\n".join(sections) if sections else ""
