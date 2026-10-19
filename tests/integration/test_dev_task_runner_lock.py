"""Only one process per database is the dev-task runner: a second Life Graph
instance (a preview from another worktree) must not claim queued tasks or run
startup recovery against the real runner's in-flight work.
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import skip_on_db_error


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_second_process_cannot_take_the_runner_lock_until_the_first_lets_go():
    from sqlalchemy.ext.asyncio import create_async_engine

    from life_graph.config import settings
    from life_graph.services.dev_tasks import acquire_runner_lock, release_runner_lock

    # Two engines = two independent "processes" as far as Postgres is concerned.
    first_engine = create_async_engine(settings.database_url)
    second_engine = create_async_engine(settings.database_url)
    try:
        first = await acquire_runner_lock(first_engine)
        assert first is not None, "nobody else should hold the lock in the test DB"
        try:
            assert await acquire_runner_lock(second_engine) is None
        finally:
            await release_runner_lock(first)

        again = await acquire_runner_lock(second_engine)
        assert again is not None, "releasing hands the lock to the next process"
        await release_runner_lock(again)
    finally:
        await first_engine.dispose()
        await second_engine.dispose()
