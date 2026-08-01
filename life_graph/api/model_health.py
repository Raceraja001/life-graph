"""Read-only free-LLM backend health for the status card."""

from __future__ import annotations

from fastapi import APIRouter

from life_graph.api.responses import success_response
from life_graph.services.llm_health import LLMHealth

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/models")
async def model_health():
    """Return each known free-LLM backend's current health state."""
    return success_response(await LLMHealth().snapshot())
