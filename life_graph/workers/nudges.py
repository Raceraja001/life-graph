"""Every 30 minutes: nudge the owner about what they said they would do (services/nudges.py)."""

from __future__ import annotations

from life_graph.storage.database import async_session


async def send_nudges(ctx: dict | None = None) -> dict:
    from life_graph.services import nudges

    return await nudges.run(async_session)
