"""Browser tool — simple page fetching via httpx.

Interactive browsing (navigate, click, fill forms) is provided by the
bridged Playwright MCP server (see services/mcp_bridge.py), not a
native tool here — see docs/superpowers/specs/2026-08-09-playwright-mcp-wiring.md
for why the earlier `browser_agent` (a nested browser-use agent loop)
was removed in favor of that.
"""

from __future__ import annotations

import json
import logging

import httpx

from life_graph.tools.registry import tool

logger = logging.getLogger(__name__)


@tool(
    name="browse_web",
    description=(
        "Browse a web page and extract its text content. "
        "Use for: reading documentation, checking release notes, "
        "scraping articles, checking GitHub repos. "
        "Returns the page text content (no JavaScript execution)."
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
    """Fetch a web page and extract content.

    Uses httpx for simple fetching — no JavaScript execution. For
    JavaScript-heavy pages or interactive tasks (navigate, click, fill
    forms), use the bridged Playwright MCP tools instead.

    Args:
        url: The URL to fetch.
        extract: What to extract from the page.

    Returns:
        JSON string with the extracted content.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={"User-Agent": "LifeGraph-Agent/1.0"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        text = resp.text

        if extract == "title":
            # Simple title extraction
            import re
            title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
            return json.dumps({
                "url": url,
                "title": title_match.group(1).strip() if title_match else "No title found",
            })

        if extract == "links":
            import re
            links = re.findall(r'href=["\']([^"\']+)["\']', text)
            return json.dumps({
                "url": url,
                "links": links[:50],  # Cap at 50 links
                "total": len(links),
            })

        # Default: extract text content
        # Strip HTML tags for a cleaner result
        import re
        # Remove script and style blocks
        clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", " ", clean)
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()

        # Truncate to reasonable size
        max_chars = 6000
        if len(clean) > max_chars:
            clean = clean[:max_chars] + f"\n\n[... truncated, {len(clean)} total chars]"

        return json.dumps({
            "url": url,
            "content_type": content_type,
            "text": clean,
            "length": len(clean),
        })

    except httpx.HTTPStatusError as exc:
        return json.dumps({"error": f"HTTP {exc.response.status_code}: {url}"})
    except httpx.ConnectError:
        return json.dumps({"error": f"Could not connect to {url}"})
    except Exception as exc:
        logger.exception("Browse failed for %s", url)
        return json.dumps({"error": f"Browse failed: {exc}"})
