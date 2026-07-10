"""Watcher API routes (Era 6 Ambient AI).

~14 endpoints covering watcher configs, events, tech radar,
notification channels, and notifications.

Prefix: /watchers
Tags: [watchers]
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, update, delete

from life_graph.api.responses import success_response, paginated_response
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import async_session
from life_graph.watchers.schemas import (
    AcknowledgeRequest,
    BulkAcknowledgeRequest,
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    NotificationResponse,
    TechRadarResponse,
    WatchConfigResponse,
    WatchConfigUpdate,
    WatcherRunResponse,
    WatchEventResponse,
    WatchEventSummary,
)

router = APIRouter(prefix="/watchers", tags=["watchers"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_tenant() -> str:
    """Get current tenant ID from context."""
    try:
        return get_current_tenant_id()
    except Exception:
        return "default"


# ── Watcher Config ────────────────────────────────────────────────────────────


@router.get(
    "/configs",
    summary="List all watcher configurations",
)
async def list_watcher_configs():
    """List all watcher configurations for the current tenant."""
    from life_graph.watchers.models import WatchConfig

    tenant_id = _get_tenant()

    async with async_session() as session:
        result = await session.execute(
            select(WatchConfig).where(
                WatchConfig.tenant_id == tenant_id,
            ).order_by(WatchConfig.watcher_name)
        )
        rows = result.scalars().all()

    return success_response(
        data=[WatchConfigResponse.model_validate(r) for r in rows],
    )


@router.patch(
    "/configs/{watcher_name}",
    summary="Update a watcher configuration",
)
async def update_watcher_config(
    watcher_name: str,
    body: WatchConfigUpdate,
):
    """Update the configuration for a specific watcher."""
    from life_graph.watchers.models import WatchConfig

    tenant_id = _get_tenant()

    async with async_session() as session:
        result = await session.execute(
            select(WatchConfig).where(
                WatchConfig.tenant_id == tenant_id,
                WatchConfig.watcher_name == watcher_name,
            )
        )
        config = result.scalar_one_or_none()

        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Watcher config '{watcher_name}' not found",
            )

        update_data = body.model_dump(exclude_unset=True)
        if update_data:
            for key, value in update_data.items():
                setattr(config, key, value)
            config.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(config)

    return success_response(data=WatchConfigResponse.model_validate(config))


@router.post(
    "/{watcher_name}/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a manual watcher run",
)
async def trigger_watcher_run(watcher_name: str):
    """Trigger an immediate run of a specific watcher.

    The run executes asynchronously; returns the run record.
    """
    from life_graph.watchers.models import WatcherRun

    tenant_id = _get_tenant()

    run_id = uuid.uuid4()
    async with async_session() as session:
        run = WatcherRun(
            id=run_id,
            tenant_id=tenant_id,
            watcher_name=watcher_name,
            status="queued",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

    return success_response(data=WatcherRunResponse.model_validate(run))


@router.get(
    "/runs",
    summary="List watcher runs",
)
async def list_watcher_runs(
    watcher_name: str | None = Query(None, description="Filter by watcher"),
    limit: int = Query(20, ge=1, le=100),
):
    """List recent watcher runs, optionally filtered by watcher name."""
    from life_graph.watchers.models import WatcherRun

    tenant_id = _get_tenant()

    query = select(WatcherRun).where(
        WatcherRun.tenant_id == tenant_id,
    )
    if watcher_name:
        query = query.where(WatcherRun.watcher_name == watcher_name)

    query = query.order_by(WatcherRun.started_at.desc()).limit(limit)

    async with async_session() as session:
        result = await session.execute(query)
        rows = result.scalars().all()

    return success_response(
        data=[WatcherRunResponse.model_validate(r) for r in rows],
    )


# ── Watch Events ──────────────────────────────────────────────────────────────


@router.get(
    "/events",
    summary="List watch events",
)
async def list_watch_events(
    severity: str | None = Query(None, description="Filter by severity"),
    acknowledged: bool | None = Query(None, description="Filter by acknowledged status"),
    watcher_name: str | None = Query(None, description="Filter by watcher"),
    limit: int = Query(50, ge=1, le=200),
):
    """List watch events with optional filters."""
    from life_graph.watchers.models import WatchEvent

    tenant_id = _get_tenant()

    query = select(WatchEvent).where(WatchEvent.tenant_id == tenant_id)

    if severity:
        query = query.where(WatchEvent.severity == severity)
    if acknowledged is not None:
        if acknowledged:
            query = query.where(WatchEvent.acknowledged_at.is_not(None))
        else:
            query = query.where(WatchEvent.acknowledged_at.is_(None))
    if watcher_name:
        query = query.where(WatchEvent.watcher_name == watcher_name)

    query = query.order_by(WatchEvent.created_at.desc()).limit(limit)

    async with async_session() as session:
        result = await session.execute(query)
        rows = result.scalars().all()

    return success_response(
        data=[WatchEventResponse.model_validate(r) for r in rows],
    )


@router.post(
    "/events/{event_id}/acknowledge",
    summary="Acknowledge a single event",
)
async def acknowledge_event(
    event_id: uuid.UUID,
    body: AcknowledgeRequest = AcknowledgeRequest(),
):
    """Acknowledge a watch event by ID."""
    from life_graph.watchers.models import WatchEvent

    tenant_id = _get_tenant()

    async with async_session() as session:
        result = await session.execute(
            select(WatchEvent).where(
                WatchEvent.id == event_id,
                WatchEvent.tenant_id == tenant_id,
            )
        )
        event = result.scalar_one_or_none()

        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event {event_id} not found",
            )

        event.acknowledged_at = datetime.now(timezone.utc)
        event.acknowledged_by = body.acknowledged_by
        await session.commit()
        await session.refresh(event)

    return success_response(data=WatchEventResponse.model_validate(event))


@router.post(
    "/events/acknowledge-all",
    summary="Bulk acknowledge events",
)
async def bulk_acknowledge_events(
    body: BulkAcknowledgeRequest = BulkAcknowledgeRequest(),
):
    """Acknowledge multiple events at once.

    If event_ids is provided, only those events are acknowledged.
    Otherwise, filters by watcher_name and severity.
    """
    from life_graph.watchers.models import WatchEvent

    tenant_id = _get_tenant()
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        query = (
            update(WatchEvent)
            .where(
                WatchEvent.tenant_id == tenant_id,
                WatchEvent.acknowledged_at.is_(None),
            )
        )

        if body.event_ids:
            query = query.where(WatchEvent.id.in_(body.event_ids))
        else:
            if body.watcher_name:
                query = query.where(WatchEvent.watcher_name == body.watcher_name)
            if body.severity:
                query = query.where(WatchEvent.severity == body.severity)

        result = await session.execute(
            query.values(
                acknowledged_at=now,
                acknowledged_by=body.acknowledged_by,
            )
        )
        await session.commit()

    return success_response(
        data={"acknowledged_count": result.rowcount},
    )


@router.get(
    "/events/summary",
    summary="Get event summary counts",
)
async def event_summary():
    """Get aggregated event counts by severity and watcher."""
    from life_graph.watchers.models import WatchEvent

    tenant_id = _get_tenant()

    async with async_session() as session:
        # Total and unacknowledged
        total_result = await session.execute(
            select(func.count(WatchEvent.id)).where(
                WatchEvent.tenant_id == tenant_id,
            )
        )
        total = total_result.scalar() or 0

        unack_result = await session.execute(
            select(func.count(WatchEvent.id)).where(
                WatchEvent.tenant_id == tenant_id,
                WatchEvent.acknowledged_at.is_(None),
            )
        )
        unack = unack_result.scalar() or 0

        # By severity
        sev_result = await session.execute(
            select(WatchEvent.severity, func.count(WatchEvent.id))
            .where(WatchEvent.tenant_id == tenant_id)
            .group_by(WatchEvent.severity)
        )
        by_severity = {row[0]: row[1] for row in sev_result.fetchall()}

        # By watcher
        watcher_result = await session.execute(
            select(WatchEvent.watcher_name, func.count(WatchEvent.id))
            .where(WatchEvent.tenant_id == tenant_id)
            .group_by(WatchEvent.watcher_name)
        )
        by_watcher = {row[0] or "unknown": row[1] for row in watcher_result.fetchall()}

    summary = WatchEventSummary(
        total=total,
        by_severity=by_severity,
        by_watcher=by_watcher,
        unacknowledged=unack,
    )

    return success_response(data=summary.model_dump())


# ── Tech Radar ────────────────────────────────────────────────────────────────


@router.get(
    "/tech-radar",
    summary="List tech radar articles",
)
async def list_tech_radar(
    source: str | None = Query(None, description="Filter by source"),
    min_score: float | None = Query(None, ge=0.0, le=1.0, description="Min relevance score"),
    days: int | None = Query(None, ge=1, description="Last N days"),
    limit: int = Query(20, ge=1, le=100),
):
    """List tech radar articles with optional filters."""
    from life_graph.watchers.models import TechRadarItem

    tenant_id = _get_tenant()

    query = select(TechRadarItem).where(
        TechRadarItem.tenant_id == tenant_id,
    )

    if source:
        query = query.where(TechRadarItem.source == source)
    if min_score is not None:
        query = query.where(TechRadarItem.score >= min_score)
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.where(TechRadarItem.scraped_at >= since)

    query = query.order_by(
        TechRadarItem.score.desc(),
    ).limit(limit)

    async with async_session() as session:
        result = await session.execute(query)
        rows = result.scalars().all()

    return success_response(
        data=[TechRadarResponse.model_validate(r) for r in rows],
    )


# ── Notification Channels ────────────────────────────────────────────────────


@router.get(
    "/notification-channels",
    summary="List notification channels",
)
async def list_notification_channels():
    """List all notification channels for the current tenant."""
    from life_graph.watchers.models import NotificationChannel

    tenant_id = _get_tenant()

    async with async_session() as session:
        result = await session.execute(
            select(NotificationChannel).where(
                NotificationChannel.tenant_id == tenant_id,
            ).order_by(NotificationChannel.priority.desc())
        )
        rows = result.scalars().all()

    return success_response(
        data=[NotificationChannelResponse.model_validate(r) for r in rows],
    )


@router.post(
    "/notification-channels",
    status_code=status.HTTP_201_CREATED,
    summary="Create a notification channel",
)
async def create_notification_channel(body: NotificationChannelCreate):
    """Create a new notification channel."""
    from life_graph.watchers.models import NotificationChannel

    tenant_id = _get_tenant()
    now = datetime.now(timezone.utc)

    channel = NotificationChannel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        channel_type=body.channel_type,
        config=body.config,
        priority=body.priority,
        enabled=body.enabled,
        created_at=now,
        updated_at=now,
    )

    async with async_session() as session:
        session.add(channel)
        await session.commit()
        await session.refresh(channel)

    return success_response(
        data=NotificationChannelResponse.model_validate(channel),
    )


@router.patch(
    "/notification-channels/{channel_id}",
    summary="Update a notification channel",
)
async def update_notification_channel(
    channel_id: uuid.UUID,
    body: NotificationChannelUpdate,
):
    """Update an existing notification channel."""
    from life_graph.watchers.models import NotificationChannel

    tenant_id = _get_tenant()

    async with async_session() as session:
        result = await session.execute(
            select(NotificationChannel).where(
                NotificationChannel.id == channel_id,
                NotificationChannel.tenant_id == tenant_id,
            )
        )
        channel = result.scalar_one_or_none()

        if channel is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification channel {channel_id} not found",
            )

        update_data = body.model_dump(exclude_unset=True)
        if update_data:
            for key, value in update_data.items():
                setattr(channel, key, value)
            channel.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(channel)

    return success_response(
        data=NotificationChannelResponse.model_validate(channel),
    )


@router.delete(
    "/notification-channels/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notification channel",
    response_class=Response,
)
async def delete_notification_channel(channel_id: uuid.UUID):
    """Delete a notification channel."""
    from life_graph.watchers.models import NotificationChannel

    tenant_id = _get_tenant()

    async with async_session() as session:
        result = await session.execute(
            select(NotificationChannel).where(
                NotificationChannel.id == channel_id,
                NotificationChannel.tenant_id == tenant_id,
            )
        )
        channel = result.scalar_one_or_none()

        if channel is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification channel {channel_id} not found",
            )

        await session.delete(channel)
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Notifications ─────────────────────────────────────────────────────────────


@router.get(
    "/notifications",
    summary="List notifications",
)
async def list_notifications(
    notification_status: str | None = Query(None, alias="status", description="Filter by status"),
    channel: str | None = Query(None, description="Filter by channel type"),
    limit: int = Query(50, ge=1, le=200),
):
    """List notifications with optional filters."""
    from life_graph.watchers.models import Notification

    tenant_id = _get_tenant()

    query = select(Notification).where(Notification.tenant_id == tenant_id)

    if notification_status:
        query = query.where(Notification.status == notification_status)
    if channel:
        query = query.where(Notification.channel_type == channel)

    query = query.order_by(Notification.created_at.desc()).limit(limit)

    async with async_session() as session:
        result = await session.execute(query)
        rows = result.scalars().all()

    return success_response(
        data=[NotificationResponse.model_validate(r) for r in rows],
    )
