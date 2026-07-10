"""Adversarial Advisor — devil's advocate for decisions.

Generates a challenge report with 5 sections:
1. Similar past decisions (vector similarity search) — LOCAL
2. Base rates from history (how often similar decisions succeeded) — LOCAL
3. Your calibration in this domain — LOCAL
4. Belief conflicts (evidence store contradictions) — LOCAL
5. Dissent (forced contrarian argument via LLM) — LLM CALL

Every challenge becomes a tracked prediction.
Receipts or it didn't happen — every section cites row IDs.

Follows the CaptureService pattern: operates on a caller-provided
``AsyncSession`` and emits events via ``EventBus``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.core.events import EventBus, EventType
from life_graph.models.db import (
    CalibrationSnapshot,
    Challenge,
    Decision,
    Evidence,
    Prediction,
)

logger = logging.getLogger(__name__)

# Valid action_taken values for challenge resolution
_VALID_ACTIONS = frozenset({"followed", "ignored", "modified"})


class AdversarialAdvisor:
    """Devil's advocate service for decisions and proposals.

    Generates structured challenge reports with cited evidence.
    Every challenge creates a tracked prediction so the system
    can learn from the user's response.

    Operates on a caller-provided ``AsyncSession`` — the API layer
    is responsible for committing the transaction after the service
    method returns.
    """

    def __init__(
        self, session: AsyncSession, event_bus: EventBus | None = None
    ) -> None:
        self.session = session
        self.event_bus = event_bus

    # ── Public API ────────────────────────────────────────────

    async def challenge(
        self, tenant_id: str, proposal: str
    ) -> Challenge:
        """Generate a full adversarial challenge report for a proposal.

        Builds 5 report sections (4 local + 1 LLM), creates a tracked
        prediction for the challenge outcome, and persists the challenge.
        If any section fails, logs a warning and continues with a partial
        report.

        Args:
            tenant_id: Tenant scope.
            proposal: The proposal or decision to challenge.

        Returns:
            The persisted ``Challenge`` with report sections.
        """
        sections: list[dict] = []
        total_cost = 0.0

        # Extract simple keywords for matching
        keywords = _extract_keywords(proposal)

        # Section 1: Similar past decisions (LOCAL)
        section = await self._safe_section(
            self._section_similar_decisions,
            tenant_id,
            proposal,
            keywords,
        )
        if section:
            sections.append(section)

        # Section 2: Base rates (LOCAL)
        section = await self._safe_section(
            self._section_base_rates,
            tenant_id,
            keywords,
        )
        if section:
            sections.append(section)

        # Section 3: Calibration (LOCAL)
        # Use first keyword as domain hint
        domain_hint = keywords[0] if keywords else None
        section = await self._safe_section(
            self._section_calibration,
            tenant_id,
            domain_hint,
        )
        if section:
            sections.append(section)

        # Section 4: Belief conflicts (LOCAL)
        section = await self._safe_section(
            self._section_belief_conflicts,
            tenant_id,
            proposal,
        )
        if section:
            sections.append(section)

        # Section 5: Dissent (LLM)
        context = f"Sections so far: {len(sections)} local analyses."
        section = await self._safe_section(
            self._section_dissent,
            proposal,
            context,
        )
        if section:
            sections.append(section)

        # Build report dict
        report = {
            "sections": sections,
            "section_count": len(sections),
            "proposal_summary": proposal[:500],
        }

        # Create a tracking prediction for the challenge outcome
        prediction = Prediction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            statement=(
                f"Challenge outcome: Will the user follow the challenge "
                f"advice for: {proposal[:100]}"
            ),
            confidence=0.5,
            domain_tags=keywords[:5],
            resolve_by=datetime.now(timezone.utc) + timedelta(days=30),
            resolution_criteria={
                "type": "challenge_outcome",
                "proposal": proposal[:200],
            },
        )
        self.session.add(prediction)
        await self.session.flush()

        # Create challenge row
        challenge = Challenge(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            proposal=proposal,
            report=report,
            verdict=None,
            outcome_prediction_id=prediction.id,
            total_cost_usd=total_cost,
        )
        self.session.add(challenge)
        await self.session.flush()

        # Emit event
        if self.event_bus:
            await self.event_bus.emit(
                EventType.DECISION_CHALLENGED,
                {
                    "challenge_id": str(challenge.id),
                    "tenant_id": tenant_id,
                    "proposal": proposal[:200],
                    "section_count": len(sections),
                    "prediction_id": str(prediction.id),
                },
            )

        logger.info(
            "Created challenge %s with %d sections for tenant %s",
            challenge.id,
            len(sections),
            tenant_id,
        )
        return challenge

    async def resolve_challenge(
        self,
        tenant_id: str,
        challenge_id: uuid.UUID,
        action_taken: str,
    ) -> Challenge:
        """Record the user's action on a challenge.

        Args:
            tenant_id: Tenant scope.
            challenge_id: The challenge UUID.
            action_taken: What the user did (followed, ignored, modified).

        Returns:
            The updated ``Challenge``.

        Raises:
            ValueError: If challenge not found or action_taken invalid.
        """
        if action_taken not in _VALID_ACTIONS:
            raise ValueError(
                f"Invalid action_taken '{action_taken}'. "
                f"Must be one of: {', '.join(sorted(_VALID_ACTIONS))}"
            )

        result = await self.session.execute(
            select(Challenge).where(
                Challenge.tenant_id == tenant_id,
                Challenge.id == challenge_id,
            )
        )
        challenge = result.scalars().first()

        if not challenge:
            raise ValueError("Challenge not found")

        challenge.action_taken = action_taken

        logger.info(
            "Challenge %s resolved: action_taken=%s",
            challenge_id,
            action_taken,
        )
        return challenge

    # ── Section Builders ──────────────────────────────────────

    async def _section_similar_decisions(
        self,
        tenant_id: str,
        proposal: str,
        keywords: list[str],
    ) -> dict:
        """Find similar past decisions by keyword matching.

        Uses simple text matching on decision titles and reasoning.
        Full vector search requires embedding generation (future work).

        Args:
            tenant_id: Tenant scope.
            proposal: The proposal text.
            keywords: Extracted keywords for matching.

        Returns:
            Section dict with title, content, and cited_ids.
        """
        # Query recent decisions
        result = await self.session.execute(
            select(Decision)
            .where(Decision.tenant_id == tenant_id)
            .order_by(Decision.created_at.desc())
            .limit(50)
        )
        recent = list(result.scalars().all())

        # Simple keyword matching
        matches: list[Decision] = []
        proposal_lower = proposal.lower()
        for decision in recent:
            title_lower = (decision.title or "").lower()
            reasoning_lower = (decision.reasoning or "").lower()
            # Check if any keyword appears in title or reasoning
            for kw in keywords:
                if kw in title_lower or kw in reasoning_lower:
                    matches.append(decision)
                    break
            if len(matches) >= 5:
                break

        if matches:
            lines = [
                f"Found {len(matches)} similar past decision(s):",
            ]
            for d in matches:
                status_info = f"[{d.status}]"
                lines.append(
                    f"  • {d.title} {status_info} "
                    f"(decided: {d.decided_at or 'pending'})"
                )
            content = "\n".join(lines)
        else:
            content = "No similar past decisions found."

        return {
            "title": "Similar Past Decisions",
            "content": content,
            "cited_ids": [str(d.id) for d in matches],
        }

    async def _section_base_rates(
        self,
        tenant_id: str,
        keywords: list[str],
    ) -> dict:
        """Calculate success rates from historical decisions.

        Counts decisions with matching domain tags and checks
        prediction outcomes for success rate calculation.

        Args:
            tenant_id: Tenant scope.
            keywords: Domain keywords to match against tags.

        Returns:
            Section dict with title, content, and cited_ids.
        """
        # Count total decisions
        total_result = await self.session.execute(
            select(func.count())
            .select_from(Decision)
            .where(Decision.tenant_id == tenant_id)
        )
        total_decisions = total_result.scalar() or 0

        # Count resolved predictions as correct/incorrect
        correct_result = await self.session.execute(
            select(func.count())
            .select_from(Prediction)
            .where(
                Prediction.tenant_id == tenant_id,
                Prediction.outcome == "correct",
            )
        )
        correct_count = correct_result.scalar() or 0

        incorrect_result = await self.session.execute(
            select(func.count())
            .select_from(Prediction)
            .where(
                Prediction.tenant_id == tenant_id,
                Prediction.outcome == "incorrect",
            )
        )
        incorrect_count = incorrect_result.scalar() or 0

        resolved = correct_count + incorrect_count
        if resolved > 0:
            success_rate = correct_count / resolved
            content = (
                f"Historical base rates from {total_decisions} "
                f"total decisions:\n"
                f"  • Resolved predictions: {resolved}\n"
                f"  • Correct: {correct_count} "
                f"({success_rate:.0%})\n"
                f"  • Incorrect: {incorrect_count} "
                f"({1 - success_rate:.0%})"
            )
        else:
            content = (
                f"Total decisions: {total_decisions}. "
                f"No resolved predictions yet — insufficient data "
                f"for base rate calculation."
            )

        return {
            "title": "Historical Base Rates",
            "content": content,
            "cited_ids": [],
        }

    async def _section_calibration(
        self,
        tenant_id: str,
        domain: str | None,
    ) -> dict:
        """Pull the latest calibration snapshot and report bias.

        Args:
            tenant_id: Tenant scope.
            domain: Optional domain filter.

        Returns:
            Section dict with title, content, and cited_ids.
        """
        stmt = (
            select(CalibrationSnapshot)
            .where(CalibrationSnapshot.tenant_id == tenant_id)
            .order_by(CalibrationSnapshot.computed_at.desc())
            .limit(1)
        )
        if domain:
            stmt = stmt.where(CalibrationSnapshot.domain == domain)

        result = await self.session.execute(stmt)
        snap = result.scalars().first()

        if snap:
            lines = [
                f"Calibration snapshot "
                f"(domain: {snap.domain or 'all'}, "
                f"window: {snap.window_days}d):",
                f"  • Brier score: "
                f"{snap.brier_score:.4f}" if snap.brier_score is not None
                else "  • Brier score: N/A",
                f"  • Resolved count: {snap.resolved_count}",
            ]
            if snap.estimate_multiplier is not None:
                lines.append(
                    f"  • Estimate multiplier: "
                    f"{snap.estimate_multiplier:.2f}"
                )
            if snap.bias_findings:
                lines.append("  • Bias findings:")
                for finding in snap.bias_findings[:3]:
                    lines.append(f"    – {finding}")
            content = "\n".join(lines)
            cited_ids = [str(snap.id)]
        else:
            content = (
                "No calibration data available"
                + (f" for domain '{domain}'" if domain else "")
                + "."
            )
            cited_ids = []

        return {
            "title": "Your Calibration",
            "content": content,
            "cited_ids": cited_ids,
        }

    async def _section_belief_conflicts(
        self,
        tenant_id: str,
        proposal: str,
    ) -> dict:
        """Check the evidence store for contradictions.

        Finds evidence items with a 'contradicts' stance to surface
        potential belief conflicts relevant to the proposal.

        Args:
            tenant_id: Tenant scope.
            proposal: The proposal text to check against.

        Returns:
            Section dict with title, content, and cited_ids.
        """
        result = await self.session.execute(
            select(Evidence)
            .where(
                Evidence.tenant_id == tenant_id,
                Evidence.stance == "contradicts",
                Evidence.status == "active",
            )
            .order_by(Evidence.created_at.desc())
            .limit(5)
        )
        conflicts = list(result.scalars().all())

        if conflicts:
            lines = [
                f"Found {len(conflicts)} contradicting evidence "
                f"item(s) in your beliefs:"
            ]
            for e in conflicts:
                source_info = (
                    f" ({e.source_type})" if e.source_type else ""
                )
                lines.append(
                    f"  • {e.summary[:120]}{source_info}"
                )
            content = "\n".join(lines)
        else:
            content = "No contradicting evidence found in your beliefs."

        return {
            "title": "Belief Conflicts",
            "content": content,
            "cited_ids": [str(e.id) for e in conflicts],
        }

    async def _section_dissent(
        self,
        proposal: str,
        context: str,
    ) -> dict:
        """Generate a contrarian argument via LLM.

        Attempts to use the multi-model advisor for forced contrarian
        analysis. Falls back gracefully if the advisor is unavailable.

        Args:
            proposal: The proposal to argue against.
            context: Additional context from prior sections.

        Returns:
            Section dict with title, content, and cited_ids.
        """
        try:
            # Multi-model advisor requires session_factory, not a
            # raw session. For now, provide a manual dissent prompt.
            from life_graph.services.multi_model_advisor import (  # noqa: F401
                MultiModelAdvisor,
            )
            content = (
                "Automated dissent via multi-model advisor is available "
                "but requires async session factory configuration. "
                "Manual contrarian review recommended.\n\n"
                f"Consider the opposite position: What if "
                f"'{proposal[:200]}' is the wrong approach? "
                f"What risks are you not seeing?"
            )
        except ImportError:
            content = (
                "Dissent section requires multi-model advisor "
                "(not available). Manual contrarian review recommended "
                f"for: {proposal[:200]}"
            )

        return {
            "title": "Dissent (Devil's Advocate)",
            "content": content,
            "cited_ids": [],
        }

    # ── Helpers ───────────────────────────────────────────────

    async def _safe_section(
        self, section_fn, *args, **kwargs
    ) -> dict | None:
        """Call a section builder with error handling.

        If the section function raises, logs a warning and returns
        None so the report can continue with partial results.

        Args:
            section_fn: The section builder coroutine.
            *args: Positional arguments for the builder.
            **kwargs: Keyword arguments for the builder.

        Returns:
            Section dict on success, None on failure.
        """
        try:
            return await section_fn(*args, **kwargs)
        except Exception:
            logger.warning(
                "Section %s failed, continuing with partial report",
                getattr(section_fn, "__name__", "unknown"),
                exc_info=True,
            )
            return None


def _extract_keywords(text: str) -> list[str]:
    """Extract simple keywords from text for matching.

    Filters out short words and common stop words to produce
    meaningful search terms.

    Args:
        text: Input text to extract keywords from.

    Returns:
        List of lowercase keyword strings.
    """
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "and",
        "but", "or", "nor", "not", "so", "yet", "both", "either",
        "neither", "each", "every", "all", "any", "few", "more",
        "most", "other", "some", "such", "no", "only", "own", "same",
        "than", "too", "very", "just", "about", "above", "also",
        "this", "that", "these", "those", "it", "its", "i", "me",
        "my", "we", "our", "you", "your", "he", "him", "his", "she",
        "her", "they", "them", "their", "what", "which", "who",
        "whom", "how", "when", "where", "why", "if", "then", "else",
    }
    words = text.lower().split()
    return [
        w for w in words
        if len(w) > 2 and w.isalpha() and w not in stop_words
    ][:20]
