"""Notification Engine — priority-routed notification management.

Creates, queries, and manages notifications for kernel events
(task failures, schedule disables, threshold alerts, etc.).
Supports multiple delivery channels and priority-based filtering.

Each notification is tenant-scoped and tracks read/delivery state
independently. The engine does NOT handle delivery — it manages
the notification records that a delivery worker will process.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from life_graph.models.db import Notification

logger = logging.getLogger(__name__)

# Valid enum-like values (kept in code, not DB enums,
# matching the project's schema-less convention).
VALID_PRIORITIES = {"critical", "important", "info"}
VALID_CHANNELS = {"terminal", "email", "webhook"}


class NotificationEngine:
    """Manages notification CRUD and read-state tracking.

    Follows the same pattern as SchedulerService: accepts an
    async session_factory, runs each operation inside its own
    session context, and returns plain dicts.

    Args:
        session_factory: Async session factory for DB access.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    # ── Create ────────────────────────────────────────────

    async def create(
        self,
        tenant_id: str,
        title: str,
        body: str | None = None,
        *,
        priority: str = "info",
        channel: str = "terminal",
        source_type: str | None = None,
        source_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new notification record.

        Args:
            tenant_id: Tenant scope.
            title: Short summary (max 500 chars).
            body: Optional longer description.
            priority: One of 'critical', 'important', 'info'.
            channel: Delivery channel — 'terminal', 'email',
                or 'webhook'.
            source_type: Origin type (e.g. 'task', 'schedule').
            source_id: UUID of the originating entity.
            metadata: Arbitrary JSONB payload.

        Returns:
            Dict representation of the created notification.

        Raises:
            ValueError: If priority or channel is invalid.
        """
        if priority not in VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority {priority!r},"
                f" must be one of {VALID_PRIORITIES}"
            )
        if channel not in VALID_CHANNELS:
            raise ValueError(
                f"Invalid channel {channel!r},"
                f" must be one of {VALID_CHANNELS}"
            )

        notif_id = uuid.uuid4()
        parsed_source_id = (
            uuid.UUID(source_id) if source_id else None
        )

        async with self._session_factory() as session:
            notif = Notification(
                id=notif_id,
                tenant_id=tenant_id,
                priority=priority,
                channel=channel,
                title=title[:500],
                body=body,
                extra_metadata=metadata or {},
                is_read=False,
                is_delivered=False,
                source_type=source_type,
                source_id=parsed_source_id,
            )
            session.add(notif)
            await session.commit()
            await session.refresh(notif)

            logger.info(
                "Created notification %s [%s] %s",
                notif_id, priority, title[:60],
            )
            return self._notif_to_dict(notif)

    # ── List ──────────────────────────────────────────────

    async def list_all(
        self,
        tenant_id: str,
        *,
        priority: str | None = None,
        is_read: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int, int]:
        """List notifications for a tenant with filters.

        Args:
            tenant_id: Tenant scope.
            priority: Optional priority filter.
            is_read: Optional read-state filter.
            limit: Page size (default 20).
            offset: Page offset (default 0).

        Returns:
            Tuple of (notification dicts, total count,
            unread count).
        """
        async with self._session_factory() as session:
            # Base filters
            base_where = [
                Notification.tenant_id == tenant_id,
            ]
            if priority is not None:
                base_where.append(
                    Notification.priority == priority,
                )
            if is_read is not None:
                base_where.append(
                    Notification.is_read == is_read,
                )

            # Total count (with filters)
            count_stmt = (
                select(func.count())
                .select_from(Notification)
                .where(*base_where)
            )
            total = (
                await session.execute(count_stmt)
            ).scalar() or 0

            # Unread count (tenant-wide, no filters)
            unread_stmt = (
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.tenant_id == tenant_id,
                    Notification.is_read.is_(False),
                )
            )
            unread_count = (
                await session.execute(unread_stmt)
            ).scalar() or 0

            # Fetch page
            query = (
                select(Notification)
                .where(*base_where)
                .order_by(Notification.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(query)
            notifs = [
                self._notif_to_dict(n)
                for n in result.scalars().all()
            ]

            return notifs, total, unread_count

    # ── Mark Read ─────────────────────────────────────────

    async def mark_read(
        self,
        tenant_id: str,
        notification_id: str,
    ) -> dict[str, Any] | None:
        """Mark a single notification as read.

        Args:
            tenant_id: Tenant scope.
            notification_id: Notification UUID string.

        Returns:
            Updated notification dict, or None if not found.
        """
        uid = uuid.UUID(notification_id)

        async with self._session_factory() as session:
            stmt = (
                update(Notification)
                .where(
                    Notification.id == uid,
                    Notification.tenant_id == tenant_id,
                )
                .values(is_read=True)
                .returning(Notification.id)
            )
            result = await session.execute(stmt)
            if result.scalar_one_or_none() is None:
                return None
            await session.commit()

        # Re-fetch to return full dict
        async with self._session_factory() as session:
            fetch = select(Notification).where(
                Notification.id == uid,
                Notification.tenant_id == tenant_id,
            )
            result = await session.execute(fetch)
            notif = result.scalar_one_or_none()
            if notif is None:
                return None

            logger.info(
                "Marked notification %s as read", uid,
            )
            return self._notif_to_dict(notif)

    # ── Mark All Read ─────────────────────────────────────

    async def mark_all_read(
        self,
        tenant_id: str,
    ) -> int:
        """Mark all unread notifications as read.

        Args:
            tenant_id: Tenant scope.

        Returns:
            Number of notifications marked as read.
        """
        async with self._session_factory() as session:
            stmt = (
                update(Notification)
                .where(
                    Notification.tenant_id == tenant_id,
                    Notification.is_read.is_(False),
                )
                .values(is_read=True)
            )
            result = await session.execute(stmt)
            await session.commit()

            count = result.rowcount
            logger.info(
                "Marked %d notifications as read"
                " for tenant %s",
                count, tenant_id,
            )
            return count

    # ── Unread Count ──────────────────────────────────────

    async def get_unread_count(
        self,
        tenant_id: str,
    ) -> int:
        """Get the count of unread notifications.

        Args:
            tenant_id: Tenant scope.

        Returns:
            Integer count of unread notifications.
        """
        async with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.tenant_id == tenant_id,
                    Notification.is_read.is_(False),
                )
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    # ── Helpers ───────────────────────────────────────────

    @staticmethod
    def _notif_to_dict(
        notif: Notification,
    ) -> dict[str, Any]:
        """Convert a Notification ORM instance to dict."""
        return {
            "id": str(notif.id),
            "tenant_id": notif.tenant_id,
            "priority": notif.priority,
            "channel": notif.channel,
            "title": notif.title,
            "body": notif.body,
            "metadata": notif.extra_metadata or {},
            "is_read": notif.is_read,
            "is_delivered": notif.is_delivered,
            "delivered_at": (
                notif.delivered_at.isoformat()
                if notif.delivered_at else None
            ),
            "delivery_error": notif.delivery_error,
            "source_type": notif.source_type,
            "source_id": (
                str(notif.source_id)
                if notif.source_id else None
            ),
            "created_at": notif.created_at.isoformat(),
        }
