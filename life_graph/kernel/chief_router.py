"""Chief Router — intent classification and agent routing.

Classifies user messages by intent using regex pattern matching
(primary) with optional LLM-based classification. Routes to the
best specialist persona and tracks routing sessions.

Follows the QueryRouter pattern from life_graph.core.router:
compiled regex, scored matching, deterministic fallback.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.models.db import AgentSession

logger = logging.getLogger(__name__)


# ── Intent Pattern Definitions ─────────────────────────────

_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("code", [
        r"\bcode\b",
        r"\bimplement\b",
        r"\brefactor\b",
        r"\bdebug\b",
        r"\bfix\s+bug\b",
        r"\badd\s+feature\b",
        r"\bfunction\b",
        r"\bclass\b",
        r"\bendpoint\b",
        r"\b(?:write|create)\s+(?:a\s+)?"
        r"(?:script|module|service|api|test)\b",
        r"\bpull\s+request\b",
        r"\bpr\b",
        r"\bcode\s+review\b",
        r"\bsyntax\b",
        r"\bcompile\b",
        r"\bbuild\b",
        r"\btype\s*(?:error|hint)\b",
        r"\blint\b",
    ]),
    ("research", [
        r"\bresearch\b",
        r"\binvestigate\b",
        r"\bcompare\b",
        r"\bevaluate\b",
        r"\banalyze\b",
        r"\bwhat\s+is\b",
        r"\bhow\s+does\b",
        r"\bbest\s+practice\b",
        r"\bpros\s+and\s+cons\b",
        r"\blearn\s+about\b",
        r"\bexplore\b",
        r"\bstudy\b",
    ]),
    ("deploy", [
        r"\bdeploy\b",
        r"\brelease\b",
        r"\brollback\b",
        r"\bdocker\b",
        r"\bkubernetes\b",
        r"\bk8s\b",
        r"\bci/?cd\b",
        r"\bship\b",
        r"\bpush\s+to\b",
        r"\bproduction\b",
        r"\bstaging\b",
        r"\bnginx\b",
        r"\bhelm\b",
    ]),
    ("monitor", [
        r"\bmonitor\b",
        r"\balert\b",
        r"\bhealth\b",
        r"\bstatus\b",
        r"\buptime\b",
        r"\bmetrics?\b",
        r"\blogs?\b",
        r"\bdashboard\b",
        r"\bobservability\b",
    ]),
    ("data", [
        r"\bdata\b",
        r"\bdatabase\b",
        r"\bquery\b",
        r"\bsql\b",
        r"\bmigration\b",
        r"\bcsv\b",
        r"\banalyze\s+data\b",
        r"\bstatistics?\b",
        r"\breport\b",
        r"\betl\b",
        r"\bschema\b",
    ]),
    ("docs", [
        r"\bdocument(?:ation)?\b",
        r"\breadme\b",
        r"\bspec\b",
        r"\bchangelog\b",
        r"\bapi\s+docs?\b",
        r"\bopenapi\b",
        r"\bswagger\b",
        r"\btutorial\b",
        r"\bguide\b",
    ]),
    ("question", [
        r"^(?:what|how|why|when|where|who)\s",
        r"^(?:can\s+you|do\s+you|is\s+there)\s",
        r"^(?:tell\s+me|explain|describe)\s",
    ]),
]

# Default intent → persona mapping
DEFAULT_ROUTING: dict[str, str] = {
    "code": "cody",
    "research": "rex",
    "deploy": "ops",
    "monitor": "ops",
    "data": "penny",
    "docs": "scribe",
    "question": "chief",
    "general": "chief",
}


# ── Compiled Pattern Engine ────────────────────────────────


class _IntentRoute:
    """Compiled regex patterns for a single intent."""

    __slots__ = ("intent", "patterns")

    def __init__(
        self, intent: str, raw: list[str],
    ) -> None:
        self.intent = intent
        self.patterns: list[re.Pattern[str]] = [
            re.compile(p, re.IGNORECASE) for p in raw
        ]

    def score(self, text: str) -> int:
        """Count how many patterns match the text."""
        return sum(
            1 for p in self.patterns if p.search(text)
        )


# Pre-compile at module load
_COMPILED_INTENTS: list[_IntentRoute] = [
    _IntentRoute(intent, patterns)
    for intent, patterns in _INTENT_PATTERNS
]


# ── Chief Router ───────────────────────────────────────────


class ChiefRouter:
    """Classifies intent and routes to specialist personas.

    Uses regex-based classification (zero-LLM) as the primary
    approach, following the project preference for rule-based
    local solutions. Creates AgentSession records to track
    routing decisions.

    Args:
        session_factory: Async session factory for DB access.
        persona_service: PersonaService for persona resolution.
        process_manager: ProcessManager for task spawning.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        persona_service: Any,
        process_manager: Any,
    ) -> None:
        self._session_factory = session_factory
        self._persona_service = persona_service
        self._process_manager = process_manager

    # ── Public API ────────────────────────────────────────

    async def route(
        self,
        tenant_id: str,
        message: str,
        *,
        session_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Classify intent and route to the best agent.

        1. Classify user intent via regex patterns
        2. Resolve the best persona for the intent
        3. Create an AgentSession record
        4. Spawn a task via ProcessManager

        Args:
            tenant_id: Tenant scope.
            message: The user's message to classify.
            session_id: Optional existing session to continue.
            project_id: Optional project context.

        Returns:
            Dict with session_id, intent, agent, task info.
        """
        start = datetime.now(timezone.utc)

        # 1. Classify
        intent, confidence = self.classify(message)

        # 2. Resolve persona
        agent_name = await self._resolve_agent(
            tenant_id, intent,
        )

        # 3. Create/update session
        agent_session_id = await self._create_session(
            tenant_id=tenant_id,
            message=message,
            intent=intent,
            confidence=confidence,
            agent_name=agent_name,
            project_id=project_id,
        )

        # 4. Spawn task
        spawn_result = await self._process_manager.spawn(
            tenant_id=tenant_id,
            agent_name=agent_name,
            input_data={
                "message": message,
                "intent": intent,
                "confidence": confidence,
            },
            task_name=f"route:{intent}",
            session_id=agent_session_id,
            project_id=project_id,
        )

        elapsed_ms = int(
            (datetime.now(timezone.utc) - start)
            .total_seconds() * 1000
        )

        return {
            "session_id": str(agent_session_id),
            "classified_intent": intent,
            "classification_confidence": confidence,
            "routed_to": agent_name,
            "task_id": spawn_result.get(
                "task_id", str(spawn_result)
            ) if isinstance(spawn_result, dict)
            else str(spawn_result),
            "task_status": "queued",
            "routing_duration_ms": elapsed_ms,
        }

    def classify(
        self, message: str,
    ) -> tuple[str, float]:
        """Classify a message's intent using regex patterns.

        Scores each intent by counting matching patterns.
        Returns the highest-scoring intent, or 'general'
        with low confidence if nothing matches.

        Args:
            message: The user's message text.

        Returns:
            Tuple of (intent_name, confidence_score).
        """
        return self._classify_by_regex(message)

    async def classify_detailed(
        self, message: str,
    ) -> dict[str, Any]:
        """Classify with full metadata for debugging.

        Returns:
            Dict with intent, confidence, all_scores, method.
        """
        intent, confidence = self._classify_by_regex(message)

        # Also return all non-zero scores for transparency
        all_scores = {}
        for route in _COMPILED_INTENTS:
            score = route.score(message)
            if score > 0:
                all_scores[route.intent] = score

        return {
            "intent": intent,
            "confidence": confidence,
            "method": "regex",
            "all_scores": all_scores,
        }

    # ── Classification Engine ─────────────────────────────

    @staticmethod
    def _classify_by_regex(
        message: str,
    ) -> tuple[str, float]:
        """Score-based regex classification.

        Counts pattern matches per intent and selects the
        highest scorer. Confidence is calibrated as:
        min(0.95, 0.4 + matches * 0.15).

        Returns:
            Tuple of (intent, confidence).
        """
        best_intent = "general"
        best_score = 0

        for route in _COMPILED_INTENTS:
            score = route.score(message)
            if score > best_score:
                best_score = score
                best_intent = route.intent

        if best_score == 0:
            return ("general", 0.3)

        confidence = min(0.95, 0.4 + best_score * 0.15)
        return (best_intent, round(confidence, 2))

    # ── Persona Resolution ────────────────────────────────

    async def _resolve_agent(
        self, tenant_id: str, intent: str,
    ) -> str:
        """Resolve the best agent persona for an intent.

        First checks PersonaService for DB-configured
        intent mappings, then falls back to DEFAULT_ROUTING.

        Args:
            tenant_id: Tenant scope.
            intent: Classified intent string.

        Returns:
            Persona name (e.g., 'cody', 'rex').
        """
        # Try DB-configured personas first
        try:
            persona = await (
                self._persona_service.get_by_intent(
                    tenant_id, intent,
                )
            )
            if persona is not None:
                return persona["name"]
        except Exception:
            logger.warning(
                "Failed to query personas for intent %s",
                intent,
                exc_info=True,
            )

        # Fall back to default routing map
        return DEFAULT_ROUTING.get(intent, "chief")

    # ── Session Tracking ──────────────────────────────────

    async def _create_session(
        self,
        *,
        tenant_id: str,
        message: str,
        intent: str,
        confidence: float,
        agent_name: str,
        project_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Create an AgentSession record for tracking.

        Args:
            tenant_id: Tenant scope.
            message: Original user message.
            intent: Classified intent.
            confidence: Classification confidence.
            agent_name: Routed persona name.
            project_id: Optional project context.

        Returns:
            The session UUID.
        """
        session_id = uuid.uuid4()

        async with self._session_factory() as db:
            session_record = AgentSession(
                id=session_id,
                tenant_id=tenant_id,
                user_message=message,
                classified_intent=intent,
                classification_conf=confidence,
                routed_to=agent_name,
                handoff_chain=[
                    {"agent": agent_name, "step": 1},
                ],
                status="active",
                context={
                    "project_id": (
                        str(project_id)
                        if project_id else None
                    ),
                },
            )
            db.add(session_record)
            await db.commit()

        logger.info(
            "Created session %s: %s → %s (%.0f%%)",
            session_id,
            intent,
            agent_name,
            confidence * 100,
        )
        return session_id

    # ── Session Queries ───────────────────────────────────

    async def list_sessions(
        self,
        tenant_id: str,
        *,
        intent: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List routing sessions with optional filters.

        Args:
            tenant_id: Tenant scope.
            intent: Filter by classified intent.
            status: Filter by session status.
            limit: Max results per page.
            offset: Pagination offset.

        Returns:
            Tuple of (session dicts, total count).
        """
        async with self._session_factory() as db:
            base = select(AgentSession).where(
                AgentSession.tenant_id == tenant_id,
            )
            count_base = (
                select(func.count())
                .select_from(AgentSession)
                .where(AgentSession.tenant_id == tenant_id)
            )

            if intent:
                base = base.where(
                    AgentSession.classified_intent == intent,
                )
                count_base = count_base.where(
                    AgentSession.classified_intent == intent,
                )
            if status:
                base = base.where(
                    AgentSession.status == status,
                )
                count_base = count_base.where(
                    AgentSession.status == status,
                )

            count_result = await db.execute(count_base)
            total = count_result.scalar() or 0

            stmt = (
                base.order_by(
                    AgentSession.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
            result = await db.execute(stmt)
            sessions = [
                self._session_to_dict(s)
                for s in result.scalars().all()
            ]
            return sessions, total

    @staticmethod
    def _session_to_dict(
        session: AgentSession,
    ) -> dict[str, Any]:
        """Convert an AgentSession ORM instance to dict."""
        return {
            "id": str(session.id),
            "tenant_id": session.tenant_id,
            "user_message": session.user_message,
            "classified_intent": session.classified_intent,
            "classification_conf": (
                session.classification_conf
            ),
            "routed_to": session.routed_to,
            "handoff_chain": session.handoff_chain or [],
            "total_duration_ms": session.total_duration_ms,
            "total_tokens": session.total_tokens,
            "total_cost_usd": float(
                session.total_cost_usd or 0
            ),
            "status": session.status,
            "context": session.context or {},
            "created_at": session.created_at.isoformat(),
            "completed_at": (
                session.completed_at.isoformat()
                if session.completed_at else None
            ),
        }
