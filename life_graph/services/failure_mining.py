"""Monthly failure-pattern mining (Judgment Engine, Story 6).

One LLM pass per month over a tenant's *failed* decisions (predictions that
resolved incorrect, or decisions that were reversed/superseded) to surface
recurring failure trajectories — e.g. "side projects abandoned around week 6".

The **instances-cited-or-dropped rule** is the trust guarantee: a pattern is
stored only if it cites at least ``MIN_INSTANCES`` distinct decision ids.
Uncited or thinly-cited patterns are discarded, never stored.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import or_, select

from life_graph.core.budget import BudgetCategory
from life_graph.models.db import Decision, Memory, Prediction
from life_graph.services.governor import governor
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

FAILURE_PATTERN_TAG = "failure_pattern"
MIN_INSTANCES = 3
# Estimated cost of the single monthly LLM mining pass (actual token cost is not
# individually metered here; a fixed estimate keeps the Governor's ledger honest).
ESTIMATED_MINING_COST_USD = 0.05
_FAILURE_STATUSES = ("superseded", "abandoned", "reversed")


class FailurePatternMiner:
    """Mines and stores failure-pattern memories for one tenant."""

    def __init__(self, *, session_factory=None, llm=None) -> None:
        self._sf = session_factory or async_session
        self._llm = llm

    # ── Gather ────────────────────────────────────────────────

    async def gather_failures(self, tenant_id: str) -> list[dict[str, Any]]:
        """Return failed decisions: incorrect-prediction or reversed/superseded."""
        async with self._sf() as session:
            incorrect_ids = (
                select(Prediction.decision_id)
                .where(
                    Prediction.tenant_id == tenant_id,
                    Prediction.outcome == "incorrect",
                    Prediction.decision_id.is_not(None),
                )
                .scalar_subquery()
            )
            result = await session.execute(
                select(Decision)
                .where(
                    Decision.tenant_id == tenant_id,
                    or_(
                        Decision.status.in_(_FAILURE_STATUSES),
                        Decision.id.in_(incorrect_ids),
                    ),
                )
                .order_by(Decision.created_at.asc())
            )
            return [
                {
                    "decision_id": str(d.id),
                    "title": d.title,
                    "reasoning": d.reasoning,
                    "domain_tags": d.domain_tags or [],
                    "status": d.status,
                }
                for d in result.scalars().all()
            ]

    # ── Mine (1 LLM pass) ─────────────────────────────────────

    async def mine(self, failures: list[dict]) -> list[dict[str, Any]]:
        """Single LLM pass turning failures into candidate patterns.

        Returns ``[{description, decision_ids}]``. No LLM configured or no
        failures → empty (nothing invented).
        """
        if not failures or self._llm is None:
            return []
        listing = "\n".join(
            f"- id={f['decision_id']} status={f['status']} "
            f"title={f['title']!r} tags={f['domain_tags']}"
            for f in failures
        )
        prompt = (
            "You analyze a person's failed decisions to find recurring failure "
            "patterns. Return JSON {\"patterns\": [{\"description\": str, "
            "\"decision_ids\": [str, ...]}]}. Only report a pattern if at least "
            f"{MIN_INSTANCES} of the listed decisions genuinely share it, and "
            "cite their exact ids. Invent nothing.\n\nFailed decisions:\n"
            f"{listing}"
        )
        raw = await self._llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        return self._parse_patterns(raw)

    @staticmethod
    def _parse_patterns(raw: str) -> list[dict[str, Any]]:
        """Parse the LLM JSON into a clean pattern list (robust to shape)."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failure-mining LLM returned non-JSON — dropping")
            return []
        items = data.get("patterns", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        out: list[dict[str, Any]] = []
        for p in items:
            if isinstance(p, dict) and p.get("description"):
                out.append(
                    {
                        "description": str(p["description"]),
                        "decision_ids": [
                            str(x) for x in (p.get("decision_ids") or [])
                        ],
                    }
                )
        return out

    # ── Citation rule (the trust guarantee) ───────────────────

    @staticmethod
    def enforce_citation_rule(
        patterns: list[dict], min_instances: int = MIN_INSTANCES
    ) -> list[dict[str, Any]]:
        """Keep only patterns citing ≥ ``min_instances`` distinct decision ids."""
        kept: list[dict[str, Any]] = []
        for p in patterns:
            ids = list(dict.fromkeys(p.get("decision_ids") or []))  # dedupe, keep order
            if len(ids) >= min_instances:
                kept.append({**p, "decision_ids": ids})
        return kept

    # ── Store ─────────────────────────────────────────────────

    async def store_patterns(
        self, tenant_id: str, patterns: list[dict]
    ) -> int:
        """Persist patterns as failure-pattern memories. Returns count stored."""
        if not patterns:
            return 0
        async with self._sf() as session:
            for p in patterns:
                session.add(
                    Memory(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        content=p["description"],
                        tags=[FAILURE_PATTERN_TAG],
                        importance=0.7,
                        importance_tier="high",
                        source_type="inferred",
                        source="failure_mining",
                        properties={
                            "kind": FAILURE_PATTERN_TAG,
                            "decision_ids": p["decision_ids"],
                            "instance_count": len(p["decision_ids"]),
                        },
                    )
                )
            await session.commit()
        return len(patterns)

    # ── Orchestration ─────────────────────────────────────────

    async def run(self, tenant_id: str) -> dict[str, Any]:
        """Full mine for a tenant: gather → LLM → citation rule → store."""
        failures = await self.gather_failures(tenant_id)
        if len(failures) < MIN_INSTANCES:
            return {
                "tenant_id": tenant_id,
                "failures": len(failures),
                "patterns_stored": 0,
                "reason": "insufficient_failures",
            }

        # Governor budget gate — the monthly LLM mining pass is low-priority
        # autonomous spend, so it is throttled first when the budget runs low.
        decision = await governor.authorize(
            tenant_id, BudgetCategory.FAILURE_MINING, estimated_usd=ESTIMATED_MINING_COST_USD,
        )
        if not decision.allowed:
            logger.info("Failure mining denied by Governor for %s: %s", tenant_id, decision.reason)
            return {
                "tenant_id": tenant_id,
                "failures": len(failures),
                "patterns_stored": 0,
                "reason": f"budget: {decision.reason}",
            }

        candidates = await self.mine(failures)
        await governor.record(tenant_id, BudgetCategory.FAILURE_MINING, ESTIMATED_MINING_COST_USD)
        kept = self.enforce_citation_rule(candidates)
        stored = await self.store_patterns(tenant_id, kept)
        logger.info(
            "Failure mining for %s: %d failures → %d candidates → %d stored",
            tenant_id, len(failures), len(candidates), stored,
        )
        return {
            "tenant_id": tenant_id,
            "failures": len(failures),
            "patterns_found": len(candidates),
            "patterns_stored": stored,
        }
