"""Action classifier — risk assessment and recommendation engine.

Classifies actions through a pipeline: rule matching → trust evaluation →
autonomy level check → risk × autonomy matrix → recommendation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.autonomy.models import ActionSafetyRule, AutonomyLevel, TrustScore
from life_graph.autonomy.trust.calculator import TrustCalculator

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Action risk classification."""

    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


class Recommendation(str, Enum):
    """Recommended action handling strategy."""

    AUTO_EXECUTE = "auto_execute"
    NOTIFY_BEFORE = "notify_before"
    QUEUE_FOR_APPROVAL = "queue_for_approval"


@dataclass
class ClassificationResult:
    """Result of classifying an action through the safety pipeline."""

    risk_level: RiskLevel
    recommendation: Recommendation
    matched_rule: ActionSafetyRule | None = None
    trust_score: float = 0.0
    autonomy_level: str = "L0"
    reasoning: dict = field(default_factory=dict)


# ── Risk → Recommendation Matrix ─────────────────────────────
# Rows: autonomy level, Columns: risk level
_RECOMMENDATION_MATRIX: dict[str, dict[RiskLevel, Recommendation]] = {
    "L0": {
        RiskLevel.SAFE: Recommendation.QUEUE_FOR_APPROVAL,
        RiskLevel.MODERATE: Recommendation.QUEUE_FOR_APPROVAL,
        RiskLevel.DANGEROUS: Recommendation.QUEUE_FOR_APPROVAL,
    },
    "L1": {
        RiskLevel.SAFE: Recommendation.AUTO_EXECUTE,
        RiskLevel.MODERATE: Recommendation.QUEUE_FOR_APPROVAL,
        RiskLevel.DANGEROUS: Recommendation.QUEUE_FOR_APPROVAL,
    },
    "L2": {
        RiskLevel.SAFE: Recommendation.AUTO_EXECUTE,
        RiskLevel.MODERATE: Recommendation.NOTIFY_BEFORE,
        RiskLevel.DANGEROUS: Recommendation.QUEUE_FOR_APPROVAL,
    },
    "L3": {
        RiskLevel.SAFE: Recommendation.AUTO_EXECUTE,
        RiskLevel.MODERATE: Recommendation.AUTO_EXECUTE,
        RiskLevel.DANGEROUS: Recommendation.NOTIFY_BEFORE,
    },
}


class ActionClassifier:
    """Classifies actions and recommends handling strategy.

    Pipeline:
    1. Match action against safety rules (glob pattern)
    2. Load trust score for agent–action pair
    3. Load autonomy level for tenant–project
    4. Upgrade risk if trust below threshold
    5. Apply risk × autonomy matrix
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def classify(
        self,
        tenant_id: str,
        agent_id: str,
        action_name: str,
        action_command: str,
        project_id: str | None = None,
    ) -> ClassificationResult:
        """Run the full classification pipeline for an action."""
        # 1. Find matching rule
        rule = await self._find_matching_rule(tenant_id, action_name)

        # 2. No rule → default to DANGEROUS + QUEUE
        if rule is None:
            logger.info(
                "No safety rule matched for action=%s, defaulting to DANGEROUS",
                action_name,
            )
            return ClassificationResult(
                risk_level=RiskLevel.DANGEROUS,
                recommendation=Recommendation.QUEUE_FOR_APPROVAL,
                reasoning={"no_rule": True, "action_name": action_name},
            )

        # 3. Get trust score and autonomy level
        trust = await self._get_effective_trust(
            tenant_id, agent_id, action_name, project_id
        )
        autonomy = await self._get_autonomy_level(tenant_id, project_id)

        # 4. Start with rule's risk level
        base_risk = RiskLevel(rule.risk_level)

        # 5. Guardrail override — always queue
        if rule.is_guardrail:
            logger.info(
                "Guardrail rule matched: %s → forced QUEUE_FOR_APPROVAL",
                rule.action_name,
            )
            return ClassificationResult(
                risk_level=base_risk,
                recommendation=Recommendation.QUEUE_FOR_APPROVAL,
                matched_rule=rule,
                trust_score=trust,
                autonomy_level=autonomy,
                reasoning={
                    "rule_id": rule.id,
                    "guardrail": True,
                    "base_risk": base_risk.value,
                },
            )

        # 6. Upgrade risk if trust is below threshold
        effective_risk = self._upgrade_risk(
            base_risk, trust, float(rule.trust_threshold)
        )
        risk_upgraded = effective_risk != base_risk

        # 7. Determine recommendation from matrix
        recommendation = self._determine_recommendation(effective_risk, autonomy)

        reasoning = {
            "rule_id": rule.id,
            "rule_pattern": rule.action_pattern,
            "base_risk": base_risk.value,
            "effective_risk": effective_risk.value,
            "risk_upgraded": risk_upgraded,
            "trust_score": trust,
            "trust_threshold": float(rule.trust_threshold),
            "autonomy_level": autonomy,
        }

        logger.info(
            "Classified action=%s: risk=%s, recommendation=%s, trust=%.3f, level=%s",
            action_name,
            effective_risk.value,
            recommendation.value,
            trust,
            autonomy,
        )

        return ClassificationResult(
            risk_level=effective_risk,
            recommendation=recommendation,
            matched_rule=rule,
            trust_score=trust,
            autonomy_level=autonomy,
            reasoning=reasoning,
        )

    async def _find_matching_rule(
        self, tenant_id: str, action_name: str
    ) -> ActionSafetyRule | None:
        """Find the highest-priority enabled rule matching the action name via glob."""
        stmt = (
            select(ActionSafetyRule)
            .where(
                ActionSafetyRule.tenant_id == tenant_id,
                ActionSafetyRule.enabled.is_(True),
            )
            .order_by(ActionSafetyRule.priority.asc())
        )
        result = await self._session.execute(stmt)
        rules = result.scalars().all()

        for rule in rules:
            if fnmatch(action_name, rule.action_pattern):
                return rule

        return None

    async def _get_effective_trust(
        self,
        tenant_id: str,
        agent_id: str,
        action_type: str,
        project_id: str | None,
    ) -> float:
        """Get the minimum trust score across all applicable scopes."""
        stmt = select(TrustScore).where(
            TrustScore.tenant_id == tenant_id,
            TrustScore.agent_id == agent_id,
        )
        result = await self._session.execute(stmt)
        scores = result.scalars().all()

        if not scores:
            return 0.0

        effective_scores: list[float] = []

        for ts in scores:
            # Only consider relevant scopes
            is_relevant = (
                ts.action_type == action_type
                or ts.action_type == "*"
                or (project_id and ts.project_id == project_id)
            )
            if not is_relevant:
                continue

            if ts.manual_override is not None:
                effective_scores.append(float(ts.manual_override))
            else:
                decayed = TrustCalculator.apply_decay(
                    float(ts.score),
                    ts.last_action_at,
                    float(ts.decay_rate),
                )
                effective_scores.append(decayed)

        return min(effective_scores) if effective_scores else 0.0

    def _upgrade_risk(
        self, risk: RiskLevel, trust_score: float, threshold: float
    ) -> RiskLevel:
        """Upgrade risk level if trust is below the rule's threshold."""
        if trust_score >= threshold:
            return risk

        if risk == RiskLevel.SAFE:
            return RiskLevel.MODERATE
        elif risk == RiskLevel.MODERATE:
            return RiskLevel.DANGEROUS
        return RiskLevel.DANGEROUS

    def _determine_recommendation(
        self, risk: RiskLevel, autonomy_level: str
    ) -> Recommendation:
        """Apply the risk × autonomy matrix to get a recommendation."""
        level_matrix = _RECOMMENDATION_MATRIX.get(autonomy_level)
        if level_matrix is None:
            return Recommendation.QUEUE_FOR_APPROVAL
        return level_matrix.get(risk, Recommendation.QUEUE_FOR_APPROVAL)

    async def _get_autonomy_level(
        self, tenant_id: str, project_id: str | None
    ) -> str:
        """Load the autonomy level for a tenant–project pair."""
        if project_id is None:
            return "L0"

        stmt = select(AutonomyLevel).where(
            AutonomyLevel.tenant_id == tenant_id,
            AutonomyLevel.project_id == project_id,
        )
        result = await self._session.execute(stmt)
        level = result.scalar_one_or_none()

        if level is None:
            return "L0"

        # Manual override takes precedence
        if level.manual_level:
            return level.manual_level

        return level.level
