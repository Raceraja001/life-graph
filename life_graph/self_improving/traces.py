"""Record extraction calls — the self-improvement loop's training data.

Every local capture extraction is stored with its exact input and output. The
facts it produced become pending memories linked back here by
``properties.extraction_trace_id``; how the user resolves those memories
(approve / edit / reject) is the label the loop learns from.

Recording is best-effort by design: a failed insert is logged and ingestion
carries on, because losing one training example is harmless and losing a
capture is not.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def current_tenant_or_none() -> str | None:
    """The tenant in context, or None outside a request/job (no trace then)."""
    from life_graph.core.tenant import get_current_tenant_id

    try:
        return get_current_tenant_id()
    except RuntimeError:
        return None


async def record_trace(
    *,
    tenant_id: str,
    task_type: str,
    prompt_version_id: str,
    model: str,
    input_text: str,
    raw_output: str | None,
    facts: list[dict[str, Any]],
    latency_ms: int | None,
) -> uuid.UUID | None:
    """Insert one ExtractionTrace; return its id, or None if disabled/failed."""
    from life_graph.config import settings

    if not settings.self_improving_trace_enabled:
        return None
    try:
        from life_graph.self_improving.models import ExtractionTrace
        from life_graph.storage.database import async_session

        trace_id = uuid.uuid4()
        async with async_session() as session:
            session.add(
                ExtractionTrace(
                    id=trace_id,
                    tenant_id=tenant_id,
                    task_type=task_type,
                    prompt_version_id=prompt_version_id,
                    model=model,
                    input_text=input_text,
                    raw_output=raw_output,
                    facts=facts,
                    latency_ms=latency_ms,
                )
            )
            await session.commit()
        return trace_id
    except Exception:
        logger.warning("Could not record extraction trace", exc_info=True)
        return None
