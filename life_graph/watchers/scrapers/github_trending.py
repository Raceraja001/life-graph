"""GitHub trending repositories scraper via Search API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx


async def scrape_github_trending(
    language: str | None = None,
    days: int = 7,
    limit: int = 30,
) -> list[dict]:
    """Fetch trending repos from GitHub Search API.

    Returns list of ``{"title", "url", "source_id", "upvotes", "comments", "description"}``.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    query = f"created:>{since} stars:>10"
    if language:
        query += f" language:{language}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": limit,
                },
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "LifeGraph-TechRadar/1.0",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return [
                {
                    "title": repo.get("full_name", ""),
                    "url": repo.get("html_url", ""),
                    "source_id": str(repo.get("id", "")),
                    "upvotes": repo.get("stargazers_count", 0) or 0,
                    "comments": repo.get("open_issues_count", 0) or 0,
                    "description": repo.get("description", "") or "",
                }
                for repo in items
            ]
    except (httpx.HTTPError, Exception):
        return []
