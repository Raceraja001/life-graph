"""Token accounting for search and recall responses.

Recall and search exist to put text into a model's context window, so the
size of what they return is a first-class property of the endpoint — but
nothing measured it. This module puts the measurement in the ``meta`` slot
of :func:`life_graph.api.responses.success_response`, which is where
``paginated_response`` already keeps its bookkeeping. ``data`` stays
byte-identical, so no existing caller is affected.

Two numbers are reported:

``tokens_injected``
    What the payload actually sent will cost the reader.

``tokens_saved``
    What the *full* payload would have cost minus what was actually sent.
    Zero when the caller asked for the full payload — nothing was saved,
    and saying so is more useful than omitting the field.

Estimation uses :func:`life_graph.llm.context.estimate_tokens`, whose JSON
branch (3 chars/token) is the right ratio for a serialized API payload.
Deliberately **not** tiktoken: it is a BPE table for OpenAI models, and this
system routes to Gemini Flash / DeepSeek, so it would be a precise answer to
the wrong question while adding a dependency. See
``.comms/outbox/2026-07-05-002-ai-engine-gaps.md``.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from life_graph.llm.context import estimate_tokens

__all__ = ["payload_tokens", "serialize_payload", "token_meta"]


def serialize_payload(payload: Any) -> str:
    """Render *payload* the way FastAPI will put it on the wire.

    Pydantic models are dumped through their own JSON encoder so that UUIDs
    and datetimes serialize exactly as the response will; everything else
    falls back to ``json.dumps`` with ``str`` coercion.
    """
    if isinstance(payload, BaseModel):
        return payload.model_dump_json()
    try:
        return json.dumps(payload, default=str)
    except (TypeError, ValueError):
        return str(payload)


def payload_tokens(payload: Any) -> int:
    """Estimated token cost of *payload* once serialized."""
    return estimate_tokens(serialize_payload(payload))


def token_meta(
    sent: Any,
    full: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build the ``meta`` block for a search/recall response.

    Args:
        sent: The payload actually being returned.
        full: The payload that would have been returned without progressive
            disclosure. ``None`` means the full payload *is* what was sent.
        **extra: Additional meta keys (e.g. ``result_mode``).

    Returns:
        Dict with ``tokens_injected``, ``tokens_saved`` and any extras.
    """
    injected = payload_tokens(sent)
    saved = max(payload_tokens(full) - injected, 0) if full is not None else 0
    meta: dict[str, Any] = {"tokens_injected": injected, "tokens_saved": saved}
    meta.update(extra)
    return meta
