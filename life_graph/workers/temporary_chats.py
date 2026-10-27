"""Hourly: purge temporary chats quiet for a day (services/temporary_chats.py)."""

from __future__ import annotations

from life_graph.storage.database import async_session


async def purge_temporary_chats(ctx: dict | None = None) -> dict:
    from life_graph.services import temporary_chats

    return await temporary_chats.purge(async_session)
