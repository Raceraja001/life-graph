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
from life_graph.services.llm_client import LMStudioClient
from life_graph.services.metamemory import MetamemoryTracker
from life_graph.services.recall import RecallEngine
from life_graph.services.synthesis import SynthesisService
from life_graph.services.impact import ImpactScorer
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
def get_lm_client() -> LMStudioClient:
    """Return the singleton LM Studio client."""
    return LMStudioClient()


@lru_cache(maxsize=1)
def get_extraction_pipeline() -> ExtractionPipeline:
    """Return the singleton extraction pipeline (rules → spaCy → LLM)."""
    from life_graph.config import settings
    from life_graph.extraction.llm import LLMExtractor
    lm_client = get_lm_client() if settings.use_local_llm else None
    llm_extractor = LLMExtractor(lm_client=lm_client)
    return ExtractionPipeline(llm_extractor=llm_extractor)


@lru_cache(maxsize=1)
def get_synthesis_service() -> SynthesisService:
    """Return the singleton synthesis service."""
    return SynthesisService(client=get_lm_client())


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


@lru_cache(maxsize=1)
def get_identity_service():
    """Return the singleton identity service."""
    from life_graph.services.identity import IdentityService
    return IdentityService(session_factory=async_session)


@lru_cache(maxsize=1)
def get_embedding_service():
    """Return the singleton embedding service."""
    from life_graph.services.embeddings import EmbeddingService
    from life_graph.config import settings
    lm_client = get_lm_client() if settings.use_local_llm else None
    return EmbeddingService(lm_client=lm_client)


@lru_cache(maxsize=1)
def get_consolidation_pipeline():
    """Return the singleton consolidation pipeline."""
    from life_graph.jobs.consolidation import ConsolidationPipeline
    return ConsolidationPipeline(
        session_factory=async_session,
        embedding_service=get_embedding_service(),
    )


@lru_cache(maxsize=1)
def get_job_scheduler():
    """Return the singleton job scheduler."""
    from life_graph.jobs.scheduler import JobScheduler
    return JobScheduler(consolidation=get_consolidation_pipeline())


@lru_cache(maxsize=1)
def get_agent_bridge():
    """Return the singleton agent bridge."""
    from life_graph.services.agent_bridge import LifeGraphBridge
    return LifeGraphBridge(
        store=get_store(),
        recall_engine=get_recall_engine(),
        memory_manager=get_memory_manager(),
        intention_service=get_intention_service(),
    )


@lru_cache(maxsize=1)
def get_impact_scorer() -> ImpactScorer:
    """Return the singleton impact scorer service."""
    return ImpactScorer()


@lru_cache(maxsize=1)
def get_micro_consolidator():
    """Return the singleton micro-consolidation service."""
    from life_graph.services.micro_consolidation import MicroConsolidator
    return MicroConsolidator(
        session_factory=async_session,
        embedding_service=get_embedding_service(),
    )


@lru_cache(maxsize=1)
def get_persona_service():
    """Return the singleton persona service."""
    from life_graph.kernel.personas import PersonaService
    return PersonaService(session_factory=async_session)


@lru_cache(maxsize=1)
def get_process_manager():
    """Return the singleton process manager."""
    from life_graph.kernel.process_manager import ProcessManager
    return ProcessManager(
        session_factory=async_session,
        persona_service=get_persona_service(),
    )


@lru_cache(maxsize=1)
def get_chief_router():
    """Return the singleton chief router."""
    from life_graph.kernel.chief_router import ChiefRouter
    return ChiefRouter(
        session_factory=async_session,
        persona_service=get_persona_service(),
        process_manager=get_process_manager(),
    )


@lru_cache(maxsize=1)
def get_scheduler_service():
    """Return the singleton scheduler service."""
    from life_graph.kernel.scheduler import SchedulerService
    return SchedulerService(
        session_factory=async_session,
        process_manager=get_process_manager(),
    )


@lru_cache(maxsize=1)
def get_project_registry():
    """Return the singleton project registry."""
    from life_graph.kernel.project_registry import ProjectRegistry
    return ProjectRegistry(session_factory=async_session)


@lru_cache(maxsize=1)
def get_notification_engine():
    """Return the singleton notification engine."""
    from life_graph.kernel.notification_engine import NotificationEngine
    return NotificationEngine(session_factory=async_session)


@lru_cache(maxsize=1)
def get_preference_store():
    """Return the singleton preference store."""
    from life_graph.services.preference_store import PreferenceStore
    return PreferenceStore(
        session_factory=async_session,
        embedding_service=get_embedding_service(),
    )


@lru_cache(maxsize=1)
def get_evidence_store():
    """Return the singleton evidence store."""
    from life_graph.services.evidence_store import EvidenceStore
    return EvidenceStore(
        session_factory=async_session,
        embedding_service=get_embedding_service(),
    )



@lru_cache(maxsize=1)
def get_multi_model_advisor():
    """Return the singleton multi-model advisor service."""
    from life_graph.services.multi_model_advisor import MultiModelAdvisor
    from life_graph.config import settings
    return MultiModelAdvisor(
        session_factory=async_session,
        openrouter_api_key=settings.openrouter_api_key,
    )


@lru_cache(maxsize=1)
def get_transcript_extractor():
    """Return the singleton transcript extractor service."""
    from life_graph.services.transcript_extractor import TranscriptExtractor
    return TranscriptExtractor(
        session_factory=async_session,
        embedding_service=get_embedding_service(),
    )


@lru_cache(maxsize=1)
def get_research_engine():
    """Return the singleton autonomous research engine."""
    from life_graph.services.research_engine import ResearchEngine
    from life_graph.config import settings
    return ResearchEngine(
        session_factory=async_session,
        preference_store=get_preference_store(),
        evidence_store=get_evidence_store(),
        advisor=get_multi_model_advisor(),
        settings=settings,
    )


# ── Self-Improving Agent (Era 5) ──────────────────────────────


@lru_cache(maxsize=1)
def get_eval_service():
    """Return the singleton eval service."""
    from life_graph.self_improving.eval_service import EvalService
    return EvalService(session_factory=async_session)


@lru_cache(maxsize=1)
def get_prompt_version_service():
    """Return the singleton prompt version service."""
    from life_graph.self_improving.prompt_version_service import PromptVersionService
    return PromptVersionService(session_factory=async_session)


@lru_cache(maxsize=1)
def get_optimizer_service():
    """Return the singleton DSPy optimizer service."""
    from life_graph.self_improving.optimizer_service import DSPyOptimizerService
    from life_graph.config import settings
    return DSPyOptimizerService(
        session_factory=async_session,
        eval_service=get_eval_service(),
        prompt_version_service=get_prompt_version_service(),
        settings=settings,
    )


@lru_cache(maxsize=1)
def get_dashboard_service():
    """Return the singleton dashboard service."""
    from life_graph.self_improving.dashboard_service import DashboardService
    return DashboardService(session_factory=async_session)


# ── Watcher Framework (Era 6) ────────────────────────────────


@lru_cache(maxsize=1)
def get_watcher_notification_engine():
    """Return the singleton watcher notification engine."""
    from life_graph.watchers.notification_engine import NotificationEngine
    return NotificationEngine(session_factory=async_session)


@lru_cache(maxsize=1)
def get_digest_generator():
    """Return the singleton digest generator."""
    from life_graph.watchers.digest import DigestGenerator
    return DigestGenerator(
        session_factory=async_session,
        notification_engine=get_watcher_notification_engine(),
    )


# ── Agent Networks (Era 7) ────────────────────────────────────


@lru_cache(maxsize=1)
def get_delegation_engine():
    """Return the singleton delegation engine."""
    from life_graph.services.delegation import DelegationEngine
    return DelegationEngine(session_factory=async_session)


@lru_cache(maxsize=1)
def get_messaging_service():
    """Return the singleton agent messaging service."""
    from life_graph.services.agent_messaging import AgentMessagingService
    return AgentMessagingService(session_factory=async_session)


@lru_cache(maxsize=1)
def get_sync_service():
    """Return the singleton cross-system sync service."""
    from life_graph.services.cross_system_sync import CrossSystemSyncService
    return CrossSystemSyncService(session_factory=async_session)


@lru_cache(maxsize=1)
def get_workflow_engine():
    """Return the singleton workflow engine."""
    from life_graph.services.workflow_engine import WorkflowEngine
    return WorkflowEngine(
        session_factory=async_session,
        delegation_engine=get_delegation_engine(),
    )


@lru_cache(maxsize=1)
def get_shared_context_service():
    """Return the singleton shared context service."""
    from life_graph.services.shared_context import SharedContextService
    return SharedContextService(
        session_factory=async_session,
        embedding_service=get_embedding_service(),
    )


# ── Autonomous AI (Era 8) ────────────────────────────────────


@lru_cache(maxsize=1)
def get_audit_service():
    """Return the singleton audit service."""
    from life_graph.autonomy.audit.service import AuditService
    return AuditService(session_factory=async_session)


@lru_cache(maxsize=1)
def get_approval_service():
    """Return the singleton approval service."""
    from life_graph.autonomy.approvals.service import ApprovalService
    return ApprovalService(
        session_factory=async_session,
        audit_service=get_audit_service(),
    )


@lru_cache(maxsize=1)
def get_autonomy_level_service():
    """Return the singleton autonomy level service."""
    from life_graph.autonomy.levels.service import AutonomyLevelService
    return AutonomyLevelService(
        session_factory=async_session,
        audit_service=get_audit_service(),
    )


def get_trust_service():
    """Return a trust-score service bound to a fresh session.

    ``TrustScoreService`` takes a live ``AsyncSession`` (not a factory), so this
    is not an lru-cached singleton — callers use it within their own session
    scope. Currently used by the trust-decay worker (which degrades gracefully
    if unavailable).
    """
    from life_graph.autonomy.trust.service import TrustScoreService
    return TrustScoreService(async_session())


@lru_cache(maxsize=1)
def get_autofix_service():
    """Return the singleton autofix pipeline service.

    The safety classifier is constructed per-request inside ``process`` (it needs
    a live session), so it is not injected here.
    """
    from life_graph.autonomy.pipeline.service import AutoFixService
    return AutoFixService(
        session_factory=async_session,
        audit_service=get_audit_service(),
        approval_service=get_approval_service(),
        level_service=get_autonomy_level_service(),
    )


# ── Agent Drivers ────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_task_dispatcher():
    """Return the singleton task dispatcher."""
    from life_graph.drivers.dispatcher import TaskDispatcher
    from life_graph.core.events import event_bus
    return TaskDispatcher(
        session_factory=async_session,
        event_bus=event_bus,
    )


@lru_cache(maxsize=1)
def get_results_loop():
    """Return the singleton results loop."""
    from life_graph.services.results_loop import ResultsLoop
    return ResultsLoop(session_factory=async_session)

