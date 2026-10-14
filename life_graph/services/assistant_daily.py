"""The assistant's daily sweep and its brief section.

One worker cron (``run_assistant_daily``, an hour before the daily brief)
walks every feature of docs/specs/assistant-capabilities.md that has
something to remind the user of, so the reminders are already held when the
brief is composed. Each feature exposes the same two things:

- ``sweep(session_factory, tenant_id, today, notifications) -> int``
- a line for the brief, built from rows only (no model call).

A failing feature is logged and skipped; it never stops the others.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import distinct, select

logger = logging.getLogger(__name__)

Sweep = Callable[[Any, str, date, Any], Awaitable[int]]


def _features() -> list[tuple[str, Any, Sweep]]:
    """(name, model holding tenant rows, sweep function) for each feature."""
    from life_graph.models.assistant import Document, MoneyBudget
    from life_graph.services import documents, money

    return [
        ("documents", Document, documents.sweep_reminders),
        ("budgets", MoneyBudget, money.sweep_budgets),
    ]


def user_today() -> date:
    from zoneinfo import ZoneInfo

    from life_graph.config import settings

    try:
        return datetime.now(ZoneInfo(settings.user_timezone)).date()
    except Exception:  # noqa: BLE001
        return datetime.now(UTC).date()


async def run_daily(session_factory, notifications, today: date | None = None) -> dict[str, Any]:
    today = today or user_today()
    report: dict[str, Any] = {}
    for name, model, sweep in _features():
        try:
            async with session_factory() as session:
                # Discovery across tenants is the point of a sweep; each
                # tenant's rows are then read with its own id.
                tenants = (await session.execute(select(distinct(model.tenant_id)))).scalars().all()
        except Exception:
            logger.warning("assistant daily: listing tenants for %s failed", name, exc_info=True)
            continue
        sent = 0
        for tenant_id in tenants:
            try:
                sent += await sweep(session_factory, tenant_id, today, notifications)
            except Exception:
                logger.warning("assistant daily: %s failed for %s", name, tenant_id, exc_info=True)
        report[name] = {"tenants": len(tenants), "sent": sent}
    return report


async def brief_lines(session_factory, tenant_id: str, today: date | None = None) -> list[str]:
    """Lines for the daily brief. They leave the machine: no amounts, no numbers."""
    today = today or user_today()
    lines: list[str] = []
    try:
        from life_graph.services import documents

        async with session_factory() as session:
            docs = await documents.expiring(session, tenant_id, today, within_days=30)
        if line := documents.brief_line(docs, today):
            lines.append(line)
    except Exception:
        logger.warning("brief: documents line failed for %s", tenant_id, exc_info=True)
    try:
        from life_graph.services import money

        async with session_factory() as session:
            spending = await money.summary(session, tenant_id, None, today)
        if line := money.brief_line(spending):
            lines.append(line)
    except Exception:
        logger.warning("brief: budgets line failed for %s", tenant_id, exc_info=True)
    return lines
