"""PyPI package version checker."""

from __future__ import annotations

import httpx


async def check_pypi_version(package: str) -> dict | None:
    """Check PyPI for the latest version of a package.

    Returns ``{"name": ..., "version": ..., "summary": ...}`` or *None* on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://pypi.org/pypi/{package}/json")
            if resp.status_code != 200:
                return None
            data = resp.json()
            info = data.get("info", {})
            return {
                "name": package,
                "version": info.get("version", "unknown"),
                "summary": info.get("summary", ""),
            }
    except (httpx.HTTPError, Exception):
        return None
