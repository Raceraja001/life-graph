"""Web search tool: SearXNG, Tavily or DuckDuckGo, whichever is available.

Research personas could not search at all while this needed a paid Tavily key
(the 2026-10-12 survey). Providers, tried in this order under
``web_search_provider=auto``:

1. **SearXNG** at ``searxng_url``, self-hosted, no key, many engines at once;
2. **Tavily**, when ``tavily_api_key`` is set;
3. **DuckDuckGo's HTML endpoint**, keyless, parsed from markup, so it is the
   fallback rather than the default.

A provider that fails falls through to the next one; the result names the
provider that answered, so a run can be studied later. Every result carries
its URL: research answers must cite what was actually returned
(services/sources.py).
"""

from __future__ import annotations

import html
import json
import logging
import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urlsplit

import httpx

from life_graph.config import settings
from life_graph.tools.registry import tool

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

Result = dict[str, str]


async def _searxng(query: str, http: httpx.AsyncClient) -> list[Result]:
    resp = await http.get(
        settings.searxng_url.rstrip("/") + "/search",
        params={"q": query, "format": "json", "safesearch": 1},
    )
    resp.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in resp.json().get("results", [])
        if r.get("url")
    ]


async def _tavily(query: str, http: httpx.AsyncClient) -> list[Result]:
    resp = await http.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": settings.web_search_max_results,
        },
    )
    resp.raise_for_status()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in resp.json().get("results", [])
        if r.get("url")
    ]


_DDG_RESULT = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>'
    r'(?:.*?<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>)?',
    re.DOTALL,
)
_TAG = re.compile(r"<[^>]+>")


def _ddg_url(href: str) -> str:
    """DuckDuckGo wraps result links as //duckduckgo.com/l/?uddg=<target>."""
    href = html.unescape(href)
    parts = urlsplit(href if "//" in href else "https:" + href)
    if parts.path.startswith("/l/"):
        target = parse_qs(parts.query).get("uddg", [""])[0]
        return unquote(target)
    return href if href.startswith("http") else "https:" + href


def parse_duckduckgo(markup: str) -> list[Result]:
    """Results from DuckDuckGo's HTML page (pure, so it is tested offline)."""
    out = []
    for m in _DDG_RESULT.finditer(markup):
        url = _ddg_url(m.group("href"))
        if not url.startswith("http") or "duckduckgo.com/y.js" in url:
            continue  # ads
        clean = lambda s: html.unescape(_TAG.sub("", s or "")).strip()  # noqa: E731
        out.append(
            {"title": clean(m.group("title")), "url": url, "content": clean(m.group("snippet"))}
        )
    return out


async def _duckduckgo(query: str, http: httpx.AsyncClient) -> list[Result]:
    resp = await http.post("https://html.duckduckgo.com/html/", data={"q": query})
    resp.raise_for_status()
    return parse_duckduckgo(resp.text)


PROVIDERS: dict[str, Callable[[str, httpx.AsyncClient], Awaitable[list[Result]]]] = {
    "searxng": _searxng,
    "tavily": _tavily,
    "duckduckgo": _duckduckgo,
}


def provider_order() -> list[str]:
    """Which providers to try, in order, given the settings."""
    choice = (settings.web_search_provider or "auto").strip().lower()
    if choice != "auto":
        return [choice] if choice in PROVIDERS else []
    order = []
    if settings.searxng_url:
        order.append("searxng")
    if settings.tavily_api_key:
        order.append("tavily")
    order.append("duckduckgo")
    return order


async def search(query: str, *, client: httpx.AsyncClient | None = None) -> dict:
    """Run the query through the first provider that answers."""
    order = provider_order()
    if not order:
        return {"status": "not_configured", "message": "Unknown web_search_provider."}
    errors: list[str] = []
    own = client is None
    http = client or httpx.AsyncClient(
        timeout=20.0, headers={"User-Agent": "Mozilla/5.0 (LifeGraph personal assistant)"}
    )
    try:
        for name in order:
            try:
                results = await PROVIDERS[name](query, http)
            except Exception as exc:  # noqa: BLE001 — fall through to the next provider
                logger.warning("web_search provider %s failed: %s", name, exc)
                errors.append(f"{name}: {type(exc).__name__}")
                continue
            if results:
                return {
                    "status": "ok",
                    "provider": name,
                    "query": query,
                    "results": results[: settings.web_search_max_results],
                }
            errors.append(f"{name}: no results")
    finally:
        if own:
            await http.aclose()
    return {"status": "error", "query": query, "message": "No provider answered.", "tried": errors}


@tool(
    name="web_search",
    description=(
        "Search the web for current information. Returns titles, URLs and "
        "snippets; cite the URLs you rely on."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
        },
        "required": ["query"],
    },
)
async def web_search(query: str) -> str:
    """Search the web; JSON with the provider used and the results."""
    logger.info("Searching web for: %s", query)
    return json.dumps(await search(query))


@tool(
    name="research_web",
    description=(
        "Research a question on the web: reads several result pages and returns an "
        "answer in short claims, each citing the pages that state it. Slower than "
        "web_search; use it for questions that need more than one page (comparisons, "
        "'what is the latest on'). Do not put personal details in the question."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question, self-contained"},
        },
        "required": ["question"],
    },
)
async def research_web(question: str) -> str:
    """Job 6 as a tool for Jarvis (services/web_research.research)."""
    from life_graph.core.tenant import get_current_tenant_id, has_tenant_context
    from life_graph.services.web_research import research
    from life_graph.services.workers import WorkerError

    tenant_id = get_current_tenant_id() if has_tenant_context() else "default"
    try:
        out = await research(question, tenant_id)
    except WorkerError as exc:
        return json.dumps({"status": "error", "message": str(exc)})
    return json.dumps(
        {
            "status": "ok",
            "answer": out["answer"],
            "sources": out["sources"],
            "pages_read": len(out["pages_read"]),
        }
    )
