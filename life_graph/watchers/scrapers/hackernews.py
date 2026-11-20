"""Hacker News front page scraper via Algolia API."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def scrape_hn_front_page(limit: int = 30) -> list[dict]:
    """Fetch top stories from HN front page.

    Returns list of ``{"title", "url", "source_id", "upvotes", "comments"}``.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={"tags": "front_page", "hitsPerPage": limit},
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            return [
                {
                    "title": h.get("title", ""),
                    "url": h.get("url", ""),
                    "source_id": str(h.get("objectID", "")),
                    "upvotes": h.get("points", 0) or 0,
                    "comments": h.get("num_comments", 0) or 0,
                }
                for h in hits
                if h.get("title")
            ]
    except Exception:  # best-effort: one source failing never stops the watch
        logger.warning("Hacker News scrape failed", exc_info=True)
        return []
