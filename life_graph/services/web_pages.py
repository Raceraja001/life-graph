"""Search, pick the pages not read yet, fetch their text — in plain code.

Shared by the jobs that read the web for the owner (Job 1 free LLM offers,
Job 6 research, Job 10 tech watch; docs/design/11_persona_roster_plan.md).
A worker never browses: these functions decide what is read and fetch it
through the safe fetcher, and the worker only reads what it is handed, so
every source it may cite is known before it runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

PAGE_CHARS = 12_000
SEEN_TTL = 30 * 86_400


@dataclass(frozen=True)
class Hit:
    url: str
    title: str


async def seen(key: str) -> tuple[Any, set[str]]:
    """(redis, the URLs already read under *key*); (None, empty) without Redis."""
    from life_graph.storage.redis import get_redis

    redis = get_redis()
    if redis is None:
        return None, set()
    try:
        return redis, set(await redis.smembers(key))
    except Exception:  # noqa: BLE001
        return None, set()


async def mark_seen(redis: Any, key: str, urls: list[str], ttl: int = SEEN_TTL) -> None:
    if redis is None or not urls:
        return
    try:
        await redis.sadd(key, *urls)
        await redis.expire(key, ttl)
    except Exception:  # noqa: BLE001
        logger.debug("could not record seen pages under %s", key, exc_info=True)


async def candidates(
    queries: list[str],
    *,
    limit: int,
    skip: set[str] = frozenset(),
    spread: bool = False,
    per_host: int = 2,
) -> list[Hit]:
    """Result pages for *queries*, in order, without duplicates or URLs in
    *skip* (normalised, see services/sources.normalise), at most *limit*.

    *spread* takes one result from each query in turn and at most *per_host*
    pages per site: the first feature-watch run let one release tracker and the
    first query (ChatGPT) fill all six pages, so Claude and Gemini got none.
    """
    from urllib.parse import urlsplit

    from life_graph.services.sources import normalise
    from life_graph.tools.web_search import search

    picked: list[Hit] = []
    # The seen sets hold URLs as fetched; compare like with like (Job 1's
    # first version compared a normalised key with raw URLs, so nothing read
    # was ever skipped).
    keys: set[str] = {normalise(u) for u in skip}

    def fresh(result: dict) -> Hit | None:
        url = str(result.get("url") or "").strip()
        key = normalise(url) if url else ""
        if not url.startswith("http") or key in keys:
            return None
        keys.add(key)
        return Hit(url=url, title=str(result.get("title") or "").strip()[:200])

    if not spread:
        for query in queries:
            found = await search(query)
            for result in found.get("results") or []:
                hit = fresh(result)
                if hit:
                    picked.append(hit)
                    if len(picked) >= limit:
                        return picked
        return picked

    lists = [list((await search(q)).get("results") or []) for q in queries]
    hosts: dict[str, int] = {}
    for depth in range(max((len(x) for x in lists), default=0)):
        for results in lists:
            if depth >= len(results):
                continue
            host = (urlsplit(str(results[depth].get("url") or "")).hostname or "").lower()
            if hosts.get(host, 0) >= per_host:
                continue
            hit = fresh(results[depth])
            if hit:
                hosts[host] = hosts.get(host, 0) + 1
                picked.append(hit)
                if len(picked) >= limit:
                    return picked
    return picked


async def read(urls: list[str], chars: int = PAGE_CHARS) -> dict[str, str]:
    """The readable text of each page that could be fetched (url -> text)."""
    from life_graph.services import safe_fetch
    from life_graph.tools.browser import page_text

    pages: dict[str, str] = {}
    for url in urls:
        try:
            page = await safe_fetch.fetch(url)
        except Exception as exc:  # noqa: BLE001 - one unreadable page skips that page
            logger.info("page %s skipped: %s", url, exc)
            continue
        text = page_text(page.text)[:chars]
        if text.strip():
            pages[url] = text
    return pages


def as_inputs(pages: list[tuple[str, str]]) -> str:
    """Pages as a worker reads them: each starts with 'SOURCE: <url>'."""
    return "\n\n".join(f"SOURCE: {url}\n{text}" for url, text in pages)
