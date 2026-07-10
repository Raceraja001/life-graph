"""NPM registry package version checker."""

from __future__ import annotations

import httpx


async def check_npm_version(package: str) -> dict | None:
    """Check npm registry for the latest version of a package.

    Returns ``{"name": ..., "version": ..., "description": ...}`` or *None* on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://registry.npmjs.org/{package}/latest",
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return {
                "name": package,
                "version": data.get("version", "unknown"),
                "description": data.get("description", ""),
            }
    except (httpx.HTTPError, Exception):
        return None
