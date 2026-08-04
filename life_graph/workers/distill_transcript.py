"""ARQ job: distill one external transcript session for one tenant.

Mirrors distill_conversation — set tenant context, build the service from DI,
run it. Backfill throttling is emergent (worker concurrency + ingest debounce
+ ResilientLLM free-model cooldowns), so no dedicated rate limiter here.
"""

from __future__ import annotations

import logging

from life_graph.core.tenant import set_tenant_context

logger = logging.getLogger(__name__)

DISTILL_TRANSCRIPT_JOB = "life_graph.workers.distill_transcript.distill_transcript"


async def distill_transcript(ctx: dict, session_id: str, tenant_id: str) -> dict:
    """Distill a single external session for one tenant."""
    set_tenant_context(tenant_id, "system")

    from life_graph.api.dependencies import get_transcript_distiller

    distiller = get_transcript_distiller()
    result = await distiller.distill(session_id)
    logger.info("Distilled transcript %s: %s", session_id, result)
    return result
