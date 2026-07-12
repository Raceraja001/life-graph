"""Daily Brief API routes.

The single delivery channel — everything the system wants from or for
the user, compressed into one daily notification.

Prefix: /brief
Tags: [brief]
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from life_graph.api.responses import success_response
from life_graph.core.events import event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.services.brief import BriefComposer
from life_graph.storage.database import async_session

router = APIRouter(prefix="/brief", tags=["brief"])


def _get_composer() -> BriefComposer:
    """Build a BriefComposer on the app-wide session factory."""
    return BriefComposer(async_session, event_bus)


@router.get(
    "/today",
    summary="Latest composed daily brief",
)
async def get_todays_brief(
    composer: BriefComposer = Depends(_get_composer),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Return the latest brief from the last 48 hours.

    Rendered by the dashboard, CLI, and (future) WhatsApp bot.
    404 when no brief has been composed — silence is intentional.
    """
    brief = await composer.get_today(tenant_id)
    if brief is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No brief composed in the last 48 hours",
        )
    return success_response(data=brief)


@router.post(
    "/compose",
    status_code=status.HTTP_201_CREATED,
    summary="Compose today's brief now",
)
async def compose_brief_now(
    composer: BriefComposer = Depends(_get_composer),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Manually trigger brief composition (normally done by the daily cron).

    Returns 204-style empty data when there is no content to brief.
    """
    brief = await composer.compose_daily(tenant_id)
    return success_response(
        data=brief or {"composed": False, "reason": "no content — staying silent"}
    )
