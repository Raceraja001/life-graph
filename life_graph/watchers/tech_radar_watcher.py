"""Era 6 — Tech Radar Watcher.

Scrapes HN, Reddit, and GitHub trending in parallel, scores articles
0-100 based on tech relevance, deduplicates by URL, and builds a daily digest.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from life_graph.watchers.base import BaseWatcher, Severity
from life_graph.watchers.models import TechRadarItem
from life_graph.watchers.scrapers.github_trending import scrape_github_trending
from life_graph.watchers.scrapers.hackernews import scrape_hn_front_page
from life_graph.watchers.scrapers.reddit import scrape_tech_subreddits

logger = logging.getLogger(__name__)

# Keywords that boost tech-relevance score
TECH_KEYWORDS = frozenset({
    "python", "rust", "go", "javascript", "typescript", "react",
    "ai", "ml", "llm", "gpt", "transformer", "neural", "deep learning",
    "kubernetes", "docker", "devops", "ci/cd", "cloud",
    "api", "microservice", "serverless", "database", "sql", "nosql",
    "security", "vulnerability", "cve", "exploit",
    "open source", "github", "framework", "library",
    "performance", "benchmark", "optimization",
    "web", "backend", "frontend", "fullstack",
    "startup", "funding", "acquisition",
    "linux", "windows", "macos",
    "fastapi", "django", "flask", "nextjs", "vue", "svelte",
    "postgresql", "redis", "mongodb", "kafka",
    "aws", "gcp", "azure",
    "wasm", "webassembly", "edge computing",
    "blockchain", "crypto", "web3",
    "robotics", "iot", "embedded",
    "compiler", "interpreter", "language design",
})

# Source credibility bonuses
SOURCE_CREDIBILITY: dict[str, int] = {
    "hn": 5,
    "github_trending": 3,
    "reddit": 0,
}


def _count_keyword_matches(text_str: str, max_score: int, per_hit: int) -> int:
    """Count keyword matches in text and return capped score."""
    if not text_str:
        return 0
    text_lower = text_str.lower()
    score = 0
    for kw in TECH_KEYWORDS:
        if kw in text_lower:
            score += per_hit
            if score >= max_score:
                return max_score
    return score


def _log_scale(value: int, max_score: int) -> int:
    """Log-scaled score component."""
    if value <= 0:
        return 0
    return min(int(math.log2(value + 1) * (max_score / 10)), max_score)


def score_article(article: dict, source: str) -> int:
    """Score an article 0-100 based on relevance criteria.

    Components:
    - Keyword match in title: +15 per hit, max 45
    - Keyword in description: +8 per hit, max 24
    - Engagement bonus: log-scaled upvotes, max 20
    - Comment bonus: log-scaled comments, max 11
    - Source credibility: HN +5, GitHub +3
    """
    title = article.get("title", "")
    description = article.get("description", "") or article.get("summary", "")
    upvotes = article.get("upvotes", 0) or 0
    comments = article.get("comments", 0) or 0

    score = 0
    score += _count_keyword_matches(title, max_score=45, per_hit=15)
    score += _count_keyword_matches(description, max_score=24, per_hit=8)
    score += _log_scale(upvotes, max_score=20)
    score += _log_scale(comments, max_score=11)
    score += SOURCE_CREDIBILITY.get(source, 0)

    return min(score, 100)


def _extract_tags(title: str, description: str = "") -> list[str]:
    """Extract matching tech keyword tags from title and description."""
    combined = (title + " " + description).lower()
    return sorted({kw for kw in TECH_KEYWORDS if kw in combined})


class TechRadarWatcher(BaseWatcher):
    """Scrapes tech news sources and builds a scored daily digest."""

    name = "tech_radar"
    display_name = "Tech Radar"
    default_schedule = "0 7 * * *"  # Daily at 7 AM

    async def execute(self) -> None:
        # ── Scrape all sources in parallel ────────────────────
        hn_task = asyncio.create_task(scrape_hn_front_page(limit=30))
        reddit_task = asyncio.create_task(scrape_tech_subreddits())
        github_task = asyncio.create_task(scrape_github_trending(days=1, limit=30))

        results = await asyncio.gather(
            hn_task, reddit_task, github_task,
            return_exceptions=True,
        )

        hn_articles: list[dict] = results[0] if not isinstance(results[0], Exception) else []
        reddit_articles: list[dict] = results[1] if not isinstance(results[1], Exception) else []
        github_articles: list[dict] = results[2] if not isinstance(results[2], Exception) else []

        if isinstance(results[0], Exception):
            self.logger.warning("HN scrape failed: %s", results[0])
        if isinstance(results[1], Exception):
            self.logger.warning("Reddit scrape failed: %s", results[1])
        if isinstance(results[2], Exception):
            self.logger.warning("GitHub scrape failed: %s", results[2])

        # ── Tag each article with source ──────────────────────
        all_articles: list[tuple[dict, str]] = []
        for a in hn_articles:
            all_articles.append((a, "hn"))
        for a in reddit_articles:
            all_articles.append((a, "reddit"))
        for a in github_articles:
            all_articles.append((a, "github_trending"))

        self.logger.info(
            "Scraped %d HN, %d Reddit, %d GitHub articles",
            len(hn_articles), len(reddit_articles), len(github_articles),
        )

        # ── Score and filter ──────────────────────────────────
        scored: list[dict[str, Any]] = []
        for article, source in all_articles:
            url = article.get("url", "")
            if not url:
                continue

            article_score = score_article(article, source)
            if article_score <= 60:
                continue

            tags = _extract_tags(
                article.get("title", ""),
                article.get("description", ""),
            )

            scored.append({
                "tenant_id": self.tenant_id,
                "title": article.get("title", "")[:500],
                "url": url[:2000],
                "source": source,
                "source_id": article.get("source_id"),
                "subreddit": article.get("subreddit"),
                "score": article_score,
                "upvotes": article.get("upvotes", 0) or 0,
                "comments": article.get("comments", 0) or 0,
                "summary": (
                    (article.get("description") or article.get("summary", ""))[:1000]
                    or None
                ),
                "tags": tags,
            })

        self.logger.info("%d articles scored > 60", len(scored))

        # ── Upsert into tech_radar (ON CONFLICT DO NOTHING) ──
        inserted_count = 0
        if scored:
            async with self.session_factory() as session:
                for item in scored:
                    stmt = (
                        pg_insert(TechRadarItem)
                        .values(**item)
                        .on_conflict_do_nothing(
                            index_elements=["tenant_id", "url"],
                        )
                    )
                    result = await session.execute(stmt)
                    if result.rowcount > 0:
                        inserted_count += 1
                await session.commit()

        # ── Build daily digest summary ────────────────────────
        source_counts: dict[str, int] = {}
        for item in scored:
            src = item["source"]
            source_counts[src] = source_counts.get(src, 0) + 1

        top_articles = sorted(scored, key=lambda x: x["score"], reverse=True)[:10]

        digest_lines = [
            f"📡 Tech Radar Daily Digest — {len(scored)} articles scored > 60",
            f"   Sources: {source_counts}",
            f"   New articles inserted: {inserted_count}",
            "",
        ]
        for i, a in enumerate(top_articles, 1):
            digest_lines.append(
                f"   {i}. [{a['score']}] {a['title'][:80]} ({a['source']})"
            )

        digest_text = "\n".join(digest_lines)

        self.emit_event(
            severity=Severity.INFO,
            title="Tech Radar Daily Digest",
            details={
                "total_scraped": len(all_articles),
                "total_scored": len(scored),
                "inserted": inserted_count,
                "source_counts": source_counts,
                "top_articles": [
                    {"title": a["title"][:100], "score": a["score"], "url": a["url"]}
                    for a in top_articles
                ],
            },
            summary=digest_text,
        )
