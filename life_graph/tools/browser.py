"""Browser tool — web browsing via browser-use.

Provides the agent with the ability to browse the web, scrape pages,
fill forms, and interact with web applications using the browser-use
library (pip install browser-use).

Falls back to simple httpx fetch if browser-use is not installed.
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

    Uses httpx for simple fetching. For JavaScript-heavy pages,
    browser-use can be integrated later.

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


@tool(
    name="browser_agent",
    description=(
        "Use an AI-controlled browser to perform complex web tasks. "
        "The browser agent can: navigate pages, fill forms, click buttons, "
        "extract structured data, and interact with web apps. "
        "Requires browser-use package (pip install browser-use). "
        "Use for: complex scraping, form submissions, multi-step web workflows."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Natural language description of what to do in the browser. "
                "Example: 'Go to github.com/trending and list the top 5 Python repos'",
            },
        },
        "required": ["task"],
    },
)
async def browser_agent(task: str) -> str:
    """Run a browser-use agent to perform a web task.

    Requires: pip install browser-use

    Args:
        task: Natural language instruction for the browser agent.

    Returns:
        JSON string with the task result.
    """
    try:
        from browser_use import Agent as BrowserAgent
        from langchain_openai import ChatOpenAI

        # Use the same LLM as the orchestrator
        llm = ChatOpenAI(model="gpt-4o-mini")
        agent = BrowserAgent(task=task, llm=llm)
        result = await agent.run()

        return json.dumps({
            "task": task,
            "result": str(result),
            "status": "completed",
        })

    except ImportError:
        return json.dumps({
            "error": "browser-use not installed. Run: pip install browser-use",
            "fallback": "Use the browse_web tool for simple page fetching.",
        })
    except Exception as exc:
        logger.exception("Browser agent failed for task: %s", task)
        return json.dumps({"error": f"Browser agent failed: {exc}"})
