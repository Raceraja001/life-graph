"""Once a day: ask the owner to keep or drop what Jarvis noted (services/memory_check.py)."""

from __future__ import annotations

from life_graph.storage.database import async_session


async def send_memory_check(ctx: dict | None = None) -> dict:
    from life_graph.services import memory_check

    return await memory_check.run(async_session)
