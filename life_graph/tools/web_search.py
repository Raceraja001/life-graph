"""Web search tool using the Tavily API.

Falls back to a helpful message when the TAVILY_API_KEY environment
variable is not configured.
"""

from __future__ import annotations

import json
import logging

import httpx

from life_graph.tools.registry import tool
from life_graph.config import Settings

logger = logging.getLogger(__name__)


@tool(
    name="web_search",
    description="Search the web for current information",
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
    """Search the web using the Tavily API.

    Args:
        query: The search query string.

    Returns:
        JSON string with search results or a configuration message.
    """
    # NOTE: Add `tavily_api_key: str = ""` to life_graph.config.Settings
    # to enable this tool. Until then, getattr() safely returns None.
    api_key = getattr(Settings(), "tavily_api_key", None)

    if not api_key:
        logger.info("Web search skipped — TAVILY_API_KEY not set")
        return json.dumps({
            "status": "not_configured",
            "message": (
                "Web search is not configured. "
                "Set the TAVILY_API_KEY environment variable "
                "to enable web search."
            ),
        })

    logger.info("Searching web for: %s", query)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": 5,
                },
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            })

        logger.info("Web search returned %d results", len(results))
        return json.dumps({
            "status": "ok",
            "query": query,
            "results": results,
        })

    except httpx.TimeoutException:
        logger.warning("Web search timed out for query: %s", query)
        return json.dumps({
            "status": "error",
            "message": "Search request timed out. Please try again.",
        })

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Tavily API error: %d %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return json.dumps({
            "status": "error",
            "message": (
                f"Search API returned HTTP {exc.response.status_code}."
            ),
        })

    except Exception as exc:
        logger.exception("Unexpected web search error: %s", exc)
        return json.dumps({
            "status": "error",
            "message": f"Search failed: {type(exc).__name__}",
        })
