"""Daily Brief composer — one delivery channel for everything.

Compresses everything the system wants from or for the user into a single
daily notification: held notifications, today's interview questions,
yesterday's capture summary, and the watcher digest. Silence is
acceptable; noise is not — if there is no content, no brief is sent.

The composed brief is stored as a kernel ``Notification`` with
``metadata.kind = "daily_brief"`` and announced via ``BRIEF_COMPOSED``
(pushed over WebSocket through the Redis bridge; future surfaces like
WhatsApp/PWA subscribe to the same event).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.config import settings
from life_graph.core.events import EventBus, EventType
from life_graph.models.db import CaptureEvent, Decision, Memory, Notification
from life_graph.services.interview import InterviewService

logger = logging.getLogger(__name__)

BRIEF_KIND = "daily_brief"


class BriefComposer:
    """Composes and stores the daily brief for a tenant."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus

    # ── Compose ───────────────────────────────────────────────

    async def compose_daily(self, tenant_id: str) -> dict[str, Any] | None:
        """Compose today's brief. Returns None when there is nothing to say.

        Sections, in order:
        1. Held / high-priority notifications since the last brief
        2. Today's interview questions (generated here, budgeted)
        3. Yesterday's capture summary (one line)
        4. Watcher digest (event counts per watcher, last 24h)
        """
        now = datetime.now(UTC)
        since = now - timedelta(hours=24)

        # 1+2 — interview questions (generation includes the expire sweep)
        async with self._session_factory() as session:
            interview = InterviewService(session, self._event_bus)
            questions = await interview.generate_daily(
                tenant_id, max_questions=settings.interview_max_questions_per_day
            )
            question_data = [
                {"id": str(q.id), "question": q.question, "origin": q.origin}
                for q in questions
            ]
            await session.commit()

        held = await self._collect_held_notifications(tenant_id, since)
        capture_summary = await self._capture_summary(tenant_id, since)
        watcher_summary = await self._watcher_summary(tenant_id, since)
        big_decisions = await self._big_decisions(tenant_id, since)

        if not (
            held
            or question_data
            or capture_summary["total"]
            or watcher_summary
            or big_decisions
        ):
            logger.info("No brief content for tenant %s — staying silent", tenant_id)
            return None

        body = self._format_body(
            held, question_data, capture_summary, watcher_summary, big_decisions
        )
        title = f"Daily Brief — {now.date().isoformat()}"

        async with self._session_factory() as session:
            notif = Notification(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                priority="info",
                channel="terminal",
                title=title,
                body=body,
                extra_metadata={
                    "kind": BRIEF_KIND,
                    "questions": question_data,
                    "held_notification_ids": [h["id"] for h in held],
                    "capture_summary": capture_summary,
                    "watcher_summary": watcher_summary,
                    "big_decisions": big_decisions,
                },
                source_type="brief",
            )
            session.add(notif)
            await session.commit()
            notif_id = str(notif.id)

        if self._event_bus:
            await self._event_bus.emit(
                EventType.BRIEF_COMPOSED,
                {
                    "notification_id": notif_id,
                    "tenant_id": tenant_id,
                    "title": title,
                    "questions": len(question_data),
                    "held": len(held),
                },
            )

        logger.info(
            "Composed brief for %s: %d questions, %d held notifications",
            tenant_id, len(question_data), len(held),
        )
        return {
            "id": notif_id,
            "title": title,
            "body": body,
            "questions": question_data,
        }

    # ── Read ──────────────────────────────────────────────────

    async def get_today(self, tenant_id: str) -> dict[str, Any] | None:
        """Latest composed brief from the last 48h (dashboard/CLI rendering)."""
        since = datetime.now(UTC) - timedelta(hours=48)
        async with self._session_factory() as session:
            result = await session.execute(
                select(Notification)
                .where(
                    Notification.tenant_id == tenant_id,
                    Notification.source_type == "brief",
                    Notification.created_at >= since,
                )
                .order_by(Notification.created_at.desc())
                .limit(1)
            )
            notif = result.scalars().first()
            if notif is None:
                return None
            return {
                "id": str(notif.id),
                "title": notif.title,
                "body": notif.body,
                "created_at": notif.created_at.isoformat(),
                "metadata": notif.extra_metadata,
                "is_read": notif.is_read,
            }

    # ── Sections ──────────────────────────────────────────────

    async def _collect_held_notifications(
        self, tenant_id: str, since: datetime
    ) -> list[dict[str, Any]]:
        """Undelivered notifications held for the brief.

        Includes anything flagged ``deliver_at_brief`` plus undelivered
        critical/important notifications since the last brief. Marks
        collected rows as delivered.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(Notification).where(
                    Notification.tenant_id == tenant_id,
                    Notification.is_delivered.is_(False),
                    Notification.is_read.is_(False),
                    Notification.created_at >= since,
                    Notification.source_type != "brief",
                )
            )
            rows = list(result.scalars())
            held = []
            now = datetime.now(UTC)
            for n in rows:
                flagged = (n.extra_metadata or {}).get("deliver_at_brief")
                if flagged or n.priority in ("critical", "important"):
                    held.append(
                        {"id": str(n.id), "title": n.title, "priority": n.priority}
                    )
                    n.is_delivered = True
                    n.delivered_at = now
            await session.commit()
            held.sort(key=lambda h: 0 if h["priority"] == "critical" else 1)
            return held

    async def _capture_summary(
        self, tenant_id: str, since: datetime
    ) -> dict[str, int]:
        """One-line counts: captures, memories, decisions in the window."""
        async with self._session_factory() as session:
            captures = await session.scalar(
                select(func.count()).select_from(CaptureEvent).where(
                    CaptureEvent.tenant_id == tenant_id,
                    CaptureEvent.occurred_at >= since,
                )
            )
            memories = await session.scalar(
                select(func.count()).select_from(Memory).where(
                    Memory.tenant_id == tenant_id,
                    Memory.created_at >= since,
                )
            )
            decisions = await session.scalar(
                select(func.count()).select_from(Decision).where(
                    Decision.tenant_id == tenant_id,
                    Decision.created_at >= since,
                )
            )
        summary = {
            "captures": captures or 0,
            "memories": memories or 0,
            "decisions": decisions or 0,
        }
        summary["total"] = sum(summary.values())
        return summary

    async def _big_decisions(
        self, tenant_id: str, since: datetime
    ) -> list[dict[str, Any]]:
        """Big candidate decisions in the window, for a one-time challenge nudge.

        The 24h window + daily cadence means each big decision surfaces in at
        most one brief — "once, never nagging" without extra state.
        """
        from life_graph.services.judgment import BIG_DECISION_TAG

        async with self._session_factory() as session:
            result = await session.execute(
                select(Decision)
                .where(
                    Decision.tenant_id == tenant_id,
                    Decision.status == "candidate",
                    Decision.created_at >= since,
                    Decision.domain_tags.any(BIG_DECISION_TAG),
                )
                .order_by(Decision.created_at.desc())
                .limit(5)
            )
            return [
                {"id": str(d.id), "title": d.title}
                for d in result.scalars().all()
            ]

    async def _watcher_summary(
        self, tenant_id: str, since: datetime
    ) -> dict[str, int]:
        """Watch-event counts per watcher in the window (empty if none)."""
        try:
            from life_graph.watchers.models import WatchEvent
        except ImportError:
            return {}
        async with self._session_factory() as session:
            result = await session.execute(
                select(WatchEvent.watcher_name, func.count())
                .where(
                    WatchEvent.tenant_id == tenant_id,
                    WatchEvent.created_at >= since,
                )
                .group_by(WatchEvent.watcher_name)
            )
            return {name or "unknown": count for name, count in result.all()}

    # ── Formatting ────────────────────────────────────────────

    @staticmethod
    def _format_body(
        held: list[dict[str, Any]],
        questions: list[dict[str, Any]],
        capture_summary: dict[str, int],
        watcher_summary: dict[str, int],
        big_decisions: list[dict[str, Any]] | None = None,
    ) -> str:
        lines: list[str] = []
        if held:
            lines.append("## Needs attention")
            for h in held:
                lines.append(f"- [{h['priority']}] {h['title']}")
            lines.append("")
        if big_decisions:
            lines.append("## Big decision — want me to argue against it first?")
            for d in big_decisions:
                lines.append(
                    f"- {d['title']}  "
                    f"_(challenge: POST /judgment/decisions/{d['id']}/challenge)_"
                )
            lines.append("")
        if questions:
            lines.append("## Questions for you")
            for q in questions:
                lines.append(f"- {q['question']}  _(answer: POST /interview/{q['id']}/answer)_")
            lines.append("")
        if capture_summary["total"]:
            lines.append(
                f"Yesterday: {capture_summary['captures']} captures, "
                f"{capture_summary['memories']} new memories, "
                f"{capture_summary['decisions']} decisions."
            )
            lines.append("")
        if watcher_summary:
            parts = ", ".join(f"{name}: {n}" for name, n in sorted(watcher_summary.items()))
            lines.append(f"Watchers (24h): {parts}")
        return "\n".join(lines).strip()
