"""Hourly: the daily "N cards due" study nudge, once its hour comes (services/study_nudge.py)."""

from __future__ import annotations

from life_graph.storage.database import async_session


async def send_study_nudge(ctx: dict | None = None) -> dict:
    from life_graph.services import study_nudge

    return await study_nudge.run(async_session)
