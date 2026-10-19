"""Browser tool — simple page fetching, through the safe fetcher.

Interactive browsing (navigate, click, fill forms) is provided by the
bridged Playwright MCP server (see services/mcp_bridge.py), not a
native tool here — see docs/superpowers/specs/2026-08-09-playwright-mcp-wiring.md
for why the earlier `browser_agent` (a nested browser-use agent loop)
was removed in favor of that.

The URL comes from model output, so the fetch goes through
services/safe_fetch.py: no private-network addresses, every redirect hop
checked, the body capped.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from life_graph.services.safe_fetch import FetchBlockedError, fetch
from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 6000
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HREF = re.compile(r'href=["\']([^"\']+)["\']')
_SCRIPTS = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")


def page_text(markup: str) -> str:
    """Readable text of an HTML page: scripts and styles dropped, tags stripped."""
    import html

    clean = _SCRIPTS.sub(" ", markup)
    clean = _TAGS.sub(" ", clean)
    return re.sub(r"\s+", " ", html.unescape(clean)).strip()


@tool(
    name="browse_web",
    description=(
        "Browse a web page and extract its text content. "
        "Use for: reading documentation, checking release notes, "
        "scraping articles, checking GitHub repos. "
        "Returns the page text content (no JavaScript execution). "
        "Private and local network addresses cannot be fetched."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to browse.",
            },
            "extract": {
                "type": "string",
                "description": "What to extract: 'text' (full page text), "
                "'title' (page title only), 'links' (all links). Default: 'text'.",
            },
        },
        "required": ["url"],
    },
)
async def browse_web(url: str, extract: str = "text") -> str:
    """Fetch a web page and extract its title, links or text (JSON)."""
    try:
        page = await fetch(url)
    except FetchBlockedError as exc:
        return json.dumps({"error": f"Not fetched: {exc}", "url": url})
    except httpx.HTTPStatusError as exc:
        return json.dumps({"error": f"HTTP {exc.response.status_code}: {url}"})
    except httpx.ConnectError:
        return json.dumps({"error": f"Could not connect to {url}"})
    except Exception as exc:
        logger.exception("Browse failed for %s", url)
        return json.dumps({"error": f"Browse failed: {exc}"})

    if extract == "title":
        m = _TITLE.search(page.text)
        return json.dumps({"url": page.url, "title": m.group(1).strip() if m else "No title found"})
    if extract == "links":
        links = _HREF.findall(page.text)
        return json.dumps({"url": page.url, "links": links[:50], "total": len(links)})

    clean = page_text(page.text)
    if len(clean) > MAX_TEXT_CHARS:
        clean = clean[:MAX_TEXT_CHARS] + f"\n\n[... truncated, {len(clean)} total chars]"
    return json.dumps(
        {"url": page.url, "content_type": page.content_type, "text": clean, "length": len(clean)}
    )
