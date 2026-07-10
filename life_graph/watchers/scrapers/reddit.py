"""Reddit JSON API scraper for tech subreddits."""

from __future__ import annotations

import httpx

DEFAULT_SUBREDDITS = [
    "programming", "python", "javascript", "devops", "machinelearning",
]
USER_AGENT = "LifeGraph-TechRadar/1.0 (ambient AI watcher)"


async def scrape_subreddit(subreddit: str, limit: int = 25) -> list[dict]:
    """Fetch hot posts from a subreddit using Reddit's JSON API.

    Returns list of ``{"title", "url", "source_id", "upvotes", "comments", "subreddit"}``.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://www.reddit.com/r/{subreddit}/hot.json",
                params={"limit": limit, "raw_json": 1},
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])
            return [
                {
                    "title": p["data"].get("title", ""),
                    "url": p["data"].get("url", ""),
                    "source_id": p["data"].get("id", ""),
                    "upvotes": p["data"].get("ups", 0) or 0,
                    "comments": p["data"].get("num_comments", 0) or 0,
                    "subreddit": subreddit,
                }
                for p in posts
                if p.get("kind") == "t3" and p["data"].get("title")
            ]
    except (httpx.HTTPError, Exception):
        return []


async def scrape_tech_subreddits(
    subreddits: list[str] | None = None,
    limit: int = 25,
) -> list[dict]:
    """Scrape multiple tech subreddits and combine results."""
    subs = subreddits or DEFAULT_SUBREDDITS
    all_posts: list[dict] = []
    for sub in subs:
        posts = await scrape_subreddit(sub, limit=limit)
        all_posts.extend(posts)
    return all_posts
