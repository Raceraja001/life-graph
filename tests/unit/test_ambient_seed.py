import pytest
from unittest.mock import AsyncMock
from life_graph.kernel.ambient import seed_ambient_jobs, AMBIENT_JOBS


@pytest.mark.asyncio
async def test_seed_creates_missing_jobs_and_deactivates_tutor():
    scheduler = AsyncMock()
    scheduler.list_all = AsyncMock(return_value=([], 0))  # nothing exists yet
    created_rows = {j["name"]: {"id": j["name"], "name": j["name"]} for j in AMBIENT_JOBS}
    scheduler.create = AsyncMock(side_effect=lambda t, d: created_rows[d["name"]])
    scheduler.update = AsyncMock(return_value={"id": "tutor-daily"})

    n = await seed_ambient_jobs(scheduler, "default")

    # Task 6: cody-ambient (seeded inactive, like ops-ambient) joins the ambient job set.
    assert n == 5
    names = [c.args[1]["name"] for c in scheduler.create.await_args_list]
    assert set(names) == {
        "scout-daily",
        "admin-daily",
        "tutor-daily",
        "ops-ambient",
        "cody-ambient",
    }
    # tutor, ops-ambient, cody-ambient (all seeded inactive) deactivated after creation
    assert scheduler.update.await_count == 3
    deactivated = {c.args[1] for c in scheduler.update.await_args_list}
    assert deactivated == {"tutor-daily", "ops-ambient", "cody-ambient"}


@pytest.mark.asyncio
async def test_seed_is_idempotent_when_jobs_exist():
    scheduler = AsyncMock()
    scheduler.list_all = AsyncMock(return_value=(
        [
            {"name": "scout-daily"},
            {"name": "admin-daily"},
            {"name": "tutor-daily"},
            {"name": "ops-ambient"},
            {"name": "cody-ambient"},
        ],
        5,
    ))
    scheduler.create = AsyncMock()
    n = await seed_ambient_jobs(scheduler, "default")
    assert n == 0
    scheduler.create.assert_not_awaited()
