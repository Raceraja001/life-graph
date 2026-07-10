"""Multi-model advisor service — queries multiple LLMs for comparative recommendations.

Queries 2-3 models in parallel via OpenRouter / LiteLLM, parses structured
JSON responses, calculates consensus scores, and persists advisor sessions
for history and learning.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

import litellm

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.config import settings
from life_graph.models.db import AdvisorSession, Preference

logger = logging.getLogger(__name__)

# Cost per 1K tokens (USD)
MODEL_COSTS = {
    "openrouter/openai/gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "openrouter/deepseek/deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "openrouter/meta-llama/llama-3.1-8b-instruct": {"input": 0.00005, "output": 0.00008},
}

DEFAULT_MODELS = list(MODEL_COSTS.keys())
MODEL_TIMEOUT = 10  # seconds


@dataclass
class ModelResponse:
    """Response from a single model query."""

    model: str
    recommendation: str
    pros: list[str]
    cons: list[str]
    confidence: float
    reasoning: str
    tokens_used: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    status: str = "completed"  # completed | timeout | error


@dataclass
class AdvisorResult:
    """Aggregated result from querying multiple models."""

    session_id: uuid.UUID
    question: str
    responses: list[ModelResponse]
    consensus_score: float
    consensus_label: str
    winning_choice: str | None
    total_tokens: int
    total_cost_usd: float
    total_latency_ms: int
    context_used: list[dict]


class MultiModelAdvisor:
    """Queries multiple LLMs for comparative advice on technology decisions.

    Uses OpenRouter via LiteLLM to query 2-3 models in parallel,
    compares responses, calculates consensus, and persists sessions
    for learning and audit.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        openrouter_api_key: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._api_key = openrouter_api_key or settings.openrouter_api_key
        self._api_base = settings.openrouter_url
        self._timeout = settings.advisor_timeout_seconds

    # ── Public API ────────────────────────────────────────────

    async def ask(
        self,
        tenant_id: str,
        question: str,
        models: list[str] | None = None,
    ) -> AdvisorResult:
        """Query multiple models and return aggregated results.

        1. Fetch relevant user preferences for context
        2. Query models in parallel with timeout
        3. Parse JSON responses
        4. Calculate consensus
        5. Persist session
        6. Return AdvisorResult
        """
        models = models or self._get_configured_models()

        # Fetch preferences for context
        context_prefs = await self._fetch_preferences(tenant_id)
        context_dicts = [
            {"topic": p.topic, "choice": p.choice, "confidence": p.confidence}
            for p in context_prefs
        ]

        # Query all models in parallel
        tasks = [
            self._query_model(model, question, context_dicts)
            for model in models
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        responses: list[ModelResponse] = []
        for model, result in zip(models, raw_results):
            if isinstance(result, Exception):
                logger.warning("Model %s failed: %s", model, result)
                responses.append(ModelResponse(
                    model=model,
                    recommendation="",
                    pros=[],
                    cons=[],
                    confidence=0.0,
                    reasoning=str(result),
                    status="error",
                ))
            else:
                responses.append(result)

        # Calculate consensus
        completed = [r for r in responses if r.status == "completed"]
        consensus_score, consensus_label, winning_choice = self._calculate_consensus(
            completed
        )

        # Build result
        session_id = uuid.uuid4()
        total_tokens = sum(r.tokens_used for r in responses)
        total_cost = sum(r.cost_usd for r in responses)
        total_latency = max((r.latency_ms for r in responses), default=0)

        result = AdvisorResult(
            session_id=session_id,
            question=question,
            responses=responses,
            consensus_score=consensus_score,
            consensus_label=consensus_label,
            winning_choice=winning_choice,
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            context_used=context_dicts,
        )

        # Persist session
        await self._save_session(tenant_id, result)

        return result

    async def list_sessions(
        self,
        tenant_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """List advisor sessions for a tenant, most recent first."""
        async with self._session_factory() as session:
            stmt = (
                select(AdvisorSession)
                .where(AdvisorSession.tenant_id == tenant_id)
                .order_by(AdvisorSession.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": str(r.id),
                    "question": r.question,
                    "answer": r.answer,
                    "models_queried": (r.properties or {}).get("models_queried", r.sources_used),
                    "consensus_score": r.consensus_score,
                    "consensus_label": (r.properties or {}).get("consensus_label"),
                    "winning_choice": (r.properties or {}).get("winning_choice", r.answer),
                    "total_tokens": (r.properties or {}).get("total_tokens"),
                    "total_cost_usd": (r.properties or {}).get("total_cost_usd", 0.0),
                    "total_latency_ms": (r.properties or {}).get("total_latency_ms"),
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]

    async def get_session(
        self,
        tenant_id: str,
        session_id: uuid.UUID,
    ) -> dict | None:
        """Get a single advisor session by ID."""
        async with self._session_factory() as session:
            stmt = select(AdvisorSession).where(
                AdvisorSession.id == session_id,
                AdvisorSession.tenant_id == tenant_id,
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            props = row.properties or {}
            return {
                "id": str(row.id),
                "question": row.question,
                "answer": row.answer,
                "reasoning": row.reasoning,
                "models_queried": props.get("models_queried", row.sources_used),
                "responses": props.get("responses", {}),
                "consensus_score": row.consensus_score,
                "consensus_label": props.get("consensus_label"),
                "winning_choice": props.get("winning_choice", row.answer),
                "total_tokens": props.get("total_tokens"),
                "total_cost_usd": props.get("total_cost_usd", 0.0),
                "total_latency_ms": props.get("total_latency_ms"),
                "context_used": props.get("context_used"),
                "status": row.status,
                "created_at": row.created_at.isoformat(),
            }

    async def choose(
        self,
        tenant_id: str,
        session_id: uuid.UUID,
        chosen_model: str,
        notes: str | None = None,
    ) -> dict | None:
        """Record the user's choice for an advisor session."""
        async with self._session_factory() as session:
            stmt = select(AdvisorSession).where(
                AdvisorSession.id == session_id,
                AdvisorSession.tenant_id == tenant_id,
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None

            props = row.properties or {}
            props["chosen_model"] = chosen_model
            props["chosen_at"] = datetime.now(timezone.utc).isoformat()
            props["choice_notes"] = notes
            row.properties = props
            row.status = "chosen"
            await session.commit()

            return {
                "id": str(row.id),
                "chosen_model": chosen_model,
                "chosen_at": props["chosen_at"],
                "choice_notes": notes,
            }

    # ── Private Helpers ───────────────────────────────────────

    def _get_configured_models(self) -> list[str]:
        """Parse configured advisor models from settings."""
        raw = settings.advisor_models
        return [m.strip() for m in raw.split(",") if m.strip()]

    async def _fetch_preferences(
        self, tenant_id: str, limit: int = 20
    ) -> list[Preference]:
        """Fetch active preferences for context injection."""
        async with self._session_factory() as session:
            stmt = (
                select(Preference)
                .where(
                    Preference.tenant_id == tenant_id,
                    Preference.status == "active",
                )
                .order_by(Preference.confidence.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return list(rows)

    async def _query_model(
        self,
        model: str,
        question: str,
        context_preferences: list[dict],
    ) -> ModelResponse:
        """Query a single model via litellm with timeout."""
        preferences_json = json.dumps(context_preferences, indent=2) if context_preferences else "None yet."

        system_prompt = (
            "You are a technology advisor. The user has these current preferences:\n"
            f"{preferences_json}\n\n"
            'Answer the question with a JSON object:\n'
            '{"recommendation": "...", "pros": ["..."], "cons": ["..."], '
            '"confidence": 0.0-1.0, "reasoning": "..."}'
        )

        t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                    api_key=self._api_key,
                    api_base=self._api_base,
                    response_format={"type": "json_object"},
                    temperature=0.3,
                ),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            latency = int((time.monotonic() - t0) * 1000)
            logger.warning("Model %s timed out after %dms", model, latency)
            return ModelResponse(
                model=model,
                recommendation="",
                pros=[],
                cons=[],
                confidence=0.0,
                reasoning="Request timed out",
                latency_ms=latency,
                status="timeout",
            )
        except Exception as exc:
            latency = int((time.monotonic() - t0) * 1000)
            logger.warning("Model %s error: %s", model, exc)
            return ModelResponse(
                model=model,
                recommendation="",
                pros=[],
                cons=[],
                confidence=0.0,
                reasoning=str(exc),
                latency_ms=latency,
                status="error",
            )

        latency = int((time.monotonic() - t0) * 1000)

        # Parse response
        content = response.choices[0].message.content or "{}"
        usage = response.usage
        tokens_used = (usage.total_tokens if usage else 0)

        # Calculate cost
        costs = MODEL_COSTS.get(model, {"input": 0.0, "output": 0.0})
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        cost = (input_tokens * costs["input"] / 1000) + (output_tokens * costs["output"] / 1000)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {
                "recommendation": content[:500],
                "pros": [],
                "cons": [],
                "confidence": 0.3,
                "reasoning": "Response was not valid JSON",
            }

        return ModelResponse(
            model=model,
            recommendation=parsed.get("recommendation", ""),
            pros=parsed.get("pros", []),
            cons=parsed.get("cons", []),
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=parsed.get("reasoning", ""),
            tokens_used=tokens_used,
            latency_ms=latency,
            cost_usd=cost,
            status="completed",
        )

    def _calculate_consensus(
        self, responses: list[ModelResponse]
    ) -> tuple[float, str, str | None]:
        """Calculate consensus from completed model responses.

        Returns (score, label, winning_choice).
        - unanimous (1.0): all models agree
        - majority (0.67): most models agree
        - split (0.33): no clear agreement
        """
        if not responses:
            return 0.0, "split", None

        # Normalize recommendations for comparison
        recs = [r.recommendation.strip().lower() for r in responses if r.recommendation]
        if not recs:
            return 0.0, "split", None

        counter = Counter(recs)
        most_common, count = counter.most_common(1)[0]
        total = len(recs)

        if count == total:
            score, label = 1.0, "unanimous"
        elif count > total / 2:
            score, label = 0.67, "majority"
        else:
            score, label = 0.33, "split"

        # Find winning choice (original case from first match)
        winning = None
        for r in responses:
            if r.recommendation.strip().lower() == most_common:
                winning = r.recommendation
                break

        return score, label, winning

    async def _save_session(
        self, tenant_id: str, result: AdvisorResult
    ) -> None:
        """Persist an advisor session to the database."""
        responses_dict = {}
        for r in result.responses:
            responses_dict[r.model] = {
                "recommendation": r.recommendation,
                "pros": r.pros,
                "cons": r.cons,
                "confidence": r.confidence,
                "reasoning": r.reasoning,
                "tokens_used": r.tokens_used,
                "latency_ms": r.latency_ms,
                "cost_usd": r.cost_usd,
                "status": r.status,
            }

        row = AdvisorSession(
            id=result.session_id,
            tenant_id=tenant_id,
            question=result.question,
            answer=result.winning_choice,
            reasoning=result.responses[0].reasoning if result.responses else None,
            sources_used=[r.model for r in result.responses],
            consensus_score=result.consensus_score,
            status="answered",
            properties={
                "models_queried": [r.model for r in result.responses],
                "responses": responses_dict,
                "consensus_label": result.consensus_label,
                "winning_choice": result.winning_choice,
                "total_tokens": result.total_tokens,
                "total_cost_usd": result.total_cost_usd,
                "total_latency_ms": result.total_latency_ms,
                "context_used": result.context_used,
            },
        )

        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            logger.info(
                "Saved advisor session %s (consensus=%s, cost=$%.4f)",
                result.session_id,
                result.consensus_label,
                result.total_cost_usd,
            )
