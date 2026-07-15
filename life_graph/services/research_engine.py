"""Autonomous research engine (Era 4 Personal AI — Phase 6).

Periodically searches external sources (HN, Reddit, GitHub) for evidence
that supports or contradicts user preferences. Uses LLM stance detection
to classify findings, stores evidence, and recalculates confidence scores.
Fires PREFERENCE_CHALLENGED events when confidence drops significantly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import litellm
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.config import Settings
from life_graph.core.budget import BudgetCategory
from life_graph.core.events import EventType, event_bus
from life_graph.models.db import Evidence, Preference, ResearchRun
from life_graph.services.evidence_store import EvidenceStore
from life_graph.services.governor import governor
from life_graph.services.multi_model_advisor import MultiModelAdvisor
from life_graph.services.preference_store import PreferenceStore

logger = logging.getLogger(__name__)


# Source credibility multipliers (higher = more trustworthy)
SOURCE_CREDIBILITY: dict[str, float] = {
    "benchmark": 1.2,
    "paper": 1.1,
    "article": 1.0,
    "hn_discussion": 0.95,
    "blog": 0.9,
    "github_trend": 0.85,
    "reddit": 0.8,
    "ai_opinion": 0.7,
}


class ResearchEngine:
    """Autonomous research engine that validates preferences against external sources.

    Searches HN Algolia, Reddit, and GitHub for evidence, classifies stance
    using LLM, and updates preference confidence accordingly.
    """

    # ── Constants ─────────────────────────────────────────────
    STALE_THRESHOLD_DAYS: int = 30
    MAX_PREFERENCES_PER_RUN: int = 5
    MONTHLY_BUDGET_USD: float = 0.60
    CONFIDENCE_ALERT_THRESHOLD: float = 0.7

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        preference_store: PreferenceStore,
        evidence_store: EvidenceStore,
        advisor: MultiModelAdvisor,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._preference_store = preference_store
        self._evidence_store = evidence_store
        self._advisor = advisor
        self._settings = settings

        # Override constants from settings if provided
        self.STALE_THRESHOLD_DAYS = settings.research_stale_days
        self.MAX_PREFERENCES_PER_RUN = settings.research_max_per_run
        self.MONTHLY_BUDGET_USD = settings.research_monthly_budget_usd
        self.CONFIDENCE_ALERT_THRESHOLD = settings.research_confidence_threshold

    # ── Public API ────────────────────────────────────────────

    async def run_research_cycle(
        self,
        tenant_id: str,
        preference_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Execute a full research cycle for a tenant.

        Creates a ResearchRun record, finds stale preferences (or a specific
        one), checks monthly budget, researches each, fires events, and
        completes the run.

        Args:
            tenant_id: The tenant to run research for.
            preference_id: If provided, research only this preference.

        Returns:
            Summary dict with run_id, preferences_researched, evidence_found.
        """
        # Governor budget gate (primary) — research is low-priority autonomous
        # spend, throttled first when the global monthly budget runs low.
        decision = await governor.authorize(
            tenant_id, BudgetCategory.RESEARCH,
            estimated_usd=self.MONTHLY_BUDGET_USD / max(1, self.MAX_PREFERENCES_PER_RUN),
        )
        if not decision.allowed:
            logger.info("Research denied by Governor for %s: %s", tenant_id, decision.reason)
            return {"status": "budget_exhausted", "reason": decision.reason}

        # Secondary per-topic research budget guard.
        budget_remaining = await self._check_budget(tenant_id)
        if budget_remaining <= 0:
            logger.info(
                "Monthly research budget exhausted for tenant %s", tenant_id
            )
            return {"status": "budget_exhausted", "budget_remaining": 0.0}

        # Find preferences to research
        if preference_id:
            pref = await self._preference_store.get(tenant_id, preference_id)
            preferences = [pref] if pref else []
        else:
            preferences = await self._preference_store.get_stale(
                tenant_id, stale_days=self.STALE_THRESHOLD_DAYS
            )
            preferences = preferences[: self.MAX_PREFERENCES_PER_RUN]

        if not preferences:
            logger.info("No stale preferences to research for tenant %s", tenant_id)
            return {"status": "no_stale_preferences", "preferences_researched": 0}

        # Create research run record
        run_id = uuid.uuid4()
        async with self._session_factory() as session:
            run = ResearchRun(
                id=run_id,
                tenant_id=tenant_id,
                query=", ".join(p.topic for p in preferences),
                status="running",
            )
            session.add(run)
            await session.commit()

        # Research each preference
        total_evidence_found = 0
        total_evidence_added = 0
        preferences_affected: list[str] = []
        sources_searched: list[str] = []

        for pref in preferences:
            try:
                result = await self._research_preference(
                    tenant_id, pref, run_id
                )
                total_evidence_found += result.get("evidence_found", 0)
                total_evidence_added += result.get("evidence_added", 0)
                if result.get("evidence_added", 0) > 0:
                    preferences_affected.append(str(pref.id))
                sources_searched.extend(result.get("sources", []))
            except Exception:
                logger.exception(
                    "Failed to research preference %s", pref.id
                )

        # Complete the run
        async with self._session_factory() as session:
            await session.execute(
                update(ResearchRun)
                .where(ResearchRun.id == run_id)
                .values(
                    status="completed",
                    evidence_found=total_evidence_found,
                    evidence_added=total_evidence_added,
                    preferences_affected=preferences_affected,
                    sources_searched=list(set(sources_searched)),
                    completed_at=datetime.now(UTC),
                )
            )
            await session.commit()

        # Fire research completed event
        await event_bus.emit(
            EventType.RESEARCH_COMPLETED,
            {
                "run_id": str(run_id),
                "tenant_id": tenant_id,
                "preferences_researched": len(preferences),
                "evidence_found": total_evidence_found,
                "evidence_added": total_evidence_added,
            },
            source="research_engine",
        )

        logger.info(
            "Research cycle complete: run=%s, prefs=%d, evidence_found=%d, added=%d",
            run_id, len(preferences), total_evidence_found, total_evidence_added,
        )

        return {
            "status": "completed",
            "run_id": str(run_id),
            "preferences_researched": len(preferences),
            "evidence_found": total_evidence_found,
            "evidence_added": total_evidence_added,
        }

    # ── Internal: Research a Single Preference ───────────────

    async def _research_preference(
        self,
        tenant_id: str,
        preference: Preference,
        run_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Research a single preference: build query, fetch sources, detect stance, store evidence.

        Returns:
            Dict with evidence_found, evidence_added, sources.
        """
        # Build search query from preference
        query = f"{preference.topic} {preference.choice}"
        if preference.reason:
            query += f" {preference.reason}"

        # Fetch from all sources concurrently
        articles = await self._fetch_from_sources(query)

        evidence_found = len(articles)
        evidence_added = 0
        sources: list[str] = []

        for article in articles:
            try:
                # Detect stance using LLM
                stance_result = await self._detect_stance(preference, article)
                if stance_result is None:
                    continue

                stance = stance_result["stance"]
                strength = stance_result["strength"]
                source_type = article["source_type"]
                sources.append(source_type)

                # Store evidence
                credibility = SOURCE_CREDIBILITY.get(source_type, 1.0)
                await self._evidence_store.create(
                    tenant_id,
                    {
                        "preference_id": str(preference.id),
                        "source_type": source_type,
                        "source_url": article.get("url"),
                        "source_title": article.get("title"),
                        "stance": stance,
                        "summary": article.get("summary", ""),
                        "raw_content": article.get("content", ""),
                        "properties": {
                            "research_run_id": str(run_id),
                            "strength": strength,
                            "auto_detected": True,
                        },
                    },
                )
                evidence_added += 1

            except ValueError as exc:
                # Dedup violation or preference not found — skip
                logger.debug("Skipping evidence: %s", exc)
            except Exception:
                logger.exception("Failed to process article: %s", article.get("title"))

        # Recalculate confidence if evidence was added
        if evidence_added > 0:
            old_confidence = preference.confidence
            await self._recalculate_confidence(tenant_id, preference.id)

            # Refresh preference to get new confidence
            updated_pref = await self._preference_store.get(tenant_id, preference.id)
            if updated_pref:
                new_confidence = updated_pref.confidence
                if new_confidence < self.CONFIDENCE_ALERT_THRESHOLD and old_confidence >= self.CONFIDENCE_ALERT_THRESHOLD:
                    await self._fire_challenge_alert(
                        tenant_id, preference, old_confidence, new_confidence
                    )

        return {
            "evidence_found": evidence_found,
            "evidence_added": evidence_added,
            "sources": sources,
        }

    # ── Internal: Fetch from External Sources ────────────────

    async def _fetch_from_sources(self, query: str) -> list[dict[str, Any]]:
        """Fetch articles from HN, Reddit, and GitHub concurrently.

        One source failing does not kill the whole run.
        Uses httpx with 10s timeout.
        """
        results: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [
                self._fetch_hn(client, query),
                self._fetch_reddit(client, query),
                self._fetch_github(client, query),
            ]
            source_results = await asyncio.gather(*tasks, return_exceptions=True)

            for source_result in source_results:
                if isinstance(source_result, Exception):
                    logger.warning("Source fetch failed: %s", source_result)
                    continue
                results.extend(source_result)

        return results

    async def _fetch_hn(
        self, client: httpx.AsyncClient, query: str
    ) -> list[dict[str, Any]]:
        """Fetch from HN Algolia API."""
        url = "https://hn.algolia.com/api/v1/search"
        params = {"query": query, "tags": "story", "hitsPerPage": 5}

        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        articles = []
        for hit in data.get("hits", []):
            articles.append({
                "title": hit.get("title", ""),
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "content": f"{hit.get('title', '')}. {hit.get('story_text', '') or ''}".strip(),
                "summary": hit.get("title", ""),
                "source_type": "hn_discussion",
                "points": hit.get("points", 0),
            })
        return articles

    async def _fetch_reddit(
        self, client: httpx.AsyncClient, query: str
    ) -> list[dict[str, Any]]:
        """Fetch from Reddit JSON API."""
        url = "https://www.reddit.com/r/python/search.json"
        params = {"q": query, "sort": "new", "limit": 5, "t": "year"}
        headers = {"User-Agent": "LifeGraph/1.0 (research-engine)"}

        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        articles = []
        for post in data.get("data", {}).get("children", []):
            pd = post.get("data", {})
            articles.append({
                "title": pd.get("title", ""),
                "url": f"https://reddit.com{pd.get('permalink', '')}",
                "content": f"{pd.get('title', '')}. {pd.get('selftext', '')[:500]}".strip(),
                "summary": pd.get("title", ""),
                "source_type": "reddit",
                "score": pd.get("score", 0),
            })
        return articles

    async def _fetch_github(
        self, client: httpx.AsyncClient, query: str
    ) -> list[dict[str, Any]]:
        """Fetch from GitHub search API."""
        url = "https://api.github.com/search/repositories"
        params = {"q": query, "sort": "stars", "per_page": 5}

        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        articles = []
        for repo in data.get("items", []):
            articles.append({
                "title": repo.get("full_name", ""),
                "url": repo.get("html_url", ""),
                "content": f"{repo.get('full_name', '')}: {repo.get('description', '') or ''}".strip(),
                "summary": repo.get("description", "") or repo.get("full_name", ""),
                "source_type": "github_trend",
                "stars": repo.get("stargazers_count", 0),
            })
        return articles

    # ── Internal: Stance Detection ───────────────────────────

    async def _detect_stance(
        self,
        preference: Preference,
        article: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Use LLM (gpt-4o-mini via litellm) to classify article stance.

        Returns:
            Dict with 'stance' (supports/contradicts/neutral) and 'strength' (0-1),
            or None if classification fails.
        """
        article_content = article.get("content", "") or article.get("summary", "")
        if not article_content:
            return None

        system_prompt = (
            "You are a stance classifier. Given a user preference and an article, "
            "determine if the article supports, contradicts, or is neutral to the preference.\n\n"
            "Respond with JSON only:\n"
            '{"stance": "supports" | "contradicts" | "neutral", "strength": 0.0-1.0, "reasoning": "..."}'
        )

        user_prompt = (
            f"Preference: {preference.topic} → {preference.choice}\n"
            f"Reason: {preference.reason or 'None given'}\n\n"
            f"Article title: {article.get('title', '')}\n"
            f"Article content: {article_content[:1000]}"
        )

        try:
            response = await asyncio.wait_for(
                litellm.acompletion(
                    model="openrouter/openai/gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    api_key=self._advisor._api_key,
                    api_base=self._advisor._api_base,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                ),
                timeout=10,
            )
        except (TimeoutError, Exception) as exc:
            logger.warning("Stance detection failed: %s", exc)
            return None

        content = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from stance detection: %s", content[:200])
            return None

        stance = parsed.get("stance", "neutral")
        if stance not in ("supports", "contradicts", "neutral"):
            stance = "neutral"

        strength = float(parsed.get("strength", 0.5))
        strength = max(0.0, min(1.0, strength))

        return {"stance": stance, "strength": strength}

    # ── Internal: Recalculate Confidence ─────────────────────

    async def _recalculate_confidence(
        self,
        tenant_id: str,
        preference_id: uuid.UUID,
    ) -> None:
        """Recalculate preference confidence from all active evidence.

        Formula: new_confidence = clamp(
            base + (sum_supporting*credibility - sum_contradicting*credibility) * 0.1,
            0.1, 1.0
        )
        """
        async with self._session_factory() as session:
            pref = await session.get(Preference, preference_id)
            if pref is None:
                return

            result = await session.execute(
                select(Evidence)
                .where(Evidence.preference_id == preference_id)
                .where(Evidence.status == "active")
            )
            items = list(result.scalars().all())

            if not items:
                return

            sum_supporting = sum(
                e.credibility * e.weight
                for e in items if e.stance == "supports"
            )
            sum_contradicting = sum(
                e.credibility * e.weight
                for e in items if e.stance == "contradicts"
            )

            base = pref.confidence
            new_confidence = base + (sum_supporting - sum_contradicting) * 0.1
            new_confidence = max(0.1, min(1.0, new_confidence))

            # Update confidence and history
            history = list(pref.confidence_history or [])
            history.append({
                "value": new_confidence,
                "at": datetime.now(UTC).isoformat(),
                "reason": "research_recalc",
            })
            pref.confidence = new_confidence
            pref.confidence_history = history
            pref.last_validated_at = datetime.now(UTC)
            pref.updated_at = datetime.now(UTC)
            await session.commit()

    # ── Internal: Budget Check ───────────────────────────────

    async def _check_budget(self, tenant_id: str) -> float:
        """Check monthly research budget remaining.

        Sums cost from completed research runs this calendar month.

        Returns:
            Remaining budget in USD.
        """
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count(ResearchRun.id))
                .where(ResearchRun.tenant_id == tenant_id)
                .where(ResearchRun.status == "completed")
                .where(ResearchRun.started_at >= month_start)
            )
            completed_runs = result.scalar() or 0

        # Estimate cost: each run ~= $0.01 (LLM stance detection calls)
        estimated_cost = completed_runs * 0.01
        remaining = self.MONTHLY_BUDGET_USD - estimated_cost
        return remaining

    # ── Internal: Challenge Alert ────────────────────────────

    async def _fire_challenge_alert(
        self,
        tenant_id: str,
        preference: Preference,
        old_confidence: float,
        new_confidence: float,
    ) -> None:
        """Fire PREFERENCE_CHALLENGED event when confidence drops below threshold."""
        await event_bus.emit(
            EventType.PREFERENCE_CHALLENGED,
            {
                "tenant_id": tenant_id,
                "preference_id": str(preference.id),
                "topic": preference.topic,
                "choice": preference.choice,
                "old_confidence": old_confidence,
                "new_confidence": new_confidence,
                "threshold": self.CONFIDENCE_ALERT_THRESHOLD,
            },
            source="research_engine",
        )
        logger.warning(
            "Preference challenged: %s (%s → %s) — confidence dropped %.2f → %.2f",
            preference.id, preference.topic, preference.choice,
            old_confidence, new_confidence,
        )

        # Update last_challenged_at
        async with self._session_factory() as session:
            await session.execute(
                update(Preference)
                .where(Preference.id == preference.id)
                .values(last_challenged_at=datetime.now(UTC))
            )
            await session.commit()
