"""FastAPI dependency injection for Life Graph services.

Provides singleton-style dependency providers using ``@lru_cache``
so that expensive objects (extractors, rankers, engines) are created
only once per process lifetime.

All public functions are designed to be used with ``Depends()``
in route handlers.
"""

from __future__ import annotations

from functools import lru_cache

from life_graph.core.memory_manager import MemoryManager
from life_graph.core.router import QueryRouter
from life_graph.extraction.pipeline import ExtractionPipeline
from life_graph.scoring.importance import ImportanceTagger
from life_graph.scoring.ranking import RecallRanker
from life_graph.services.context import ContextBuilder
from life_graph.services.contradiction import ContradictionDetector
from life_graph.services.intentions import IntentionService
from life_graph.services.metamemory import MetamemoryTracker
from life_graph.services.recall import RecallEngine
from life_graph.storage.database import async_session
from life_graph.storage.postgres import PostgresMemoryStore


@lru_cache(maxsize=1)
def get_store() -> PostgresMemoryStore:
    """Return the singleton PostgreSQL memory store.

    ``PostgresMemoryStore`` opens its own sessions internally via
    the module-level ``async_session`` factory, so no session argument
    is required here.
    """
    return PostgresMemoryStore()


@lru_cache(maxsize=1)
def get_extraction_pipeline() -> ExtractionPipeline:
    """Return the singleton extraction pipeline (rules → spaCy → LLM)."""
    return ExtractionPipeline()


@lru_cache(maxsize=1)
def get_importance_tagger() -> ImportanceTagger:
    """Return the singleton importance tagger."""
    return ImportanceTagger()


@lru_cache(maxsize=1)
def get_contradiction_detector() -> ContradictionDetector:
    """Return the singleton contradiction detector."""
    return ContradictionDetector(store=get_store())


@lru_cache(maxsize=1)
def get_memory_manager() -> MemoryManager:
    """Return the singleton memory manager (ingestion orchestrator)."""
    return MemoryManager(
        store=get_store(),
        extractor=get_extraction_pipeline(),
        tagger=get_importance_tagger(),
        contradiction_detector=get_contradiction_detector(),
    )


@lru_cache(maxsize=1)
def get_context_builder() -> ContextBuilder:
    """Return the singleton context builder."""
    return ContextBuilder()


@lru_cache(maxsize=1)
def get_ranker() -> RecallRanker:
    """Return the singleton recall ranker."""
    return RecallRanker()


@lru_cache(maxsize=1)
def get_recall_engine() -> RecallEngine:
    """Return the singleton proactive recall engine."""
    return RecallEngine(
        store=get_store(),
        ranker=get_ranker(),
        context_builder=get_context_builder(),
    )


@lru_cache(maxsize=1)
def get_intention_service() -> IntentionService:
    """Return the singleton intention service."""
    return IntentionService(session_factory=async_session)


@lru_cache(maxsize=1)
def get_metamemory() -> MetamemoryTracker:
    """Return the singleton metamemory tracker."""
    return MetamemoryTracker(session_factory=async_session)


@lru_cache(maxsize=1)
def get_router() -> QueryRouter:
    """Return the singleton query router (pattern-based, zero LLM)."""
    return QueryRouter()
