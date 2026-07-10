"""Transcript ingestion endpoint (Phase 5 — Personal AI).

Accepts chat transcripts from Antigravity, Claude, and ChatGPT,
extracts user preferences, and returns extraction results.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from life_graph.api.dependencies import get_transcript_extractor
from life_graph.api.responses import success_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.transcript_extractor import TranscriptExtractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["transcript"])


# ── Request/Response Schemas ──────────────────────────────────


class TranscriptMessage(BaseModel):
    """A single message in the transcript."""

    role: str = Field(..., description="Message role: user, assistant, human, ai")
    content: str | dict | list = Field(..., description="Message content (string or structured)")


class TranscriptIngestRequest(BaseModel):
    """Request body for transcript ingestion."""

    messages: list[TranscriptMessage] = Field(
        ..., min_length=1, description="List of transcript messages"
    )
    source: str = Field(
        "antigravity",
        description="Origin of the transcript: antigravity, claude, chatgpt",
    )
    format: str = Field(
        "plain",
        description="Transcript format to parse: plain, chatgpt, claude",
    )


# ── Endpoint ──────────────────────────────────────────────────


@router.post(
    "/transcript",
    summary="Ingest a chat transcript and extract preferences",
    status_code=status.HTTP_200_OK,
)
async def ingest_transcript(
    body: TranscriptIngestRequest,
    extractor: TranscriptExtractor = Depends(get_transcript_extractor),
):
    """Ingest a chat transcript and extract user preferences.

    Supports three formats:
    - **plain**: Simple {role, content} messages (also handles Human:/Assistant: blocks)
    - **chatgpt**: ChatGPT export JSON format
    - **claude**: Claude export JSON format

    The extractor identifies preference patterns in user messages,
    deduplicates against existing preferences, and detects contradictions.

    Returns counts of extracted, reinforced, and contradicted preferences
    along with per-preference detail.
    """
    tenant_id = get_current_tenant_id()

    # Convert Pydantic models to plain dicts for the extractor
    messages_raw = []
    for msg in body.messages:
        content = msg.content
        if isinstance(content, (dict, list)):
            # Pass structured content through for chatgpt/claude parsers
            messages_raw.append({"role": msg.role, **content} if isinstance(content, dict) else {"role": msg.role, "content": content})
        else:
            messages_raw.append({"role": msg.role, "content": content})

    result = await extractor.ingest(
        tenant_id=tenant_id,
        messages=messages_raw,
        source=body.source,
        format=body.format,
    )

    return success_response(data={
        "preferences_extracted": result.preferences_extracted,
        "preferences_reinforced": result.preferences_reinforced,
        "contradictions_found": result.contradictions_found,
        "processing_time_ms": result.processing_time_ms,
        "details": result.details,
    })
