"""Reject outbound URLs that point at the private network (audit 2026-11-19, M6).

Tenant webhooks and webhook notification channels make the server POST to a
URL the caller chose. Without a check, that URL can be ``http://127.0.0.1``,
a LAN admin page or the cloud metadata address. The rule is the one
``services/safe_fetch.check_url`` already applies to model-chosen URLs:
http(s) only, and every resolved address public unless the host is listed in
``LIFE_GRAPH_FETCH_ALLOW_HOSTS``.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from life_graph.services.safe_fetch import FetchBlockedError, check_url

logger = logging.getLogger(__name__)


async def require_public_url(url: str, field: str = "url") -> None:
    """Raise 422 unless the server may send requests to ``url``.

    The detail is fixed: check_url's own message names the private address a
    host resolved to, which would turn this into an internal-DNS oracle.
    """
    try:
        await check_url(url)
    except FetchBlockedError as exc:
        logger.info("Rejected outbound %s %r: %s", field, url, exc)
        raise HTTPException(
            status_code=422,
            detail=(
                f"{field} must be a public http(s) address "
                "(or a host listed in LIFE_GRAPH_FETCH_ALLOW_HOSTS)"
            ),
        ) from exc
